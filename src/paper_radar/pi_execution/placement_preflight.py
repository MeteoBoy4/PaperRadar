"""产品身份的闭合 true 放置预检;不读取证据资格、lease、凭据或业务预算。"""

from __future__ import annotations

import math
import os
import selectors
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path
from time import monotonic, sleep
from uuid import uuid4

from paper_radar.pi_execution.errors import ExecutionError
from paper_radar.pi_execution.placement import (
    LinuxPlacementPlatform,
    PlacementTarget,
    _ptrace,
)
from paper_radar.pi_execution.placement_protocol import (
    NATIVE_PREFLIGHT_CHECKPOINTS,
    RUNTIME_ROOT,
)
from paper_radar.pi_execution.process import cleanup_process

_POST_PROFILE = "paperradar-placement-post-v1 (enforce)"
_TRUE = Path("/usr/bin/true")


@dataclass(frozen=True)
class PreflightProcessState:
    executable: tuple[int, int]
    tracer: int
    uid: tuple[int, ...]
    gid: tuple[int, ...]
    capabilities: tuple[int, ...]
    no_new_privs: int
    seccomp: int
    core: tuple[str, str]
    namespaces: tuple[tuple[int, int], tuple[int, int]]
    profile: str
    descriptors: frozenset[int]


class LinuxPreflightPlatform(LinuxPlacementPlatform):
    """可替换的 OS adapter;生产命令与两个目标路径固定。"""

    def expected_executable(self, *, final: bool) -> Path:
        return _TRUE if final else RUNTIME_ROOT / "placement-post"

    def inspect(self, pid: int) -> PreflightProcessState:
        root = Path("/proc") / str(pid)
        fields = dict(
            line.split(":", 1)
            for line in (root / "status").read_text().splitlines()
            if ":" in line
        )
        limits = (root / "limits").read_text().splitlines()
        core = next(
            line.split()[4:6]
            for line in limits
            if line.startswith("Max core file size")
        )
        executable = (root / "exe").stat()
        namespaces = tuple((root / "ns" / kind).stat() for kind in ("user", "mnt"))
        return PreflightProcessState(
            (executable.st_dev, executable.st_ino),
            int(fields["TracerPid"]),
            tuple(map(int, fields["Uid"].split())),
            tuple(map(int, fields["Gid"].split())),
            tuple(
                int(fields[name], 16)
                for name in ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb")
            ),
            int(fields["NoNewPrivs"]),
            int(fields["Seccomp"]),
            (core[0], core[1]),
            (
                (namespaces[0].st_dev, namespaces[0].st_ino),
                (namespaces[1].st_dev, namespaces[1].st_ino),
            ),
            (root / "attr/apparmor/current").read_text().strip(),
            frozenset(int(path.name) for path in (root / "fd").iterdir()),
        )


PREFLIGHT_PLATFORM = LinuxPreflightPlatform()


class NativePreflightError(ExecutionError):
    """保留封闭 native 检查点;仍使用原执行失败类别与清理路径。"""

    def __init__(self, checkpoint: str) -> None:
        if checkpoint not in NATIVE_PREFLIGHT_CHECKPOINTS:
            raise ValueError("native_checkpoint_invalid")
        self.checkpoint = checkpoint
        super().__init__("placement_exec_failed")


class _PreflightExited(ExecutionError):
    def __init__(self, code: int) -> None:
        self.code = code
        super().__init__("placement_exec_failed")


def _check_state(
    platform: LinuxPreflightPlatform,
    pid: int,
    *,
    final: bool,
    uid: int,
    gid: int,
    controller: int,
    initial: tuple[tuple[int, int], tuple[int, int]],
) -> None:
    state = platform.inspect(pid)
    expected = platform.expected_executable(final=final).stat()
    if (
        state.executable != (expected.st_dev, expected.st_ino)
        or state.tracer != (controller if final else 0)
        or state.uid != (uid,) * 4
        or state.gid != (gid,) * 4
        or state.capabilities != (0,) * 5
        or state.no_new_privs != 1
        or state.seccomp != 2
        or state.core != ("0", "0")
        or any(
            actual == before
            for actual, before in zip(state.namespaces, initial, strict=True)
        )
        or state.profile != _POST_PROFILE
        or not state.descriptors <= {0, 1, 2}
    ):
        raise ExecutionError("placement_exec_failed")


