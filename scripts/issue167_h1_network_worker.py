"""H1待审包的无凭据合成worker/peer;本模块不在导入时联网或执行服务。"""

from __future__ import annotations

import argparse
import errno
import importlib
import importlib.util
import json
import os
import resource
import selectors
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Literal, TypedDict, cast

if TYPE_CHECKING:
    from scripts.issue167_h1_phase import Plan

Phase = Literal["a", "b"]
Outcome = Literal["allowed", "denied", "unknown"]
ErrnoCategory = Literal[
    "none",
    "permission_denied",
    "admin_unreachable",
    "connection_refused",
    "timed_out",
    "other",
    "address_family_unavailable",
]


class WorkerRejected(ValueError):
    """只携带闭集原因,不携请求内容或外部异常。"""


@dataclass(frozen=True)
class Probe:
    case: str
    kind: Literal["tcp", "udp", "socket_check"]
    family: Literal["v4", "v6"]
    port: int
    expected: Literal["allow", "deny"]


class ProbeRow(TypedDict):
    case: str
    kind: str
    family: str
    port: int
    expected: str
    outcome: Outcome
    errno_category: ErrnoCategory


def probes(plan: Plan, phase: Phase) -> tuple[Probe, ...]:
    if phase not in ("a", "b"):
        raise WorkerRejected("phase_invalid")
    current = plan.port_a if phase == "a" else plan.port_b
    other = plan.port_b if phase == "a" else plan.port_a
    specifications: tuple[
        tuple[str, Literal["tcp", "udp"], int, Literal["allow", "deny"]], ...
    ] = (
        ("current", "tcp", current, "allow"),
        ("other", "tcp", other, "deny"),
        ("blocked", "tcp", plan.blocked_port, "deny"),
        ("blocked", "udp", plan.blocked_port, "deny"),
        ("dns", "udp", 53, "deny"),
    )
    families: tuple[Literal["v4", "v6"], ...] = (
        ("v4",) if plan.network_mode == "ipv4_only" else ("v4", "v6")
    )
    connections = tuple(
        Probe(f"{family}-{label}-{kind}", kind, family, port, expected)
        for label, kind, port, expected in specifications
        for family in families
    )
    if plan.network_mode == "ipv4_only":
        return (
            Probe("v6-socket-tcp", "socket_check", "v6", 0, "deny"),
            Probe("v6-socket-udp", "socket_check", "v6", 0, "deny"),
            *connections,
        )
    return connections


def classify_error(error: OSError) -> tuple[Outcome, ErrnoCategory]:
    if error.errno in {errno.EPERM, errno.EACCES}:
        return "denied", "permission_denied"
    if error.errno in {errno.EHOSTUNREACH, errno.ENETUNREACH}:
        return "denied", "admin_unreachable"
    if error.errno == errno.ECONNREFUSED:
        return "unknown", "connection_refused"
    if isinstance(error, TimeoutError) or error.errno == errno.ETIMEDOUT:
        return "unknown", "timed_out"
    return "unknown", "other"


def run_probe(probe: Probe) -> ProbeRow:
    outcome: Outcome = "unknown"
    category: ErrnoCategory = "none"
    family = socket.AF_INET if probe.family == "v4" else socket.AF_INET6
    if probe.kind == "socket_check" and (
        probe.case not in {"v6-socket-tcp", "v6-socket-udp"}
        or probe.family != "v6"
        or probe.port != 0
        or probe.expected != "deny"
    ):
        raise WorkerRejected("socket_check_invalid")
    kind = (
        socket.SOCK_STREAM
        if probe.kind == "tcp" or probe.case == "v6-socket-tcp"
        else socket.SOCK_DGRAM
    )
    address = ("127.0.0.1" if probe.family == "v4" else "::1", probe.port)
    try:
        if probe.kind == "socket_check":
            # Only a failure of construction proves creation denial. In
            # particular an error while closing an existing socket cannot pass.
            channel = socket.socket(family, kind)
            try:
                channel.close()
                outcome = "allowed"
            except OSError:
                outcome, category = "unknown", "other"
        else:
            with socket.socket(family, kind) as channel:
                channel.settimeout(0.5)
                channel.connect(address)
                # 固定一个字节,不构造DNS请求/域名,也不调用resolver。
                if probe.kind == "udp" and channel.send(b"P") != 1:
                    raise WorkerRejected("synthetic_send_incomplete")
                outcome = "allowed" if channel.recv(2) == b"OK" else "unknown"
    except OSError as error:
        if probe.kind == "socket_check" and error.errno in {
            errno.EAFNOSUPPORT,
            errno.EPROTONOSUPPORT,
        }:
            outcome, category = "denied", "address_family_unavailable"
        else:
            outcome, category = classify_error(error)
            if probe.kind == "socket_check" and category == "admin_unreachable":
                # Network reachability errors do not establish creation denial.
                outcome, category = "unknown", "other"
    return {
        "case": probe.case,
        "kind": probe.kind,
        "family": probe.family,
        "port": probe.port,
        "expected": probe.expected,
        "outcome": outcome,
        "errno_category": category,
    }


