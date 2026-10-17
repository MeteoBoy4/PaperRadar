"""A3 独立测试支撑;不修改 A2 的固定 support 或哨兵。"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Connection, Engine, event

from tests.a3_process_support import paused_subprocess


def registration_facts(database: Path) -> tuple[list[tuple[object, ...]], ...]:
    with sqlite3.connect(database) as connection:
        return tuple(
            connection.execute(f"SELECT * FROM {table} ORDER BY 1, 2").fetchall()
            for table in ("content_objects", "artifacts", "artifact_members")
        )


@contextmanager
def fail_sql(prefix: str) -> Iterator[None]:
    def fail(
        connection: Connection,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        if statement.startswith(prefix):
            connection.exec_driver_sql("INSERT INTO nonexistent_a3_table VALUES (1)")

    event.listen(Engine, "before_cursor_execute", fail)
    try:
        yield
    finally:
        event.remove(Engine, "before_cursor_execute", fail)


@contextmanager
def paused_operation(
    code: str, arguments: list[str], prefix: str
) -> Iterator[subprocess.Popen[str]]:
    with paused_subprocess(
        [sys.executable, "-c", code, *arguments],
        Path(__file__).parent / "artifact_process",
        {"A3_PAUSE_SQL": prefix},
        "子进程未到达 A3 屏障",
        "子进程提前退出",
    ) as (process, _):
        yield process
