"""Bounded self-owned synthetic IPC controls; import never performs a probe.

The real backend is for the separately approved worker, before authentication.
No external process, credential, environment, or network is an input. Ordinary
unit tests inject Operations and do not execute the process-access syscalls.
"""

from __future__ import annotations

import ctypes
import json
import math
import os
import platform
import resource
import selectors
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, cast

CATEGORIES = (
    "process_vm_readv",
    "process_vm_writev",
    "ptrace",
    "pidfd_getfd",
    "proc_mem",
    "proc_fd",
    "signal",
)
LIMITS = {
    "pair_entries": 7,
    "target_processes": 7,
    "peer_processes": 14,
    "peer_probes": 14,
    "ptrace_seize_per_peer": 1,
    "ptrace_interrupt_per_peer": 1,
    "ptrace_detach_per_peer": 2,
    "signal_usr1_per_peer": 1,
    "network_operations": 0,
    "node_pi": False,
    "credentials_read": False,
}
RECEIPT_FIELDS = {
    "scope",
    "result",
    "integrity",
    "counts_semantics",
    "pair_entries",
    "peer_operations_entered",
    "limits",
    "steps",
}
Clock = Callable[[], float]
BoundaryFactory = Callable[[Path, Path, Path], Callable[[], None]]

TARGET = r"""
import ctypes,json,os,resource,signal,sys,time
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
libc=ctypes.CDLL(None,use_errno=True)
if libc.prctl(38,1,0,0,0)!=0 or libc.prctl(0x59616d61,ctypes.c_ulong(-1),0,0,0)!=0:
    print('{"ready":false}',flush=True);raise SystemExit(1)
original=b'synthetic-memory-marker-A';written=b'synthetic-memory-marker-B'
buffer=ctypes.create_string_buffer(original)
received=False

def handler(_signum,_frame):
    global received
    received=True

signal.signal(signal.SIGUSR1,handler)
fd=os.open(sys.argv[1],os.O_RDONLY|os.O_NOFOLLOW)
print(json.dumps({'ready':True,'pid':os.getpid(),'address':ctypes.addressof(buffer),
                  'length':len(original),'fd':fd}),flush=True)
try:
    for line in sys.stdin.buffer:
        command=json.loads(line)
        if command=='quit':
            print('{"done":true}',flush=True);break
        if command=='reset':
            ctypes.memmove(ctypes.addressof(buffer),original,len(original));received=False
            print('{"reset":true}',flush=True)
        elif command=='state':
            print(json.dumps({'original':buffer.raw[:len(original)]==original,
                              'written':buffer.raw[:len(original)]==written,
                              'signal_received':received}),flush=True)
        elif command=='signal_state':
            end=time.monotonic()+0.2
            while not received and time.monotonic()<end:time.sleep(0.001)
            print(json.dumps({'signal_received':received}),flush=True)
        else:
            print('{"unknown":true}',flush=True)
finally:
    os.close(fd)
"""

