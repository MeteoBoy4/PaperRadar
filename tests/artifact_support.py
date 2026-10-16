"""A3 独立测试支撑;不修改 A2 的固定 support 或哨兵。"""

from __future__ import annotations

import os
import select
import sqlite3
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Connection, Engine, event


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
    ready_read, ready_write = os.pipe()
    release_read, release_write = os.pipe()
    process = subprocess.Popen(
        [sys.executable, "-c", code, *arguments],
        env={
            "PATH": os.environ["PATH"],
            "PYTHONPATH": str(Path(__file__).parent / "artifact_process"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "A3_PAUSE_SQL": prefix,
            "A3_READY_FD": str(ready_write),
            "A3_RELEASE_FD": str(release_read),
        },
        pass_fds=(ready_write, release_read),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    os.close(ready_write)
    os.close(release_read)
    try:
        readable, _, _ = select.select([ready_read], [], [], 15)
        assert readable, "子进程未到达 A3 屏障"
        assert os.read(ready_read, 1) == b"R", "子进程提前退出"
        yield process
    finally:
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=15)
        os.close(ready_read)
        os.close(release_write)
