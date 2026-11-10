"""认证、模型与 collector 共用的有界 scope 放置;不授予执行资格。"""

from __future__ import annotations

import ctypes
import json
import math
import os
import signal
import socket
import stat
import struct
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from time import monotonic, sleep
from typing import Self
from uuid import uuid4

from pydantic import model_validator

from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerError
from paper_radar.live_evidence.observation import load_current_observation
from paper_radar.live_evidence.receipt import WireModel, canonical_bytes
from paper_radar.live_evidence.types import BindingComponent as B
from paper_radar.llm.rpc_types import RpcProblem
from paper_radar.pi_execution import isolation
from paper_radar.pi_execution.errors import ExecutionError, ExecutionReason
from paper_radar.pi_execution.process import cleanup_process

PLACEMENT_POLICY_VERSION = "pi-placement-v1"
TARGET_FILENAME = "placement-target-v1.json"
_CGROUP_ROOT = Path("/sys/fs/cgroup")
_PROC_ROOT = Path("/proc")
_LIBC = ctypes.CDLL(None, use_errno=True)


class PlacementError(ExecutionError):
    """保留受控观察分类;来源失信和单纯观察租期不能混淆。"""

    def __init__(self, reason: ExecutionReason, *, source_reason: str) -> None:
        super().__init__(reason)
        self.source_reason = source_reason


@dataclass(frozen=True)
class CgroupIdentity:
    path: str
    device: int
    inode: int  # kernfs cgroup id: path equality alone never suffices.


class PlacementTarget(WireModel):
    format_version: int
    slice: str
    ancestors: tuple[CgroupIdentity, ...]
    anchor_pid: int
    anchor_start: int
    anchor_cgroup: str
    egress_digest: str
    resolver_view: str
    resolver_digest: str

    @model_validator(mode="after")
    def valid(self) -> Self:
        if (
            self.format_version != 1
            or self.slice != "paperradar.slice"
            or not self.ancestors
            or PurePosixPath(self.ancestors[0].path).name != self.slice
            or self.anchor_pid <= 0
            or self.anchor_start <= 0
            or self.anchor_cgroup
            != self.ancestors[0].path + "/paperradar-anchor.service"
            or not self.resolver_view.startswith("/run/paper-radar/")
            or any(
                len(value) != 64 or any(c not in "0123456789abcdef" for c in value)
                for value in (self.egress_digest, self.resolver_digest)
            )
        ):
            raise ValueError("placement_target_invalid")
        expected = PurePosixPath(self.ancestors[0].path)
        for item in self.ancestors:
            if (
                not expected.is_absolute()
                or ".." in expected.parts
                or str(expected) != item.path
                or item.device < 0
                or item.inode <= 0
            ):
                raise ValueError("placement_target_invalid")
            expected = expected.parent
        if self.ancestors[-1].path != "/":
            raise ValueError("placement_target_invalid")
        return self


def load_placement_target(*, now: datetime | None = None) -> PlacementTarget:
    """只从现有 root 所有受保护 inbox 读取,不接收用户自报的规则目标。"""
    try:
        ledger = EvidenceLedger()
        data = ledger._read_source(ledger.root / "inbox" / TARGET_FILENAME)
        target = PlacementTarget.model_validate_json(data)
        if canonical_bytes(target) != data:
            raise PlacementError(
                "placement_unavailable", source_reason="source_integrity"
            )
        observation = load_current_observation(ledger, now=now or datetime.now(UTC))
        if observation.binding[B.IPV4_EGRESS] != target.egress_digest or not {
            B.IPV4_EGRESS,
            B.OBSERVER,
        } <= set(observation.checked_components):
            raise ExecutionError("placement_mismatch")
        return target
    except LedgerError as error:
        raise PlacementError(
            "placement_unavailable", source_reason=error.category
        ) from None
    except (OSError, ValueError) as error:
        if isinstance(error, ExecutionError):
            raise
        raise PlacementError(
            "placement_unavailable", source_reason="source_untrusted"
        ) from None


