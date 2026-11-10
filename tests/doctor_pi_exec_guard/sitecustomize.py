"""独立 Pi doctor 冷进程守卫;不放松 basic/config 的旧守卫。"""

import errno
import importlib.abc
import os
import sqlite3
import sys
from typing import Any


class NoExecution(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname: str, *_args: Any, **_kwargs: Any) -> None:
        if fullname in {
            "paper_radar.pi_execution.auth",
            "paper_radar.pi_execution.launcher",
            "paper_radar.pi_execution.service",
        } or (
            os.environ.get("PI_DOCTOR_HELP") == "1"
            and fullname.startswith("paper_radar.pi_execution")
        ):
            os._exit(97)


sys.meta_path.insert(0, NoExecution())


# 冷进程不继承父进程 monkeypatch;真实现场源必须在 OS 边界隔离。
def protected_source(path: object) -> bool:
    return isinstance(path, (str, bytes, os.PathLike)) and os.fsdecode(path).startswith(
        "/var/lib/paperradar/"
    )


for name in ("stat", "lstat"):
    original = getattr(os, name)

    def offline_stat(
        path: Any, *args: Any, _stat: Any = original, **kwargs: Any
    ) -> Any:
        if protected_source(path):
            raise PermissionError(errno.EACCES, "offline protected source unavailable")
        return _stat(path, *args, **kwargs)

    setattr(os, name, offline_stat)


def guard(event: str, args: tuple[object, ...]) -> None:
    if (
        event.startswith(
            ("socket.", "subprocess.", "os.exec", "os.spawn", "os.posix_spawn")
        )
        or event
        in {
            "os.system",
            "os.fork",
            "os.forkpty",
            "pty.spawn",
            "tempfile.mkdtemp",
            "os.mkdir",
            "os.remove",
            "os.rename",
            "os.rmdir",
            "os.chmod",
        }
        or (event == "sqlite3.connect" and os.environ.get("PI_DOCTOR_HELP") == "1")
    ):
        os._exit(97)
    if event in {"open", "sqlite3.connect"} and args and protected_source(args[0]):
        raise PermissionError(errno.EACCES, "offline protected source unavailable")
    if event == "open":
        if str(args[0]) == os.environ.get("PI_DOCTOR_CREDENTIAL"):
            os._exit(97)
        flags = args[2]
        if isinstance(flags, int) and flags & (
            os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC
        ):
            os._exit(97)


sys.addaudithook(guard)
_connect = sqlite3.connect


def readonly_connect(*args: Any, **kwargs: Any) -> sqlite3.Connection:
    connection: sqlite3.Connection = _connect(*args, **kwargs)

    def authorize(action: int, table: str | None, *_rest: object) -> int:
        if action in {
            sqlite3.SQLITE_INSERT,
            sqlite3.SQLITE_UPDATE,
            sqlite3.SQLITE_DELETE,
            sqlite3.SQLITE_CREATE_TABLE,
            sqlite3.SQLITE_DROP_TABLE,
        } or (
            action == sqlite3.SQLITE_READ
            and table
            and table.startswith(("screening_", "audit_"))
        ):
            os._exit(97)
        return sqlite3.SQLITE_OK

    connection.set_authorizer(authorize)
    return connection


setattr(sqlite3, "connect", readonly_connect)  # noqa: B010