def _ready(child: subprocess.Popen[bytes], deadline: float) -> int:
    if child.stdout is None or child.stderr is None:
        raise ExecutionError("placement_handshake_invalid")
    with selectors.DefaultSelector() as selector:
        selector.register(child.stdout, selectors.EVENT_READ, "stdout")
        selector.register(child.stderr, selectors.EVENT_READ, "stderr")
        raw = bytearray()
        diagnostic = bytearray()
        while monotonic() < deadline:
            for key, _mask in selector.select(
                min(0.05, max(0, deadline - monotonic()))
            ):
                data = os.read(key.fd, 65)
                if not data:
                    selector.unregister(key.fd)
                    continue
                if key.data == "stderr":
                    diagnostic.extend(data)
                    if len(diagnostic) > 96 or raw:
                        raise ExecutionError("placement_handshake_invalid")
                    continue
                if diagnostic:
                    raise ExecutionError("placement_handshake_invalid")
                raw.extend(data)
                if len(raw) > 64:
                    raise ExecutionError("placement_handshake_invalid")
                if b"\n" in raw:
                    if (
                        not raw.startswith(b"R ")
                        or not raw.endswith(b"\n")
                        or raw.count(b"\n") != 1
                        or not raw[2:-1].isdigit()
                    ):
                        raise ExecutionError("placement_handshake_invalid")
                    pid = int(raw[2:-1])
                    if pid <= 1:
                        raise ExecutionError("placement_handshake_invalid")
                    return pid
            # Require both complete streams and the original failure exit code.
            # A known prefix, a partial line or extra bytes prove no checkpoint.
            if not selector.get_map():
                code = child.wait(timeout=max(0.001, deadline - monotonic()))
                for checkpoint in NATIVE_PREFLIGHT_CHECKPOINTS:
                    if (
                        code == 125
                        and not raw
                        and diagnostic
                        == ("placement_native_v1:" + checkpoint + "\n").encode()
                    ):
                        raise NativePreflightError(checkpoint)
                raise ExecutionError("placement_peer_exited")
    raise ExecutionError("placement_handshake_timeout")


def _exec_stop(pid: int, deadline: float) -> None:
    while monotonic() < deadline:
        waited, status = os.waitpid(pid, os.WNOHANG | 0x40000000)
        if waited:
            if os.WIFEXITED(status):
                raise _PreflightExited(os.WEXITSTATUS(status))
            if (
                not os.WIFSTOPPED(status)
                or status >> 16 != 4
                or os.WSTOPSIG(status) != signal.SIGTRAP
            ):
                raise ExecutionError("placement_exec_failed")
            return
        sleep(0.005)
    raise ExecutionError("placement_handshake_timeout")


def run_cold_preflight(*, product_uid: int, product_gid: int) -> None:
    """产品身份的固定冷预检;有限输出,无 manager、凭据或任意执行参数。"""
    if (
        type(product_uid) is not int
        or type(product_gid) is not int
        or product_uid <= 0
        or product_gid <= 0
        or (os.getuid(), os.geteuid(), os.getgid(), os.getegid())
        != (product_uid, product_uid, product_gid, product_gid)
    ):
        raise ExecutionError("placement_unavailable")
    child: subprocess.Popen[bytes] | None = None
    deadline = monotonic() + 10
    try:
        child = PREFLIGHT_PLATFORM.spawn(
            (str(RUNTIME_ROOT / "placement-pre"), "--preflight"), {}
        )
        if child.stdout is None or child.stderr is None:
            raise ExecutionError("placement_exec_failed")
        diagnostic = bytearray()
        with selectors.DefaultSelector() as selector:
            selector.register(child.stdout, selectors.EVENT_READ, "stdout")
            selector.register(child.stderr, selectors.EVENT_READ, "stderr")
            while selector.get_map() and monotonic() < deadline:
                for key, _mask in selector.select(
                    min(0.05, max(0, deadline - monotonic()))
                ):
                    data = os.read(key.fd, 97)
                    if not data:
                        selector.unregister(key.fd)
                    elif key.data == "stdout":
                        raise ExecutionError("placement_exec_failed")
                    else:
                        diagnostic.extend(data)
                        if len(diagnostic) > 96:
                            raise ExecutionError("placement_exec_failed")
            if selector.get_map():
                raise ExecutionError("placement_handshake_timeout")
        code = child.wait(timeout=max(0.001, deadline - monotonic()))
        if code == 0 and not diagnostic:
            return
        for checkpoint in NATIVE_PREFLIGHT_CHECKPOINTS:
            if (
                code == 125
                and diagnostic == ("placement_native_v1:" + checkpoint + "\n").encode()
            ):
                raise NativePreflightError(checkpoint)
        raise ExecutionError("placement_exec_failed")
    except (OSError, subprocess.SubprocessError):
        raise ExecutionError("placement_exec_failed") from None
    finally:
        if child is not None:
            cleanup_process(child)