def run_phase(
    plan: Plan,
    phase: Phase,
    *,
    perform: Callable[[Probe], ProbeRow] = run_probe,
) -> tuple[list[ProbeRow], bool]:
    rows = []
    for probe in probes(plan, phase):
        row = perform(probe)
        rows.append(row)
        expected = "allowed" if probe.expected == "allow" else "denied"
        if row["outcome"] != expected:
            return rows, False
    return rows, True


def publish(path: Path, data: dict[str, object]) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=".metadata-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as output:
            json.dump(data, output, sort_keys=True, separators=(",", ":"))
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.link(temporary, path, follow_symlinks=False)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        os.unlink(temporary)


def reserve_started(path: Path, run_id: str) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as output:
        json.dump({"run_id": run_id, "result": "reserved_unknown"}, output)
        output.flush()
        os.fsync(output.fileno())


def decode_gate(raw: bytes, run_id: str, phase: Phase) -> None:
    if phase not in ("a", "b"):
        raise WorkerRejected("phase_invalid")
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeError):
        raise WorkerRejected("gate_invalid") from None
    expected = {"run_id": run_id, "phase": phase, "sequence": 1 if phase == "a" else 2}
    if data != expected or type(data.get("sequence")) is not int:
        raise WorkerRejected("gate_invalid")


def read_gate(path: Path, run_id: str, phase: Phase) -> None:
    before = path.lstat()
    if before.st_nlink == 2:
        raise FileNotFoundError
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_uid != 0
        or stat.S_IMODE(before.st_mode) & 0o022
        or before.st_nlink != 1
    ):
        raise WorkerRejected("gate_metadata_invalid")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        after = os.fstat(descriptor)
        if (before.st_dev, before.st_ino, before.st_size) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
        ) or before.st_size > 1024:
            raise WorkerRejected("gate_metadata_invalid")
        decode_gate(os.read(descriptor, 1025), run_id, phase)
    finally:
        os.close(descriptor)


def wait_gate(plan: Plan, phase: Phase, *, deadline: float) -> None:
    path = plan.runtime_root / f"go-{phase}.json"
    while time.monotonic() < deadline:
        try:
            read_gate(path, plan.run_id, phase)
            return
        except FileNotFoundError:
            time.sleep(0.05)
    raise WorkerRejected("gate_timeout")


def check_directories(plan: Plan) -> Path:
    root = plan.runtime_root
    own = root / "worker"
    for path, owner, permissions in ((root, 0, 0o755), (own, plan.uid, 0o700)):
        info = path.lstat()
        if (
            not stat.S_ISDIR(info.st_mode)
            or info.st_uid != owner
            or stat.S_IMODE(info.st_mode) != permissions
        ):
            raise WorkerRejected("runtime_metadata_invalid")
    return own


def _runtime_ready_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise WorkerRejected("runtime_ready_invalid")
        value[key] = item
    return value