PEER = r"""
import ctypes,errno,json,os,signal,sys,time
value=json.loads(sys.stdin.buffer.readline())
category=value['category'];pid=value['pid'];address=value['address'];length=value['length'];target_fd=value['fd'];deadline=value['deadline']
result='unknown';reason='other';verified=False
original=b'synthetic-memory-marker-A';written=b'synthetic-memory-marker-B';file_marker=b'synthetic-file-marker'
libc=ctypes.CDLL(None,use_errno=True)

def status(number):
    if number==-1:
        e=ctypes.get_errno()
        if e in (errno.EPERM,errno.EACCES):return ('denied','permission')
        reason='unsupported' if e in (errno.ENOSYS,errno.EINVAL) else 'other'
        return ('unknown',reason)
    return ('unknown','other')

try:
    if category in ('process_vm_readv','process_vm_writev'):
        class IOVec(ctypes.Structure):
            _fields_=[('base',ctypes.c_void_p),('length',ctypes.c_size_t)]
        call=getattr(libc,category)
        call.argtypes=[ctypes.c_int,ctypes.POINTER(IOVec),ctypes.c_ulong,ctypes.POINTER(IOVec),ctypes.c_ulong,ctypes.c_ulong]
        call.restype=ctypes.c_ssize_t
        source=written if category=='process_vm_writev' else length
        data=ctypes.create_string_buffer(source)
        local=IOVec(ctypes.addressof(data),length);remote=IOVec(address,length)
        count=call(pid,ctypes.byref(local),1,ctypes.byref(remote),1,0)
        if count==length and (category=='process_vm_writev' or data.raw==original):
            result='allowed';reason='none';verified=True
        else:result,reason=status(count)
    elif category=='ptrace':
        call=libc.ptrace;call.argtypes=[ctypes.c_uint,ctypes.c_int,ctypes.c_void_p,ctypes.c_void_p];call.restype=ctypes.c_long
        seized=detached=False
        try:
            count=call(0x4206,pid,None,None)
            if count==-1:result,reason=status(count)
            else:
                seized=True
                if call(0x4207,pid,None,None)==0:
                    stopped=False
                    while time.monotonic()<deadline:
                        got,wait_status=os.waitpid(pid,os.WNOHANG|os.WUNTRACED|0x40000000)
                        if got==pid:
                            stopped=os.WIFSTOPPED(wait_status);break
                        time.sleep(0.001)
                    if stopped and call(17,pid,None,None)==0:
                        detached=True;result='allowed';reason='none';verified=True
        finally:
            if seized and not detached:call(17,pid,None,None)
    elif category=='pidfd_getfd':
        if not hasattr(os,'pidfd_open'):
            reason='unsupported'
        else:
            descriptor=os.pidfd_open(pid,0)
            try:
                dup=libc.syscall(438,ctypes.c_int(descriptor),ctypes.c_int(target_fd),ctypes.c_uint(0))
                if dup==-1:result,reason=status(dup)
                else:
                    try:
                        verified=os.pread(dup,len(file_marker),0)==file_marker
                        if verified:result='allowed';reason='none'
                    finally:os.close(dup)
            finally:os.close(descriptor)
    elif category in ('proc_mem','proc_fd'):
        leaf='/mem' if category=='proc_mem' else '/fd/'+str(target_fd)
        path='/proc/'+str(pid)+leaf
        descriptor=os.open(path,os.O_RDONLY)
        try:
            expected=original if category=='proc_mem' else file_marker
            offset=address if category=='proc_mem' else 0
            verified=os.pread(descriptor,len(expected),offset)==expected
            if verified:result='allowed';reason='none'
        finally:os.close(descriptor)
    elif category=='signal':
        os.kill(pid, signal.SIGUSR1)
        result='allowed';reason='none';verified=True
except PermissionError:
    result='denied';reason='permission'
except (AttributeError,NotImplementedError):
    result='unknown';reason='unsupported'
except BaseException:
    result='unknown';reason='other'
if result=='denied':verified=True
print(json.dumps({'result':result,'errno_category':reason,'verified':verified}),flush=True)
"""


class IpcRejected(ValueError):
    """Only controlled reasons are returned to the caller."""


class PairOperations(Protocol):
    def probe(self, isolated: bool, deadline: float) -> dict[str, object]: ...
    def close(self, deadline: float) -> bool: ...


class Operations(Protocol):
    def open(self, category: str, deadline: float) -> PairOperations: ...


def remaining(deadline: float, clock: Clock) -> float:
    value = deadline - clock()
    if not math.isfinite(value) or value <= 0:
        raise IpcRejected("ipc_deadline_unknown")
    return value


