"""开发环境的只读系统探测; 不安装、不创建探测文件。"""

from __future__ import annotations

import ctypes
import os
import platform
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Capacity:
    available_bytes: int
    available_inodes: int


@dataclass(frozen=True)
class Quota:
    limit_bytes: int
    used_bytes: int


class _Dqblk(ctypes.Structure):
    # Linux UAPI <linux/quota.h>, struct if_dqblk.
    _fields_ = [
        ("hard", ctypes.c_uint64),
        ("soft", ctypes.c_uint64),
        ("used", ctypes.c_uint64),
        ("inode_hard", ctypes.c_uint64),
        ("inode_soft", ctypes.c_uint64),
        ("inode_used", ctypes.c_uint64),
        ("block_time", ctypes.c_uint64),
        ("inode_time", ctypes.c_uint64),
        ("valid", ctypes.c_uint32),
    ]


def read_capacity(path: Path) -> Capacity:
    value = os.statvfs(path)
    return Capacity(value.f_bavail * value.f_frsize, value.f_favail)


def read_quota(path: Path) -> Quota | None:
    """Q_GETQUOTA; 未支持、无配额、无权限或缺少有效额度时均为未知。"""
    if sys.platform != "linux" or platform.machine() not in {
        "x86_64",
        "aarch64",
        "riscv64",
        "i386",
        "i686",
        "armv7l",
        "ppc64le",
        "s390x",
    }:
        return None
    # x32 ABI 使用 __X32_SYSCALL_BIT, 不能把 443 直接传给 syscall。
    if platform.machine() == "x86_64" and ctypes.sizeof(ctypes.c_void_p) != 8:
        return None
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        syscall = libc.syscall
        syscall.restype = ctypes.c_long
        quota = _Dqblk()
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            result = syscall(
                ctypes.c_long(443),  # SYS_quotactl_fd, Linux >= 5.14
                ctypes.c_int(descriptor),
                ctypes.c_uint(0x800007 << 8),  # QCMD(Q_GETQUOTA, USRQUOTA)
                ctypes.c_uint(os.getuid()),
                ctypes.byref(quota),
            )
        finally:
            os.close(descriptor)
        if result != 0 or quota.valid & 3 != 3:
            return None
        # 保守使用非零软/硬上限中的较小者, 不假设宽限期仍有余量。
        limits = [limit for limit in (quota.hard, quota.soft) if limit > 0]
        return Quota(min(limits) * 1024, quota.used) if limits else None
    except (OSError, AttributeError):
        return None


def git_isolated(path: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        timeout=10,
        check=False,
        env={
            **{
                key: value
                for key, value in os.environ.items()
                if not key.startswith("GIT_")
            },
            "LC_ALL": "C",
        },
    )
    if result.returncode == 0:
        return False
    if result.returncode == 128 and result.stderr.startswith(
        b"fatal: not a git repository"
    ):
        return True
    raise OSError("git_probe_failed")


def writable(path: Path) -> bool:
    return os.access(path, os.W_OK | os.X_OK, effective_ids=True)


def read_temporary_root() -> Path:
    """按 tempfile 候选顺序选择, 但只探测权限, 不创建测试文件。"""
    candidates = [os.environ.get(key) for key in ("TMPDIR", "TEMP", "TMP")]
    candidates.extend(("/tmp", "/var/tmp", "/usr/tmp", str(Path.cwd())))
    for candidate in candidates:
        if candidate:
            path = Path(candidate)
            if path.is_dir() and writable(path):
                return path.resolve(strict=True)
    raise OSError("temporary_unavailable")


@dataclass(frozen=True)
class Probes:
    capacity: Callable[[Path], Capacity] = read_capacity
    quota: Callable[[Path], Quota | None] = read_quota
    git_isolated: Callable[[Path], bool] = git_isolated
    writable: Callable[[Path], bool] = writable