def read_runtime_ready(path: Path, run_id: str) -> None:
    """Read only a fully published root-owned completion marker."""
    before = path.lstat()
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_uid != 0
        or stat.S_IMODE(before.st_mode) != 0o644
        or before.st_nlink not in {1, 2}
        or before.st_size > 1024
    ):
        raise WorkerRejected("runtime_ready_metadata_invalid")
    if before.st_nlink == 2:
        raise FileNotFoundError("runtime_ready_publishing")
    descriptor = -1
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        after = os.fstat(descriptor)
        if (
            not stat.S_ISREG(after.st_mode)
            or after.st_uid != 0
            or stat.S_IMODE(after.st_mode) != 0o644
            or after.st_nlink != 1
            or (before.st_dev, before.st_ino, before.st_size)
            != (after.st_dev, after.st_ino, after.st_size)
        ):
            raise WorkerRejected("runtime_ready_metadata_invalid")
        raw = bytearray()
        while len(raw) <= 1024:
            chunk = os.read(descriptor, 1025 - len(raw))
            if not chunk:
                break
            raw.extend(chunk)
        if len(raw) > 1024:
            raise WorkerRejected("runtime_ready_metadata_invalid")
        try:
            value = json.loads(raw, object_pairs_hook=_runtime_ready_pairs)
        except (ValueError, UnicodeError):
            raise WorkerRejected("runtime_ready_invalid") from None
        if value != {"run_id": run_id, "state": "runtime_ready"}:
            raise WorkerRejected("runtime_ready_invalid")
    except FileNotFoundError:
        raise
    except OSError:
        raise WorkerRejected("runtime_ready_metadata_invalid") from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def wait_directories(plan: Plan, *, deadline: float) -> Path:
    # Directory creation/chown has observable intermediate states. Only the
    # immutable root marker declares them complete; never inspect worker data
    # before it, or retry an invalid final state after it.
    while time.monotonic() < deadline:
        try:
            info = plan.runtime_root.lstat()
        except FileNotFoundError:
            time.sleep(0.05)
            continue
        if (
            not stat.S_ISDIR(info.st_mode)
            or info.st_uid != 0
            or stat.S_IMODE(info.st_mode) not in {0o700, 0o755}
        ):
            raise WorkerRejected("runtime_metadata_invalid")
        if stat.S_IMODE(info.st_mode) == 0o700:
            time.sleep(0.05)
            continue
        try:
            read_runtime_ready(plan.runtime_root / "runtime-ready.json", plan.run_id)
        except FileNotFoundError:
            time.sleep(0.05)
            continue
        try:
            return check_directories(plan)
        except OSError:
            raise WorkerRejected("runtime_metadata_invalid") from None
    raise WorkerRejected("runtime_timeout")


