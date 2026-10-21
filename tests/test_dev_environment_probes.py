"""只读 OS 边界测试: 配额 ABI 与错误降级。"""

import ctypes
import errno
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


def test_linux_quota_converts_kib_limits_but_keeps_byte_usage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def syscall(*args: Any) -> int:
        # Linux if_dqblk: 八个 u64, 接着是 dqb_valid; 额度单位 KiB。
        payload = struct.pack("=8QI", 8_388_608, 0, 2_147_483_648, 0, 0, 0, 0, 0, 3)
        ctypes.memmove(args[4], payload, len(payload))
        return 0

    monkeypatch.setattr(
        ctypes, "CDLL", lambda *a, **kw: SimpleNamespace(syscall=syscall)
    )

    assert read_quota(tmp_path) == Quota(8_589_934_592, 2_147_483_648)