def _pairs(items: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in items:
        if key in result:
            raise IpcRejected("ipc_metadata_unknown")
        result[key] = value
    return result


def parse_json(raw: bytes) -> dict[str, object]:
    try:
        if not raw or len(raw) > 4096 or raw.count(b"\n") > 1:
            raise ValueError
        value = json.loads(raw, object_pairs_hook=_pairs)
        if type(value) is not dict:
            raise ValueError
        return cast(dict[str, object], value)
    except (ValueError, UnicodeError, RecursionError):
        raise IpcRejected("ipc_metadata_unknown") from None


def validate_observation(value: object) -> dict[str, object]:
    if (
        type(value) is not dict
        or set(value) != {"result", "errno_category", "verified", "peer_reaped"}
        or value["result"] not in {"allowed", "denied", "unknown"}
        or value["errno_category"] not in {"none", "permission", "unsupported", "other"}
        or type(value["verified"]) is not bool
        or (value["result"] != "unknown" and value["verified"] is not True)
        or value["peer_reaped"] is not True
    ):
        raise IpcRejected("peer_metadata_unknown")
    return cast(dict[str, object], value)


def _flags_match(value: dict[str, object], expected: dict[str, bool]) -> bool:
    return set(value) == set(expected) and all(
        type(value[key]) is bool and value[key] is flag
        for key, flag in expected.items()
    )


def run_ipc_preflight(
    work_root: Path,
    deadline: float,
    *,
    operations: Operations | None = None,
    isolation_factory: BoundaryFactory | None = None,
    clock: Clock = time.monotonic,
) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    result: dict[str, object] = {
        "scope": "self_owned_synthetic_ipc_matrix",
        "result": "unknown",
        "integrity": "unknown",
        "counts_semantics": "entered_bounded_probe_not_syscall_or_process_success",
        "pair_entries": 0,
        "peer_operations_entered": 0,
        "limits": dict(LIMITS),
        "steps": rows,
    }
    active: PairOperations | None = None
    row: dict[str, object] | None = None
    reason: str | None = None
    try:
        remaining(deadline, clock)
        if operations is None:
            operations = KernelOperations(
                work_root, isolation_factory=isolation_factory, clock=clock
            )
        for sequence, category in enumerate(CATEGORIES, 1):
            remaining(deadline, clock)
            row = {
                "sequence": sequence,
                "category": category,
                "control": "unknown",
                "denial": "unknown",
                "control_errno_category": None,
                "denial_errno_category": None,
                "cleanup_complete": False,
            }
            rows.append(row)
            result["pair_entries"] = sequence
            active = operations.open(category, deadline)
            for isolated in (False, True):
                remaining(deadline, clock)
                result["peer_operations_entered"] = (
                    cast(int, result["peer_operations_entered"]) + 1
                )
                observation = validate_observation(
                    active.probe(isolated, min(deadline, clock() + 5))
                )
                remaining(deadline, clock)
                row[
                    "denial_errno_category" if isolated else "control_errno_category"
                ] = observation["errno_category"]
                if isolated:
                    if (
                        observation["result"] != "denied"
                        or observation["errno_category"] != "permission"
                    ):
                        raise IpcRejected("isolation_denial_unknown")
                    row["denial"] = "observed_permission_denial"
                else:
                    if (
                        observation["result"] != "allowed"
                        or observation["errno_category"] != "none"
                    ):
                        raise IpcRejected("positive_control_unknown")
                    row["control"] = "observed_allowed"
            complete = active.close(min(deadline, clock() + 5))
            active = None
            row["cleanup_complete"] = complete
            if complete is not True:
                raise IpcRejected("ipc_cleanup_unknown")
            remaining(deadline, clock)
        result.update(result="observed_expected", integrity="complete")
    except BaseException as error:
        allowed = {
            "ipc_deadline_unknown",
            "peer_metadata_unknown",
            "positive_control_unknown",
            "isolation_denial_unknown",
            "ipc_cleanup_unknown",
        }
        value = (
            error.args[0]
            if isinstance(error, IpcRejected) and len(error.args) == 1
            else None
        )
        reason = (
            value
            if isinstance(value, str) and value in allowed
            else "ipc_observation_unknown"
        )
    finally:
        if active is not None:
            try:
                complete = active.close(clock() + 5)
            except BaseException:
                complete = False
            if row is not None:
                row["cleanup_complete"] = complete is True
            if complete is not True:
                reason = "ipc_cleanup_unknown"
    if reason is not None:
        result.update(result="unknown", integrity="unknown", failure_reason=reason)
    return result


def _control() -> None:
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    if (
        resource.getrlimit(resource.RLIMIT_CORE) != (0, 0)
        or ctypes.CDLL(None).prctl(38, 1, 0, 0, 0) != 0
    ):
        raise IpcRejected("ipc_preexec_unknown")


def _default_boundary(install: Path, cwd: Path, attempt: Path) -> Callable[[], None]:
    from paper_radar.pi_execution.isolation import IsolationBoundary

    boundary = IsolationBoundary(install, cwd, attempt, None)
    # Fixture-only versioned stdlib read scope; product policy is unchanged.
    standard_library = (
        Path(sys.base_prefix)
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
    )
    boundary._runtime = (*boundary._runtime, standard_library)
    return boundary


def _stop(child: subprocess.Popen[bytes], deadline: float, clock: Clock) -> bool:
    try:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=remaining(deadline, clock))
        return child.returncode is not None
    except (OSError, subprocess.TimeoutExpired, IpcRejected):
        return False