def _load_local(name: str, filename: str) -> ModuleType:
    path = Path(__file__).resolve().parent / filename
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise WorkerRejected("file_probe_module_unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_FILE_CHILD = r"""
import json, os, sys
p = json.loads(sys.argv[1])
r = {}
for label, key in [('install_read','marker'), ('business_read','business'),
                   ('publisher_read','publisher'), ('credentials_read','credentials')]:
    try:
        with open(p[key], 'rb') as f:
            f.read(1)
        r[label] = True
    except PermissionError:
        r[label] = False
try:
    with open(p['marker'], 'ab') as f:
        f.write(b'S')
    r['install_write'] = True
except PermissionError:
    r['install_write'] = False
r['cwd_created'] = None
try:
    fd = os.open(p['cwd_target'], os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
    st = os.fstat(fd)
    r['cwd_created'] = [st.st_dev, st.st_ino]
    os.write(fd, b'S'); os.close(fd)
    r['cwd_write'] = True
except PermissionError:
    r['cwd_write'] = False
with open(p['transient'], 'wb') as f:
    f.write(b'synthetic-session')
os.unlink(p['transient'])
with open(p['retained'], 'wb') as f:
    f.write(b'synthetic-state')
r['attempt_write'] = True
print(json.dumps(r, sort_keys=True))
"""


def _probe_cwd() -> Path:
    return Path("/srv/pi-cwd")


def run_file_probe(plan: Plan) -> dict[str, object]:
    # 仅由H1显式授权后执行;数据全部在本轮新建私有合成根。
    own = plan.runtime_root / "worker"
    fixtures = own / "files"
    fixtures.mkdir(mode=0o700, exist_ok=False)
    install = fixtures / "fake-install"
    install.mkdir(mode=0o700)
    executable = install / "synthetic-python"
    shutil.copyfile(Path(sys.executable).resolve(), executable)
    executable.chmod(0o500)
    marker = install / "marker"
    marker.write_bytes(b"synthetic")
    private = {}
    for key in ("business", "publisher", "credentials"):
        path = fixtures / f"fake-{key}"
        path.write_bytes(b"synthetic")
        private[key] = str(path)
    attempt = fixtures / "attempt"
    attempt.mkdir(mode=0o700)
    agent = attempt / "agent"
    agent.mkdir(mode=0o700)
    cwd = _probe_cwd()
    cwd_target = cwd / f"issue167-{plan.run_id}-denied"
    try:
        cwd_target.lstat()
    except FileNotFoundError:
        pass
    else:
        raise WorkerRejected("file_probe_cwd_collision")
    paths = {
        **private,
        "marker": str(marker),
        "cwd_target": str(cwd_target),
        "transient": str(agent / "transient"),
        "retained": str(agent / "retained"),
    }
    _load_local("paper_radar.pi_execution.errors", "production_errors.py")
    isolation = _load_local("issue167_production_isolation", "production_isolation.py")
    observation = _load_local("issue167_file_observation", "issue167_observation.py")
    boundary = isolation.IsolationBoundary(install, cwd, attempt, None)
    # 私有合成Python stdlib读取例外,不扩展生产Node白名单或策略身份。
    boundary._runtime = (*boundary._runtime, Path(sys.base_prefix) / "lib")
    with observation.FileObserver(attempt) as watcher:
        watcher.launch_started()
        child = subprocess.run(
            [
                str(executable),
                "-I",
                "-S",
                "-B",
                "-c",
                _FILE_CHILD,
                json.dumps(paths, sort_keys=True),
            ],
            env={},
            cwd=cwd,
            capture_output=True,
            timeout=5,
            check=False,
            preexec_fn=boundary,
        )
        watcher.descendants_reaped()
        decoded = None
        if child.returncode == 0 and len(child.stdout) <= 2048:
            with suppress(ValueError, UnicodeError):
                decoded = json.loads(child.stdout)
        # 若负例意外获准,仅能按child回传dev/inode精确清理自己创建的cwd标记。
        if type(decoded) is dict and decoded.get("cwd_created") is not None:
            identity = decoded["cwd_created"]
            current = cwd_target.lstat()
            if (
                type(identity) is not list
                or len(identity) != 2
                or any(type(value) is not int for value in identity)
                or identity != [current.st_dev, current.st_ino]
                or current.st_uid != plan.uid
                or not stat.S_ISREG(current.st_mode)
            ):
                raise WorkerRejected("file_probe_cwd_cleanup_unknown")
            cwd_target.unlink()
        watcher.snapshot_terminal()
        shutil.rmtree(attempt)
        receipt = watcher.receipt()
    checks = {
        "allow_install_read": ("install_read", True),
        "allow_attempt_write": ("attempt_write", True),
        "deny_install_write": ("install_write", False),
        "deny_cwd_write": ("cwd_write", False),
        "deny_business_read": ("business_read", False),
        "deny_publisher_read": ("publisher_read", False),
        "deny_credentials_read": ("credentials_read", False),
    }
    result: dict[str, object] = {
        key: type(decoded) is dict and decoded.get(field) is expected
        for key, (field, expected) in checks.items()
    }
    result.update(
        {
            "history": receipt.history,
            "terminal_regular_files": receipt.terminal_regular_files,
            "directory_deleted": receipt.directory_deleted,
            "coverage_complete": not receipt.reasons,
        }
    )
    passed = (
        all(result[key] is True for key in checks)
        and receipt.history == "observed_mutation"
        and receipt.terminal_regular_files == 1
        and receipt.directory_deleted
        and not receipt.reasons
    )
    result["result"] = "observed_expected" if passed else "unknown"
    return result


def _read_process_metadata(path: Path) -> str:
    with path.open("rb") as source:
        raw = source.read(16385)
    if len(raw) > 16384:
        raise WorkerRejected("process_metadata_invalid")
    try:
        return raw.decode("ascii")
    except UnicodeError:
        raise WorkerRejected("process_metadata_invalid") from None


def process_metadata(plan: Plan) -> dict[str, object]:
    status = _read_process_metadata(Path("/proc/self/status"))
    selected = {}
    for line in status.splitlines():
        key, separator, value = line.partition(":")
        if separator and key in {"NoNewPrivs", "CapEff"}:
            if key in selected:
                raise WorkerRejected("process_metadata_invalid")
            selected[key] = value.strip()
    caps = selected.get("CapEff", "")
    caps_zero = (
        len(caps) == 16
        and all(c in "0123456789abcdefABCDEF" for c in caps)
        and int(caps, 16) == 0
    )
    groups = _read_process_metadata(Path("/proc/self/cgroup")).splitlines()
    return {
        "core_limits": list(resource.getrlimit(resource.RLIMIT_CORE)),
        "no_new_privs": selected.get("NoNewPrivs") == "1",
        "cap_eff_zero": caps_zero,
        "cgroup_matches": groups == [f"0::{plan.cgroup}"],
    }


def execute_worker(plan: Plan) -> None:
    if os.getuid() != plan.uid or os.getuid() == 0 or os.getgid() != plan.gid:
        raise WorkerRejected("worker_identity_invalid")
    own = wait_directories(plan, deadline=time.monotonic() + 5)
    # 必须先排他预占再做任何子进程/网络动作,失败或中断保留状态。
    reserve_started(own / "started.json", plan.run_id)
    if resource.getrlimit(resource.RLIMIT_CORE) != (0, 0):
        raise WorkerRejected("core_limit_invalid")
    metadata = process_metadata(plan)
    if metadata != {
        "core_limits": [0, 0],
        "no_new_privs": True,
        "cap_eff_zero": True,
        "cgroup_matches": True,
    }:
        raise WorkerRejected("process_metadata_invalid")
    file_probe = run_file_probe(plan)
    if file_probe["result"] != "observed_expected":
        raise WorkerRejected("file_probe_unknown")
    publish(
        own / "ready.json",
        {
            "run_id": plan.run_id,
            "pid": os.getpid(),
            "uid": os.getuid(),
            "file_probe": file_probe,
            **metadata,
        },
    )
    deadline = time.monotonic() + plan.timeout_s - 10
    for phase in ("a", "b"):
        wait_gate(plan, phase, deadline=deadline)
        rows, complete = run_phase(plan, phase)
        publish(
            own / f"{phase}-done.json",
            {
                "run_id": plan.run_id,
                "phase": phase,
                "cases": rows,
            },
        )
        if not complete:
            raise WorkerRejected("phase_observation_unknown")
    # 故意跨session但留在同unit cgroup,供guardian独立拒绝阶段切换并stop。
    child = subprocess.Popen(
        [sys.executable, "-I", "-S", "-B", "-c", "import time; time.sleep(60)"],
        env={},
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        publish(
            own / "leftover-ready.json",
            {
                "run_id": plan.run_id,
                "controller_pid": os.getpid(),
                "child_pid": child.pid,
            },
        )
        while time.monotonic() < deadline:
            if child.poll() is not None:
                raise WorkerRejected("leftover_exited_before_guard")
            time.sleep(0.05)
        raise WorkerRejected("guardian_stop_missing")
    finally:
        if child.poll() is None:
            child.terminate()
        child.wait(timeout=2)


def peer_endpoints(plan: Plan) -> tuple[tuple[socket.AddressFamily, str], ...]:
    if plan.network_mode == "ipv4_only":
        return ((socket.AF_INET, "127.0.0.1"),)
    return ((socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1"))


def execute_peer(plan: Plan) -> None:
    if os.getuid() != plan.uid or os.getuid() == 0 or os.getgid() != plan.gid:
        raise WorkerRejected("peer_identity_invalid")
    sockets = []
    deadline = time.monotonic() + plan.timeout_s
    accepted = 0
    try:
        with selectors.DefaultSelector() as ready:
            for family, address in peer_endpoints(plan):
                for port in (plan.port_a, plan.port_b):
                    channel = socket.socket(family, socket.SOCK_STREAM)
                    sockets.append(channel)
                    if family == socket.AF_INET6:
                        channel.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
                    channel.bind((address, port))
                    channel.listen(8)
                    channel.setblocking(False)
                    ready.register(channel, selectors.EVENT_READ)
            sys.stdout.buffer.write(b"READY\n")
            sys.stdout.buffer.flush()
            maximum = 10 if plan.network_mode == "ipv4_only" else 20
            while time.monotonic() < deadline and accepted < maximum:
                for key, _mask in ready.select(
                    min(0.2, max(0, deadline - time.monotonic()))
                ):
                    listener = key.fileobj
                    if not isinstance(listener, socket.socket):
                        raise WorkerRejected("peer_listener_invalid")
                    with listener.accept()[0] as client:
                        client.settimeout(0.5)
                        # 固定响应;不读任何客户端内容,不存完整流。
                        client.sendall(b"OK")
                    accepted += 1
    finally:
        for channel in sockets:
            channel.close()


def load_worker_plan(path: Path) -> Plan:
    if os.geteuid() == 0:
        raise WorkerRejected("nonroot_worker_required")
    if not __package__:
        # H1安装器须先验证此目录root-owned且不可由普通用户写入。
        sys.path.insert(0, str(Path(__file__).resolve().parent))
    module_name = "scripts.issue167_h1_phase" if __package__ else "issue167_h1_phase"
    module = importlib.import_module(module_name)
    return cast("Plan", module.load_plan(path))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="待H1授权的无凭据本地合成worker/peer")
    parser.add_argument("--plan", type=Path, required=True)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--worker", action="store_true")
    modes.add_argument("--peer", action="store_true")
    arguments = parser.parse_args()
    try:
        selected_plan = load_worker_plan(arguments.plan)
        if arguments.peer:
            execute_peer(selected_plan)
        else:
            execute_worker(selected_plan)
    except Exception:
        # 元数据文件缺失/不完整由guardian判unknown,不导出外部异常原文。
        raise SystemExit(1) from None
