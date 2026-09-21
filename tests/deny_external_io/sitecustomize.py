"""拒绝 CLI 子进程外部 I/O。按测试请求注入发布中断。"""

from __future__ import annotations

import os
import socket
import sqlite3
from typing import NoReturn


def _deny_operation(*_args: object, **_kwargs: object) -> NoReturn:
    raise AssertionError("帮助命令不应访问网络或数据库")


setattr(socket, "socket", _deny_operation)  # noqa: B010
setattr(socket, "create_connection", _deny_operation)  # noqa: B010
setattr(sqlite3, "connect", _deny_operation)  # noqa: B010


def _interrupt_publish(*_args: object, **_kwargs: object) -> NoReturn:
    raise InterruptedError("synthetic-secret-cli-interruption")


if os.environ.get("PAPER_RADAR_TEST_INTERRUPT_PUBLISH") == "1":
    setattr(os, "replace", _interrupt_publish)  # noqa: B010


_fail_publish_number = os.environ.get("PAPER_RADAR_TEST_FAIL_PUBLISH_NUMBER")
if _fail_publish_number is not None:
    _original_replace = os.replace
    _fail_at = int(_fail_publish_number)
    _publish_count = 0

    def _fail_selected_publish(
        source: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        destination: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
    ) -> None:
        global _publish_count
        _publish_count += 1
        if _publish_count == _fail_at:
            raise InterruptedError("synthetic-secret-second-publish")
        _original_replace(
            source,
            destination,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
        )

    setattr(os, "replace", _fail_selected_publish)  # noqa: B010