def _proc(pid: int) -> tuple[int, str]:
    # comm can contain spaces and ')'; starttime is field 22.
    fields = (_PROC_ROOT / str(pid) / "stat").read_text().rsplit(")", 1)[1].split()
    lines = (_PROC_ROOT / str(pid) / "cgroup").read_text().splitlines()
    if len(lines) != 1 or not lines[0].startswith("0::/"):
        raise ExecutionError("placement_mismatch")
    return int(fields[19]), lines[0][3:]


def verify_placement(target: PlacementTarget, pid: int, start: int, unit: str) -> None:
    """公共 /proc 与 kernfs 身份核验;collector/observer 可复用,无环境或内存读取。"""
    try:
        if _proc(pid) != (start, target.ancestors[0].path + "/" + unit):
            raise ExecutionError("placement_mismatch")
        for item in target.ancestors:
            info = (_CGROUP_ROOT / item.path.lstrip("/")).lstat()
            if not stat.S_ISDIR(info.st_mode) or (info.st_dev, info.st_ino) != (
                item.device,
                item.inode,
            ):
                raise ExecutionError("placement_mismatch")
        if _proc(target.anchor_pid) != (target.anchor_start, target.anchor_cgroup):
            raise ExecutionError("placement_anchor_invalid")
    except ExecutionError:
        raise
    except (OSError, ValueError, IndexError):
        raise ExecutionError("placement_anchor_invalid") from None


def _manager() -> dict[str, str]:
    uid = os.getuid()
    env = {
        "PATH": "/usr/bin:/bin",
        "LANG": "C",
        "LC_ALL": "C",
        "XDG_RUNTIME_DIR": f"/run/user/{uid}",
        "DBUS_SESSION_BUS_ADDRESS": f"unix:path=/run/user/{uid}/bus",
    }
    try:
        for argv, expected in (
            (("/usr/bin/systemctl", "--user", "is-system-running"), b"running\n"),
            (
                (
                    "/usr/bin/loginctl",
                    "show-user",
                    str(uid),
                    "--property=Linger",
                    "--value",
                ),
                b"yes\n",
            ),
            (
                (
                    "/usr/bin/systemctl",
                    "--user",
                    "is-active",
                    "paperradar-anchor.service",
                ),
                b"active\n",
            ),
        ):
            result = subprocess.run(
                argv, env=env, capture_output=True, timeout=3, check=False
            )
            if result.returncode != 0 or result.stdout != expected:
                raise ExecutionError("placement_unavailable")
        return env
    except (OSError, subprocess.SubprocessError):
        raise ExecutionError("placement_unavailable") from None


def _ptrace(request: int, pid: int, data: int = 0) -> None:
    if _LIBC.ptrace(request, pid, 0, data) != 0:
        raise ExecutionError("placement_exec_failed")


class LinuxPlacementPlatform:
    """可替换的 Linux/systemd I/O 边界;产品只使用固定默认实现。"""

    def manager_environment(self) -> dict[str, str]:
        return _manager()

    def process_identity(self, pid: int) -> tuple[int, str]:
        return _proc(pid)

    def scope_identity(self, target: PlacementTarget, unit: str) -> tuple[int, int]:
        info = (_CGROUP_ROOT / target.ancestors[0].path.lstrip("/") / unit).stat()
        return info.st_dev, info.st_ino

    def verify(self, target: PlacementTarget, pid: int, start: int, unit: str) -> None:
        verify_placement(target, pid, start, unit)

    def spawn(
        self, argv: tuple[str, ...], env: dict[str, str]
    ) -> subprocess.Popen[bytes]:
        return subprocess.Popen(
            argv,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
            umask=0o077,
        )


PLACEMENT_PLATFORM = LinuxPlacementPlatform()


