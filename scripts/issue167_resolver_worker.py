"""No-network H1 worker; importing this module never runs a case.

Only the installed, root-protected entry is eligible for the owner-run service.
Ordinary tests exercise isolated seams with explicitly synthetic provenance.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import resource
import selectors
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from contextlib import suppress
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from scripts.issue167_resolver_case import Case


class WorkerRejected(ValueError):
    """Closed metadata reason only."""


def require_time(deadline: float) -> None:
    if time.monotonic() >= deadline:
        raise WorkerRejected("worker_timeout")


def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in items:
        if key in value:
            raise WorkerRejected("metadata_unknown")
        value[key] = item
    return value


def read_json(path: Path, *, owner: int, limit: int = 16384) -> object:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    with os.fdopen(fd, "rb") as source:
        info = os.fstat(source.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != owner
            or info.st_mode & 0o022
        ):
            raise WorkerRejected("metadata_unknown")
        if info.st_nlink == 2:
            raise FileNotFoundError("metadata_publishing")
        if info.st_nlink != 1 or info.st_size > limit:
            raise WorkerRejected("metadata_unknown")
        raw = source.read(limit + 1)
    try:
        if len(raw) > limit:
            raise ValueError
        return json.loads(raw, object_pairs_hook=pairs)
    except (ValueError, UnicodeError, RecursionError):
        raise WorkerRejected("metadata_unknown") from None


def publish(path: Path, value: object) -> None:
    fd, temporary_name = tempfile.mkstemp(prefix=".metadata-", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w") as output:
            os.fchmod(output.fileno(), 0o600)
            json.dump(value, output, sort_keys=True, separators=(",", ":"))
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.link(temporary, path, follow_symlinks=False)
    finally:
        temporary.unlink(missing_ok=True)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def reserve(path: Path, run_id: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as output:
        os.fchmod(output.fileno(), 0o600)
        json.dump({"run_id": run_id, "state": "reserved_unknown"}, output)
        output.flush()
        os.fsync(output.fileno())


def wait_gate(path: Path, run_id: str, sequence: int, deadline: float) -> None:
    while time.monotonic() < deadline:
        try:
            value = read_json(path, owner=0, limit=1024)
        except FileNotFoundError:
            time.sleep(0.02)
            continue
        if (
            type(value) is not dict
            or set(value) != {"run_id", "sequence"}
            or value["run_id"] != run_id
            or type(value["sequence"]) is not int
            or value["sequence"] != sequence
        ):
            raise WorkerRejected("gate_unknown")
        require_time(deadline)
        return
    raise WorkerRejected("gate_timeout")


def _unescape_mount(value: str) -> str:
    return re.sub(
        r"\\(040|011|012|134)", lambda match: chr(int(match.group(1), 8)), value
    )


def resolver_metadata(expected_sha: str) -> bool:
    path = Path("/etc/resolv.conf")
    with path.open("rb") as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > 4096:
            raise WorkerRejected("resolver_unknown")
        raw = source.read(4097)
    if len(raw) > 4096 or hashlib.sha256(raw).hexdigest() != expected_sha:
        raise WorkerRejected("resolver_unknown")
    target = str(path.resolve(strict=True))
    with Path("/proc/self/mountinfo").open() as source:
        mountinfo = source.read(1024 * 1024 + 1)
    if len(mountinfo) > 1024 * 1024:
        raise WorkerRejected("resolver_mount_unknown")
    return any(
        len(fields := line.split()) >= 7
        and _unescape_mount(fields[4]) in {str(path), target}
        and "ro" in fields[5].split(",")
        for line in mountinfo.splitlines()
    )


def own_metadata(case: Case) -> dict[str, object]:
    with Path("/proc/self/status").open("rb") as source:
        raw = source.read(16385)
    if len(raw) > 16384:
        raise WorkerRejected("worker_metadata_unknown")
    selected = {}
    for line in raw.decode("ascii").splitlines():
        key, _, value = line.partition(":")
        if key in {"NoNewPrivs", "CapEff"}:
            if key in selected:
                raise WorkerRejected("worker_metadata_unknown")
            selected[key] = value.strip()
    with Path("/proc/self/cgroup").open("rb") as source:
        group = source.read(16385)
    plan = case.base_plan()
    if not resolver_metadata(case.resolver_sha256):
        raise WorkerRejected("resolver_mount_unknown")
    result: dict[str, object] = {
        "run_id": case.run_id,
        "pid": os.getpid(),
        "uid": os.getuid(),
        "core_limits": list(resource.getrlimit(resource.RLIMIT_CORE)),
        "no_new_privs": selected.get("NoNewPrivs") == "1",
        "cap_eff_zero": selected.get("CapEff") == "0000000000000000",
        "cgroup_matches": group == f"0::{plan.cgroup}\n".encode(),
        "resolver_sha256": case.resolver_sha256,
        "mount_namespace": os.readlink("/proc/self/ns/mnt"),
        "pid_namespace": os.readlink("/proc/self/ns/pid"),
    }
    from scripts.issue167_resolver_case import validate_ready

    validate_ready(case, result)
    return result


def load_isolation(root: Path) -> ModuleType:
    def load(name: str, path: Path) -> ModuleType:
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise WorkerRejected("isolation_source_unknown")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module

    load("paper_radar.pi_execution.errors", root / "production_errors.py")
    return load("issue167_resolver_isolation", root / "production_isolation.py")


def child_argv(
    root: Path, role: str, fd: int, cgroup: str, resolver_sha: str, tree: Path
) -> list[str]:
    if role not in {"auth", "model"}:
        raise WorkerRejected("child_role_unknown")
    return [
        str(root / "synthetic-python"),
        "-I",
        "-S",
        "-B",
        str(root / "issue167_resolver_child.py"),
        "--role",
        role,
        "--fd",
        str(fd),
        "--cgroup",
        cgroup,
        "--resolver-sha",
        resolver_sha,
        "--tree",
        str(tree),
    ]


def _line(channel: subprocess.Popen[bytes], deadline: float) -> object:
    assert channel.stdout is not None
    raw = bytearray()
    with selectors.DefaultSelector() as poll:
        poll.register(channel.stdout, selectors.EVENT_READ)
        while time.monotonic() < deadline:
            for key, _mask in poll.select(
                min(0.05, max(0, deadline - time.monotonic()))
            ):
                part = os.read(key.fd, 1)
                if not part:
                    raise WorkerRejected("child_output_unknown")
                raw.extend(part)
                if len(raw) > 2048:
                    raise WorkerRejected("child_output_unknown")
                if part == b"\n":
                    try:
                        return json.loads(raw, object_pairs_hook=pairs)
                    except (ValueError, UnicodeError):
                        raise WorkerRejected("child_output_unknown") from None
    raise WorkerRejected("child_timeout")


def _stop(child: subprocess.Popen[bytes]) -> None:
    if child.poll() is None:
        with suppress(ProcessLookupError):
            os.killpg(child.pid, signal.SIGTERM)
        try:
            child.wait(timeout=1)
        except subprocess.TimeoutExpired:
            with suppress(ProcessLookupError):
                os.killpg(child.pid, signal.SIGKILL)
            child.wait(timeout=1)
    for stream in (child.stdin, child.stdout):
        if stream is not None:
            stream.close()


def _exclusive(path: Path) -> bool:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        return True
    finally:
        os.close(fd)


def _child_meta(value: object) -> dict[str, bool]:
    required = {
        "fd_inherited",
        "core_zero",
        "cgroup_matches",
        "resolver_matches",
        "no_new_privs",
        "separate_session",
    }
    if (
        type(value) is not dict
        or not required <= set(value)
        or not set(value) <= required | {"marker_received"}
        or any(type(v) is not bool for v in value.values())
        or any(value[k] is not True for k in required)
    ):
        raise WorkerRejected("child_metadata_unknown")
    return cast(dict[str, bool], value)


def run_chain(
    root: Path,
    tree: Path,
    lock: Path,
    cgroup: str,
    resolver_sha: str,
    *,
    deadline: float,
    cwd: Path = Path("/srv/pi-cwd"),
) -> dict[str, bool]:
    """Run exactly one fixed auth and model Python peer, without network code."""
    require_time(deadline)
    isolation = load_isolation(root)
    fd = os.open(lock, os.O_RDONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    child: subprocess.Popen[bytes] | None = None
    try:
        fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        os.lseek(fd, 17, os.SEEK_SET)
        require_time(deadline)
        auth = subprocess.Popen(
            child_argv(root, "auth", fd, cgroup, resolver_sha, tree),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env={},
            cwd=cwd,
            start_new_session=True,
            pass_fds=(fd,),
            preexec_fn=isolation.disable_core_dumps,
        )
        child = auth
        decoded = _line(auth, min(deadline, time.monotonic() + 5))
        if auth.wait(timeout=max(0.01, min(5, deadline - time.monotonic()))) != 0:
            raise WorkerRejected("synthetic_auth_unknown")
        if type(decoded) is not dict or set(decoded) != {"marker", "metadata"}:
            raise WorkerRejected("synthetic_auth_unknown")
        marker = decoded["marker"]
        if (
            type(marker) is not str
            or marker != "issue167-public-nonsecret-resolver-fixture"
        ):
            raise WorkerRejected("synthetic_auth_unknown")
        auth_meta = _child_meta(decoded["metadata"])
        _stop(auth)
        child = None
        boundary = isolation.IsolationBoundary(root, cwd, tree, None)
        # This is only the synthetic Python peer, not a widened Node policy.
        boundary._runtime = (
            *boundary._runtime,
            Path(sys.base_prefix)
            / "lib"
            / f"python{sys.version_info.major}.{sys.version_info.minor}",
        )
        require_time(deadline)
        model = subprocess.Popen(
            child_argv(root, "model", fd, cgroup, resolver_sha, tree),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env={"OPENAI_API_KEY": marker},
            cwd=cwd,
            start_new_session=True,
            pass_fds=(fd,),
            preexec_fn=boundary,
        )
        marker = ""
        decoded = None
        child = model
        ready = _line(model, min(deadline, time.monotonic() + 5))
        if (
            type(ready) is not dict
            or set(ready) != {"stage", "metadata"}
            or ready["stage"] != "ready"
        ):
            raise WorkerRejected("synthetic_model_unknown")
        model_meta = _child_meta(ready["metadata"])
        if (
            model_meta.get("marker_received") is not True
            or os.lseek(fd, 0, os.SEEK_CUR) != 23
        ):
            raise WorkerRejected("ofd_or_marker_unknown")
        os.close(fd)
        fd = -1
        if _exclusive(lock):
            raise WorkerRejected("ofd_lifetime_unknown")
        require_time(deadline)
        assert model.stdin is not None
        model.stdin.write(b"GO\n")
        model.stdin.flush()
        model.stdin.close()
        done = _line(model, min(deadline, time.monotonic() + 5))
        if done != {"stage": "done", "mutation_complete": True}:
            raise WorkerRejected("synthetic_model_unknown")
        if model.wait(timeout=max(0.01, min(5, deadline - time.monotonic()))) != 0:
            raise WorkerRejected("synthetic_model_unknown")
        _stop(model)
        child = None
        if not _exclusive(lock):
            raise WorkerRejected("ofd_release_unknown")
        return {
            "auth_marker_transferred": True,
            "model_marker_received": True,
            "auth_fd_inherited": auth_meta["fd_inherited"],
            "model_fd_inherited": model_meta["fd_inherited"],
            "shared_offset": True,
            "exclusive_denied_while_child_alive": True,
            "exclusive_allowed_after_exit": True,
            "child_core_zero": auth_meta["core_zero"] and model_meta["core_zero"],
            "child_cgroup_matches": auth_meta["cgroup_matches"]
            and model_meta["cgroup_matches"],
            "child_resolver_matches": auth_meta["resolver_matches"]
            and model_meta["resolver_matches"],
            "child_no_new_privs": auth_meta["no_new_privs"]
            and model_meta["no_new_privs"],
            "separate_session": auth_meta["separate_session"]
            and model_meta["separate_session"],
        }
    finally:
        if child is not None:
            _stop(child)
        if fd >= 0:
            os.close(fd)


def run_worker(case: Case) -> dict[str, object]:
    from scripts.issue167_fork_observation import CgroupReader, ForkObservation
    from scripts.issue167_resolver_case import validate_result

    if (
        os.getuid() != case.uid
        or os.geteuid() != case.uid
        or os.getgid() != case.gid
        or os.getegid() != case.gid
    ):
        raise WorkerRejected("worker_identity_unknown")
    info = case.worker_root.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != case.uid
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise WorkerRejected("worker_directory_unknown")
    reserve(case.worker_root / "worker-started.json", case.run_id)
    deadline = time.monotonic() + case.worker_timeout_s
    result: dict[str, object] = {
        "run_id": case.run_id,
        "result": "unknown",
        "network_operations": 0,
        "node_pi": False,
        "auth_calls": 0,
        "model_calls": 0,
    }
    try:
        ready = own_metadata(case)
        tree = case.worker_root / "model"
        tree.mkdir(mode=0o700)
        (tree / "agent").mkdir(mode=0o700)
        (tree / "agent" / "settings.json").write_text('{"synthetic":true}\n')
        reader = CgroupReader(case.base_plan())
        with ForkObservation(tree, reader) as window:
            window.start()
            publish(case.worker_root / "ready.json", ready)
            wait_gate(case.runtime_root / "gate-run.json", case.run_id, 1, deadline)
            chain = run_chain(
                case.install_root,
                tree,
                case.worker_root / "protection.lock",
                case.base_plan().cgroup,
                case.resolver_sha256,
                deadline=deadline,
            )
            require_time(deadline)
            window.seal_terminal()
            shutil.rmtree(tree)
            window.check_deleted()
            receipt = window.receipt()
            require_time(deadline)
        result = {
            **ready,
            "result": "observed_expected",
            "window": receipt,
            "synthetic_chain": chain,
            "network_operations": 0,
            "node_pi": False,
            "auth_calls": 0,
            "model_calls": 0,
            "synthetic_auth_execs": 1,
            "synthetic_model_execs": 1,
        }
        validate_result(case, result)
    except (Exception, KeyboardInterrupt):
        result = {
            "run_id": case.run_id,
            "result": "unknown",
            "failure_reason": "worker_observation_unknown",
            "network_operations": 0,
            "node_pi": False,
            "auth_calls": 0,
            "model_calls": 0,
        }
    publish(case.worker_root / "worker-result.json", result)
    if result["result"] == "observed_expected":
        wait_gate(case.runtime_root / "gate-exit.json", case.run_id, 2, deadline)
    return result


def installed_case_module(root: Path) -> ModuleType:
    """Verify root ownership and the first module bytes before sibling imports."""
    if (
        re.fullmatch(r"/home/paperradar-probes/issue167-[a-f0-9]{12}", str(root))
        is None
    ):
        raise WorkerRejected("installed_root_unknown")
    for item in (root, *root.parents):
        info = item.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise WorkerRejected("protected_root_required")
    manifest = read_json(root / "manifest.json", owner=0, limit=65536)
    if type(manifest) is not dict or type(manifest.get("members")) is not dict:
        raise WorkerRejected("manifest_unknown")
    path = root / "issue167_resolver_case.py"
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as source:
        info = os.fstat(source.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != 0
            or info.st_nlink != 1
            or info.st_mode & 0o022
        ):
            raise WorkerRejected("case_source_unknown")
        raw = source.read(65537)
    if len(raw) > 65536 or hashlib.sha256(raw).hexdigest() != manifest["members"].get(
        path.name
    ):
        raise WorkerRejected("case_source_unknown")
    module = ModuleType("issue167_resolver_case_verified")
    module.__file__ = str(path)
    sys.modules[module.__name__] = module
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


def main() -> int:
    parser = argparse.ArgumentParser(
        description="仅H1批准后运行的无网络合成service worker"
    )
    parser.parse_args()
    root = Path(__file__).absolute().parent
    try:
        module = installed_case_module(root)
        case, _tools, _sha = module.verify_installation(root)
        package = ModuleType("scripts")
        package.__path__ = [str(root)]
        sys.modules["scripts"] = package
        result = run_worker(case)
        return 0 if result["result"] == "observed_expected" else 1
    except (Exception, KeyboardInterrupt):
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
