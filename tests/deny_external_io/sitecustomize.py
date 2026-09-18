"""拒绝 CLI 帮助进程访问网络或 SQLite。"""

from __future__ import annotations

import socket
import sqlite3
from typing import NoReturn


def _deny_operation(*_args: object, **_kwargs: object) -> NoReturn:
    raise AssertionError("帮助命令不应访问网络或数据库")


setattr(socket, "socket", _deny_operation)  # noqa: B010
setattr(socket, "create_connection", _deny_operation)  # noqa: B010
setattr(sqlite3, "connect", _deny_operation)  # noqa: B010