def check_placement_readiness() -> None:
    """公共只读诊断:不创建 scope,不读凭据,不授予模型资格。"""
    target = load_placement_target()
    PLACEMENT_PLATFORM.manager_environment()
    PLACEMENT_PLATFORM.verify(
        target, target.anchor_pid, target.anchor_start, "paperradar-anchor.service"
    )


class PlacedProcess:
    """先核阻塞封装,再 exec-stop 核同一进程,释放后才可认证或接收 prompt。"""

    def __init__(self, *, timeout: float = 10) -> None:
        if (
            type(timeout) not in (int, float)
            or not math.isfinite(timeout)
            or not 0 < timeout <= 10
        ):
            raise ExecutionError("timeout_invalid")
        self.target = load_placement_target()
        self._platform = PLACEMENT_PLATFORM
        env = self._platform.manager_environment()
        self.unit = f"paperradar-{uuid4().hex}.scope"
        self.child: subprocess.Popen[bytes] | None = None
        self.peer: socket.socket | None = None
        self.pid = 0
        self.start = 0
        self._scope_identity: tuple[int, int] | None = None
        self._traced = False
        self._released = False
        self._temporary = tempfile.TemporaryDirectory(
            prefix="paperradar-placement-", dir="/tmp"
        )
        try:
            with socket.socket(socket.AF_UNIX) as listener:
                listener.bind(self._temporary.name + "/handshake")
                listener.listen(1)
                listener.settimeout(timeout)
                self.child = self._platform.spawn(
                    (
                        "/usr/bin/systemd-run",
                        "--user",
                        "--scope",
                        "--quiet",
                        "--collect",
                        "--expand-environment=no",
                        "--slice=" + self.target.slice,
                        "--unit=" + self.unit,
                        sys.executable,
                        "-I",
                        str(Path(__file__).with_name("placement_wrapper.py")),
                        listener.getsockname(),
                        str(os.getpid()),
                    ),
                    env,
                )
                deadline = monotonic() + timeout
                while self.peer is None:
                    listener.settimeout(min(0.05, max(0.001, deadline - monotonic())))
                    try:
                        self.peer, _address = listener.accept()
                    except TimeoutError:
                        if self.child.poll() is not None:
                            raise ExecutionError("placement_peer_exited") from None
                        if monotonic() >= deadline:
                            raise ExecutionError(
                                "placement_handshake_timeout"
                            ) from None
            self.peer.settimeout(timeout)
            self.pid, uid, _gid = struct.unpack(
                "3i", self.peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
            )
            if uid != os.getuid() or os.getpgid(self.pid) != self.child.pid:
                raise ExecutionError("placement_handshake_invalid")
            if self.peer.recv(1) != b"R":
                raise ExecutionError("placement_handshake_invalid")
            self.start = self._platform.process_identity(self.pid)[0]
            self.recheck()
            _ptrace(0x4206, self.pid, 0x10 | 0x100000)  # SEIZE, TRACEEXEC, EXITKILL
            self._traced = True
        except TimeoutError:
            self.close()
            raise ExecutionError("placement_handshake_timeout") from None
        except (
            OSError,
            ValueError,
            ChildProcessError,
            subprocess.SubprocessError,
        ) as error:
            self.close()
            if isinstance(error, ExecutionError):
                raise
            raise ExecutionError("placement_handshake_invalid") from None
        except BaseException:
            self.close()
            raise

    def recheck(self) -> None:
        # Re-read the protected current target: replacement invalidates the handle.
        if load_placement_target() != self.target:
            raise ExecutionError("placement_mismatch")
        self._platform.verify(self.target, self.pid, self.start, self.unit)
        current_scope = self._platform.scope_identity(self.target, self.unit)
        if self._scope_identity is not None and current_scope != self._scope_identity:
            raise ExecutionError("placement_mismatch")
        self._scope_identity = current_scope

    def execute(
        self,
        argv: tuple[str, ...],
        *,
        env: dict[str, str],
        cwd: Path,
        install: Path,
        attempt: Path | None,
        proxy_port: int | None,
        pass_fds: tuple[int, ...],
        timeout: float = 10,
        before_release: Callable[[], None] | None = None,
    ) -> subprocess.Popen[bytes]:
        if (
            type(timeout) not in (int, float)
            or not math.isfinite(timeout)
            or not 0 < timeout <= 10
        ):
            raise ExecutionError("timeout_invalid")
        if self._released or self.peer is None or self.child is None:
            raise ExecutionError("placement_handshake_invalid")
        try:
            self.recheck()
            # SCM_RIGHTS preserves protection even if systemd-run closes fds.
            payload = json.dumps(
                {
                    "argv": argv,
                    "env": env,
                    "cwd": str(cwd),
                    "install": str(install),
                    "attempt": str(attempt) if attempt else None,
                    "proxy_port": proxy_port,
                    "resolver_view": self.target.resolver_view,
                    "resolver_digest": self.target.resolver_digest,
                    "runtime_paths": [str(path) for path in isolation._RUNTIME_PATHS],
                }
            ).encode()
            if len(payload) > 512 * 1024:
                raise ExecutionError("placement_handshake_invalid")
            import array

            rights = array.array("i", pass_fds)
            self.peer.sendmsg(
                [struct.pack("!I", len(payload))],
                [(socket.SOL_SOCKET, socket.SCM_RIGHTS, rights)],
            )
            self.peer.sendall(payload)
            deadline = monotonic() + timeout
            while True:
                waited, status = os.waitpid(self.pid, os.WNOHANG | 0x40000000)
                if waited:
                    if not os.WIFSTOPPED(status) or status >> 16 != 4:
                        raise ExecutionError("placement_exec_failed")
                    break
                if monotonic() >= deadline:
                    raise ExecutionError("placement_handshake_timeout")
                sleep(0.005)
            self.recheck()
            if not os.path.samefile(f"/proc/{self.pid}/exe", argv[0]):
                raise ExecutionError("placement_exec_failed")
            status_text = Path(f"/proc/{self.pid}/status").read_text()
            limits = Path(f"/proc/{self.pid}/limits").read_text().splitlines()
            if "NoNewPrivs:\t1" not in status_text or not any(
                line.split()[:5] == ["Max", "core", "file", "size", "0"]
                and line.split()[5] == "0"
                for line in limits
            ):
                raise ExecutionError("placement_exec_failed")
            if before_release is not None:
                before_release()
            _ptrace(
                17, self.pid
            )  # DETACH: no target instruction ran before verification.
            self._traced = False
            self._released = True
            self.peer.close()
            self.peer = None
            return self.child
        except TimeoutError:
            self.close()
            raise ExecutionError("placement_handshake_timeout") from None
        except (OSError, ValueError, ChildProcessError) as error:
            self.close()
            if isinstance(error, ExecutionError):
                raise
            raise ExecutionError("placement_exec_failed") from None
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        try:
            self._close()
        except (OSError, RpcProblem, subprocess.SubprocessError):
            raise ExecutionError("cleanup_failed") from None

    def _close(self) -> None:
        if self.peer is not None:
            self.peer.close()
            self.peer = None
        if self.child is not None:
            if self._traced:
                try:
                    os.kill(self.pid, signal.SIGKILL)
                    os.waitpid(self.pid, 0x40000000)
                except (ProcessLookupError, ChildProcessError):
                    pass
                self._traced = False
            # Failed group cleanup cannot claim successful resource removal.
            cleanup_process(self.child)
            self.child = None
        self._temporary.cleanup()

    def handoff(self) -> None:
        """调用方已接管 PipeSession 后转移进程组所有权,身份仍可复核。"""
        if not self._released:
            raise ExecutionError("placement_handshake_invalid")
        self.child = None
