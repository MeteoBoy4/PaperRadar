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
