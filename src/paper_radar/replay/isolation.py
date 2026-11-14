"""回放专用最小 Landlock 白名单与纯 seccomp;不载入 Pi 或 SDK。"""

import ctypes
import os
import platform
import resource
import sys
import sysconfig
from pathlib import Path

from paper_radar.docling_execution.sandbox import deny_network
from paper_radar.replay.contract import ReplayError

_LIBC = ctypes.CDLL(None, use_errno=True)


class _Ruleset(ctypes.Structure):
    _fields_ = [
        ("fs", ctypes.c_uint64),
        ("net", ctypes.c_uint64),
        ("scope", ctypes.c_uint64),
    ]


class _PathRule(ctypes.Structure):
    _pack_ = 1
    _layout_ = "ms"
    _fields_ = [("access", ctypes.c_uint64), ("fd", ctypes.c_int32)]


def _syscall(number: int, *args: object) -> int:
    result: int = _LIBC.syscall(number, *args)
    if result < 0:
        raise ReplayError("isolation_unavailable")
    return result


def runtime_paths() -> tuple[Path, ...]:
    """准确运行依赖,不授予 /usr、/home、/tmp、项目祖先或 /proc。"""
    candidates = (
        Path(sys.executable).resolve(),
        Path(sysconfig.get_path("purelib")),
        Path(sysconfig.get_path("platlib")),
        Path(sys.prefix) / "pyvenv.cfg",
        Path(sys.base_prefix)
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}",
        Path(__file__).resolve().parents[2],
        Path("/lib/x86_64-linux-gnu"),
        Path("/lib64"),
        Path("/etc/ld.so.cache"),
        Path("/usr/share/zoneinfo"),
        Path("/dev/null"),
    )
    return tuple(dict.fromkeys(path.resolve() for path in candidates if path.exists()))


class ReplayBoundary:
    def __init__(self, root: Path, dependencies: tuple[Path, ...]) -> None:
        self.root = root
        self.dependencies = dependencies

    def __call__(self) -> None:
        if platform.system() != "Linux" or platform.machine() != "x86_64":
            raise ReplayError("isolation_unavailable")
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        abi = _syscall(444, 0, 0, 1)
        if abi < 4:
            raise ReplayError("isolation_unavailable")
        handled = (1 << (16 if abi >= 5 else 15)) - 1
        attr = _Ruleset(handled, 3, 3 if abi >= 6 else 0)
        descriptor = _syscall(444, ctypes.byref(attr), 24 if abi >= 6 else 16, 0)
        try:
            paths = [
                (self.root, 8),
                (self.root / "restore-receipt.json", 4),
                (self.root / "contents", 12),
                (self.root / "views", handled),
            ]
            paths.extend((path, 13) for path in self.dependencies)
            for path, access in paths:
                fd = os.open(path, os.O_PATH | os.O_CLOEXEC)
                try:
                    if not path.is_dir():
                        access &= 1 | 2 | 4 | (1 << 14)
                    if path == Path("/dev/null"):
                        access |= 2
                    rule = _PathRule(access, fd)
                    _syscall(445, descriptor, 1, ctypes.byref(rule), 0)
                finally:
                    os.close(fd)
            if _LIBC.prctl(38, 1, 0, 0, 0) != 0:
                raise ReplayError("isolation_unavailable")
            _syscall(446, descriptor, 0)
        finally:
            os.close(descriptor)
        deny_network()
