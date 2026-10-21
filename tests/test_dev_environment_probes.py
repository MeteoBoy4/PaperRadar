"""只读 OS 边界测试: 配额 ABI 与错误降级。"""

import ctypes
import errno
import platform
import struct
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from scripts.dev_environment_probes import Quota, read_quota


@pytest.mark.parametrize("error", [errno.ENOSYS, errno.ESRCH, errno.EPERM])
def test_unreadable_quota_is_unknown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error: int,
) -> None:
    def syscall(*args: Any) -> int:
        ctypes.set_errno(error)
        return -1

    monkeypatch.setattr(
        ctypes, "CDLL", lambda *a, **kw: SimpleNamespace(syscall=syscall)
    )

    assert read_quota(tmp_path) is None


@pytest.mark.parametrize("architecture", ["x86_64", "ppc64le", "s390x"])
def test_linux_quota_converts_kib_limits_but_keeps_byte_usage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    architecture: str,
) -> None:
    monkeypatch.setattr(platform, "machine", lambda: architecture)

    def syscall(*args: Any) -> int:
        # Linux if_dqblk: 八个 u64, 接着是 dqb_valid; 额度单位 KiB。
        assert args[0].value == 443
        payload = struct.pack("=8QI", 8_388_608, 0, 2_147_483_648, 0, 0, 0, 0, 0, 3)
        ctypes.memmove(args[4], payload, len(payload))
        return 0

    monkeypatch.setattr(
        ctypes, "CDLL", lambda *a, **kw: SimpleNamespace(syscall=syscall)
    )

    assert read_quota(tmp_path) == Quota(8_589_934_592, 2_147_483_648)


@pytest.mark.parametrize("architecture", ["mips64", "unrecognized-abi"])
def test_unverified_syscall_abi_is_unknown_without_attempting_a_number(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    architecture: str,
) -> None:
    monkeypatch.setattr(platform, "machine", lambda: architecture)

    def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("an unverified syscall ABI must not be called")

    monkeypatch.setattr(ctypes, "CDLL", forbidden)

    assert read_quota(tmp_path) is None


def test_x32_abi_does_not_use_native_x86_64_syscall_number(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(ctypes, "sizeof", lambda kind: 4)

    def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("x32 must not use the native x86_64 syscall number")

    monkeypatch.setattr(ctypes, "CDLL", forbidden)

    assert read_quota(tmp_path) is None