def _line(
    child: subprocess.Popen[bytes], deadline: float, clock: Clock
) -> dict[str, object]:
    if child.stdout is None:
        raise IpcRejected("ipc_metadata_unknown")
    raw = bytearray()
    with selectors.DefaultSelector() as ready:
        ready.register(child.stdout, selectors.EVENT_READ)
        while not raw.endswith(b"\n"):
            if not ready.select(remaining(deadline, clock)):
                raise IpcRejected("ipc_deadline_unknown")
            part = os.read(child.stdout.fileno(), 4097 - len(raw))
            if not part:
                raise IpcRejected("ipc_metadata_unknown")
            raw.extend(part)
            if len(raw) > 4096:
                raise IpcRejected("ipc_metadata_unknown")
    remaining(deadline, clock)
    return parse_json(bytes(raw))


def _peer_json(
    child: subprocess.Popen[bytes], deadline: float, clock: Clock
) -> dict[str, object]:
    if child.stdout is None:
        raise IpcRejected("ipc_metadata_unknown")
    raw = bytearray()
    with selectors.DefaultSelector() as ready:
        ready.register(child.stdout, selectors.EVENT_READ)
        while True:
            if not ready.select(remaining(deadline, clock)):
                raise IpcRejected("ipc_deadline_unknown")
            part = os.read(child.stdout.fileno(), 4097 - len(raw))
            if not part:
                break
            raw.extend(part)
            if len(raw) > 4096:
                raise IpcRejected("ipc_metadata_unknown")
    remaining(deadline, clock)
    return parse_json(bytes(raw))


class KernelOperations:
    """The caller must authorize this backend; no instance is created on import."""

    def __init__(
        self,
        root: Path,
        *,
        isolation_factory: BoundaryFactory | None = None,
        clock: Clock = time.monotonic,
    ) -> None:
        if platform.system() != "Linux" or platform.machine() not in {
            "x86_64",
            "aarch64",
        }:
            raise IpcRejected("ipc_platform_unknown")
        if not root.is_absolute() or any(p.is_symlink() for p in (root, *root.parents)):
            raise IpcRejected("ipc_directory_unknown")
        root.mkdir(mode=0o700, exist_ok=False)
        self.root = root
        self.factory = isolation_factory or _default_boundary
        self.clock = clock

    def open(self, category: str, deadline: float) -> PairOperations:
        if category not in CATEGORIES:
            raise IpcRejected("ipc_category_unknown")
        return KernelPair(
            self.root / category, category, self.factory, deadline, self.clock
        )


