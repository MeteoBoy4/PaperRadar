"""A2-09 子进程专用 SQLite 屏障。真实安装 CLI 与真实数据库保持不变。"""

from __future__ import annotations

import os
import runpy
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any, Self, cast, overload

runpy.run_path(str(Path(__file__).parents[1] / "deny_network/sitecustomize.py"))

_PAUSE_AT = os.environ["PAPER_RADAR_TEST_PAUSE_AT"]
_READY = int(os.environ["PAPER_RADAR_TEST_READY_FD"])
_RELEASE = int(os.environ["PAPER_RADAR_TEST_RELEASE_FD"])
_paused = False
_references = 0


def _pause() -> None:
    global _paused
    if not _paused:
        _paused = True
        os.write(_READY, b"R")
        if os.read(_RELEASE, 1) != b"G":
            raise RuntimeError("测试屏障未释放")


class ControlledCursor(sqlite3.Cursor):
    def execute(self, sql: str, parameters: Any = (), /) -> Self:
        global _references
        if (_PAUSE_AT == "begin" and sql == "BEGIN IMMEDIATE") or (
            _PAUSE_AT == "snapshot"
            and sql.startswith("INSERT INTO runtime_config_snapshots")
        ):
            _pause()
        elif sql.startswith("INSERT INTO snapshot_version_refs"):
            _references += 1
            if _PAUSE_AT == "references" and _references == 2:
                _pause()
        return super().execute(sql, parameters)


class ControlledConnection(sqlite3.Connection):
    @overload
    def cursor(self, factory: None = None) -> sqlite3.Cursor: ...

    @overload
    def cursor[T: sqlite3.Cursor](
        self, factory: Callable[[sqlite3.Connection], T]
    ) -> T: ...

    def cursor(
        self, factory: Callable[[sqlite3.Connection], sqlite3.Cursor] | None = None
    ) -> sqlite3.Cursor:
        return super().cursor(factory or ControlledCursor)

    def commit(self) -> None:
        if _PAUSE_AT == "commit" and self.in_transaction:
            _pause()
        super().commit()


_connect = sqlite3.connect


def connect(*args: Any, **kwargs: Any) -> sqlite3.Connection:
    kwargs["factory"] = ControlledConnection
    return cast(sqlite3.Connection, _connect(*args, **kwargs))


setattr(sqlite3, "connect", connect)  # noqa: B010