def run_traced_preflight(
    target: PlacementTarget,
    *,
    product_uid: int,
    product_gid: int,
    timeout: float = 10,
    aggregate_manager: bool = False,
) -> None:
    """固定 native → SEIZE → 单字节释放 → true exec-stop → DETACH。

    target 由 root owner 验证后提供。本函数自身必须是产品 UID/GID,绝不 root
    tracer。仅输出受控异常,无私有 socket 或任意目标/环境/参数语言。
    """
    if (
        type(product_uid) is not int
        or type(product_gid) is not int
        or product_uid <= 0
        or product_gid <= 0
        or (os.getuid(), os.geteuid(), os.getgid(), os.getegid())
        != (product_uid, product_uid, product_gid, product_gid)
    ):
        raise ExecutionError("placement_unavailable")
    if (
        type(timeout) not in (int, float)
        or not math.isfinite(timeout)
        or not 0 < timeout <= 10
    ):
        raise ExecutionError("timeout_invalid")
    platform = PREFLIGHT_PLATFORM
    deadline = monotonic() + timeout
    child: subprocess.Popen[bytes] | None = None
    pid = 0
    traced = False
    try:
        env = (
            platform.manager_preflight_environment()
            if aggregate_manager
            else platform.manager_environment()
        )
        platform.verify(
            target, target.anchor_pid, target.anchor_start, "paperradar-anchor.service"
        )
        initial_stats = tuple(
            Path("/proc/self/ns", kind).stat() for kind in ("user", "mnt")
        )
        initial = (
            (initial_stats[0].st_dev, initial_stats[0].st_ino),
            (initial_stats[1].st_dev, initial_stats[1].st_ino),
        )
        controller = os.getpid()
        unit = f"paperradar-{uuid4().hex}.scope"
        child = platform.spawn(
            (
                "/usr/bin/systemd-run",
                "--user",
                "--scope",
                "--quiet",
                "--collect",
                "--expand-environment=no",
                "--slice=" + target.slice,
                "--unit=" + unit,
                str(RUNTIME_ROOT / "placement-pre"),
                "--preflight-traced",
                str(controller),
            ),
            env,
        )
        pid = _ready(child, deadline)
        if os.getpgid(pid) != child.pid:
            raise ExecutionError("placement_handshake_invalid")
        start = platform.process_identity(pid)[0]
        scope = platform.scope_identity(target, unit)
        platform.verify(target, pid, start, unit)
        _check_state(
            platform,
            pid,
            final=False,
            uid=product_uid,
            gid=product_gid,
            controller=controller,
            initial=initial,
        )
        _ptrace(0x4206, pid, 0x10 | 0x100000)  # SEIZE TRACEEXEC EXITKILL
        traced = True
        if child.stdin is None:
            raise ExecutionError("placement_handshake_invalid")
        child.stdin.write(b"G")
        child.stdin.close()
        _exec_stop(pid, deadline)
        platform.verify(target, pid, start, unit)
        if platform.scope_identity(target, unit) != scope:
            raise ExecutionError("placement_mismatch")
        _check_state(
            platform,
            pid,
            final=True,
            uid=product_uid,
            gid=product_gid,
            controller=controller,
            initial=initial,
        )
        _ptrace(17, pid)  # DETACH; no true instruction has run.
        traced = False
        child.wait(timeout=max(0.001, deadline - monotonic()))
        if child.stdout is None or child.stderr is None:
            raise ExecutionError("placement_exec_failed")
        for stream in (child.stdout, child.stderr):
            os.set_blocking(stream.fileno(), False)
        if (
            child.returncode != 0
            or child.stdout is None
            or child.stderr is None
            or os.read(child.stdout.fileno(), 1)
            or os.read(child.stderr.fileno(), 1)
        ):
            raise ExecutionError("placement_exec_failed")
    except ExecutionError as error:
        if isinstance(error, _PreflightExited):
            # waitpid has consumed the native peer's exit; never signal a reused
            # pid. A direct OS adapter child also needs Popen's status updated.
            traced = False
            if child is not None and child.pid == pid:
                child.returncode = error.code
            if error.code == 125 and child is not None:
                try:
                    child.wait(timeout=max(0.001, deadline - monotonic()))
                    if child.stdout is not None and child.stderr is not None:
                        for stream in (child.stdout, child.stderr):
                            os.set_blocking(stream.fileno(), False)
                        raw = os.read(child.stderr.fileno(), 97)
                        extra = os.read(child.stdout.fileno(), 1)
                        for checkpoint in NATIVE_PREFLIGHT_CHECKPOINTS:
                            if (
                                child.returncode == 125
                                and not extra
                                and raw
                                == ("placement_native_v1:" + checkpoint + "\n").encode()
                            ):
                                raise NativePreflightError(checkpoint) from None
                except (OSError, subprocess.SubprocessError):
                    pass
        raise
    except (
        OSError,
        ValueError,
        ChildProcessError,
        StopIteration,
        KeyError,
        subprocess.SubprocessError,
    ):
        raise ExecutionError("placement_exec_failed") from None
    finally:
        if traced:
            try:
                os.kill(pid, signal.SIGKILL)
                os.waitpid(pid, 0x40000000)
            except (ProcessLookupError, ChildProcessError):
                pass
        if child is not None:
            cleanup_process(child)