class KernelPair:
    def __init__(
        self,
        root: Path,
        category: str,
        factory: BoundaryFactory,
        deadline: float,
        clock: Clock,
    ) -> None:
        self.category, self.clock, self.factory = category, clock, factory
        self.target: subprocess.Popen[bytes] | None = None
        self.root = root
        root.mkdir(mode=0o700, exist_ok=False)
        self.install, self.cwd, self.attempt = (
            root / name for name in ("install", "cwd", "attempt")
        )
        for p in (self.install, self.cwd, self.attempt):
            p.mkdir(mode=0o700)
        self.python = self.install / "synthetic-python"
        shutil.copyfile(Path(sys.executable).resolve(), self.python)
        self.python.chmod(0o700)
        marker = root / "target-file"
        marker.write_bytes(b"synthetic-file-marker")
        marker.chmod(0o600)
        try:
            self.target = subprocess.Popen(
                [sys.executable, "-I", "-S", "-B", "-c", TARGET, str(marker)],
                cwd=self.cwd,
                env={},
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                preexec_fn=_control,
            )
            ready = _line(self.target, min(deadline, clock() + 5), clock)
            if (
                set(ready) != {"ready", "pid", "address", "length", "fd"}
                or ready["ready"] is not True
                or ready["pid"] != self.target.pid
                or any(
                    type(ready[k]) is not int or cast(int, ready[k]) <= 0
                    for k in ("pid", "address", "length", "fd")
                )
                or ready["length"] != len(b"synthetic-memory-marker-A")
            ):
                raise IpcRejected("ipc_target_unknown")
            self.metadata = ready
        except BaseException:
            if self.target is not None:
                self.close(clock() + 5)
            raise

    def _command(self, command: str, deadline: float) -> dict[str, object]:
        if (
            self.target is None
            or self.target.stdin is None
            or self.target.poll() is not None
        ):
            raise IpcRejected("ipc_target_unknown")
        payload = json.dumps(command).encode() + b"\n"
        if os.write(self.target.stdin.fileno(), payload) != len(payload):
            raise IpcRejected("ipc_target_unknown")
        return _line(self.target, deadline, self.clock)

    def probe(self, isolated: bool, deadline: float) -> dict[str, object]:
        if self.target is None or self.target.poll() is not None:
            raise IpcRejected("ipc_target_unknown")
        if not _flags_match(self._command("reset", deadline), {"reset": True}):
            raise IpcRejected("ipc_target_unknown")
        payload = {k: self.metadata[k] for k in ("pid", "address", "length", "fd")}
        payload.update(category=self.category, deadline=deadline)
        child = subprocess.Popen(
            [str(self.python), "-I", "-S", "-B", "-c", PEER],
            cwd=self.cwd,
            env={},
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            preexec_fn=self.factory(self.install, self.cwd, self.attempt)
            if isolated
            else _control,
        )
        reaped = False
        try:
            assert child.stdin is not None
            data = json.dumps(payload).encode() + b"\n"
            if len(data) > 1024 or os.write(child.stdin.fileno(), data) != len(data):
                raise IpcRejected("ipc_metadata_unknown")
            child.stdin.close()
            value = _peer_json(child, deadline, self.clock)
            child.wait(timeout=remaining(deadline, self.clock))
            remaining(deadline, self.clock)
            reaped = child.returncode == 0
            if set(value) != {"result", "errno_category", "verified"} or not reaped:
                raise IpcRejected("ipc_metadata_unknown")
            if self.category == "process_vm_writev":
                state = self._command("state", deadline)
                expected = {
                    "original": isolated,
                    "written": not isolated,
                    "signal_received": False,
                }
                if not _flags_match(state, expected):
                    value.update(result="unknown", verified=False)
            elif self.category == "signal":
                state = self._command("signal_state", deadline)
                if not _flags_match(state, {"signal_received": not isolated}):
                    value.update(result="unknown", verified=False)
            return {**value, "peer_reaped": reaped}
        finally:
            if child.poll() is None and not _stop(child, self.clock() + 5, self.clock):
                raise IpcRejected("ipc_cleanup_unknown")
            if child.stdin is not None:
                child.stdin.close()
            if child.stdout is not None:
                child.stdout.close()

    def close(self, deadline: float) -> bool:
        if self.target is None:
            return True
        target = self.target
        try:
            if target.poll() is None:
                self._command("quit", deadline)
                if target.stdin is not None:
                    target.stdin.close()
                target.wait(timeout=remaining(deadline, self.clock))
            remaining(deadline, self.clock)
            return target.returncode == 0
        except (OSError, subprocess.TimeoutExpired, IpcRejected):
            _stop(target, self.clock() + 5, self.clock)
            return False
        finally:
            if target.stdin is not None:
                target.stdin.close()
            if target.stdout is not None:
                target.stdout.close()
            self.target = None
