"""#124 独立冷进程守卫。不改变历史绑定守卫。"""

import os
import sqlite3
import sys
from typing import Any


def guard(event: str, _args: tuple[object, ...]) -> None:
    if (
        event.startswith(
            ("socket.", "subprocess.", "os.exec", "os.spawn", "os.posix_spawn")
        )
        or event in {"os.system", "os.fork", "os.forkpty", "pty.spawn"}
        or (event == "sqlite3.connect" and os.environ.get("DOCTOR_HELP_ONLY") == "1")
    ):
        os._exit(97)
    if event == "os.scandir" and str(_args[0]).startswith(
        os.environ.get("DOCTOR_FORBIDDEN_INSTALL", "\0")
    ):
        os._exit(97)
    if event == "open" and str(_args[0]) == os.environ.get(
        "DOCTOR_FORBIDDEN_CREDENTIAL"
    ):
        os._exit(97)


sys.addaudithook(guard)

_connect = sqlite3.connect


def readonly_connect(*args: Any, **kwargs: Any) -> sqlite3.Connection:
    connection: sqlite3.Connection = _connect(*args, **kwargs)

    def authorize(action: int, table: str | None, *_rest: object) -> int:
        if (
            action == sqlite3.SQLITE_READ
            and table
            and table.startswith(("audit_", "pi_"))
        ):
            os._exit(97)
        return sqlite3.SQLITE_OK

    connection.set_authorizer(authorize)
    return connection


setattr(sqlite3, "connect", readonly_connect)  # noqa: B010
