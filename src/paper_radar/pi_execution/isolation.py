"""Linux Landlock 固定权限策略;只限 TCP 端口,不提供主机级出站保证。"""

import ctypes
import os
import platform
import resource
from pathlib import Path

from paper_radar.pi_execution.errors import ExecutionError

ISOLATION_POLICY_VERSION = "pi-landlock-v1"
# Linux UAPI: CREATE_RULESET=444, ADD_RULE=445, RESTRICT_SELF=446。
# 两个已登记的 syscall ABI 使用相同编号;其他平台失败关闭。
_LIBC = ctypes.CDLL(None, use_errno=True)
_READ = (1 << 2) | (1 << 3)
_EXECUTE = 1
_WRITE_FILE = 1 << 1
_TRUNCATE = 1 << 14
_RUNTIME_PATHS = (
    Path("/lib/x86_64-linux-gnu"),
    Path("/lib/aarch64-linux-gnu"),
    Path("/lib64"),
    Path("/etc/ld.so.cache"),
    Path("/etc/ssl"),
    Path("/etc/resolv.conf"),
    Path("/etc/hosts"),
    Path("/etc/nsswitch.conf"),
    Path("/dev/null"),
    Path("/dev/urandom"),
)
_RUNTIME_EXECUTABLES = frozenset(_RUNTIME_PATHS[:3])


class _Ruleset(ctypes.Structure):
    _fields_ = [
        ("fs", ctypes.c_uint64),
        ("net", ctypes.c_uint64),
        ("scope", ctypes.c_uint64),
    ]


class _PathRule(ctypes.Structure):
    # Linux UAPI packed struct, exactly 12 bytes (u64 access + s32 parent_fd).
    _pack_ = 1
    _layout_ = "ms"
    _fields_ = [("access", ctypes.c_uint64), ("fd", ctypes.c_int32)]


class _NetRule(ctypes.Structure):
    _fields_ = [("access", ctypes.c_uint64), ("port", ctypes.c_uint64)]


def _syscall(number: int, *args: object) -> int:
    result: int = _LIBC.syscall(number, *args)
    if result < 0:
        raise ExecutionError("isolation_unavailable")
    return result


def _abi() -> int:
    if platform.system() != "Linux" or platform.machine() not in {"x86_64", "aarch64"}:
        raise ExecutionError("isolation_unavailable")
    abi = _syscall(444, 0, 0, 1)
    if abi < 4:
        raise ExecutionError("isolation_unavailable")
    return abi


def _ruleset(abi: int) -> int:
    fs = (1 << (16 if abi >= 5 else 15)) - 1
    attr = _Ruleset(fs, 3, 3 if abi >= 6 else 0)
    return _syscall(444, ctypes.byref(attr), 24 if abi >= 6 else 16, 0)


def isolation_capability() -> int:
    """无进程、无文件创建的能力检查;不声称现场 Pi/TLS 可用。"""
    abi = _abi()
    descriptor = _ruleset(abi)
    os.close(descriptor)
    return abi


def disable_core_dumps() -> None:
    """仅在子进程 pre-exec 调用;软硬限额都为零,失败不得继续 exec。"""
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    if resource.getrlimit(resource.RLIMIT_CORE) != (0, 0):
        raise ExecutionError("isolation_unavailable")


class IsolationBoundary:
    """仅启动器构造的 pre-exec 边界;每个进程重新取得自身 /proc 视图。"""

    def __init__(
        self, install: Path, cwd: Path, attempt: Path, proxy_port: int | None
    ) -> None:
        self._install = install
        self._cwd = cwd
        self._attempt = attempt
        self._proxy_port = proxy_port
        self._runtime: tuple[Path, ...] = _RUNTIME_PATHS

    def __call__(self) -> None:
        disable_core_dumps()
        if (
            self._cwd.is_symlink()
            or not self._cwd.is_dir()
            or any(part.is_symlink() for part in self._cwd.parents)
            or any(self._cwd.iterdir())
        ):
            raise ExecutionError("cwd_invalid")
        abi = _abi()
        descriptor = _ruleset(abi)
        handled = (1 << (16 if abi >= 5 else 15)) - 1
        try:
            paths = [
                (self._install, _READ | _EXECUTE),
                (self._cwd, _READ),
                (self._attempt, handled),
                *(
                    (path, _READ | (_EXECUTE if path in _RUNTIME_EXECUTABLES else 0))
                    for path in self._runtime
                    if path.exists()
                ),
                (Path("/proc/self"), _READ),
            ]
            for path, access in paths:
                fd = os.open(path, os.O_PATH | os.O_CLOEXEC)
                try:
                    if not path.is_dir():
                        access &= _READ | _EXECUTE | _WRITE_FILE | _TRUNCATE
                        access &= ~(1 << 3)
                    if path == Path("/dev/null"):
                        access |= _WRITE_FILE
                    rule = _PathRule(access, fd)
                    _syscall(445, descriptor, 1, ctypes.byref(rule), 0)
                finally:
                    os.close(fd)
            for port in {443, self._proxy_port} - {None}:
                assert port is not None
                net = _NetRule(2, port)  # connect only; no TCP bind permission.
                _syscall(445, descriptor, 2, ctypes.byref(net), 0)
            if _LIBC.prctl(38, 1, 0, 0, 0) != 0:  # PR_SET_NO_NEW_PRIVS
                raise ExecutionError("isolation_unavailable")
            _syscall(446, descriptor, 0)
        finally:
            os.close(descriptor)
