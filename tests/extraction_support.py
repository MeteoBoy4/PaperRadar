"""多文件发布的独立 A3 输入与真实进程屏障。"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path

from tests.a3_process_support import paused_subprocess

PAYLOADS = {
    "document": b"PRIVATE_DOCUMENT",
    "evidence_map": b"PRIVATE_EVIDENCE",
    "manifest": b"PRIVATE_MANIFEST",
    "reading": b"PRIVATE_READING",
}


def chunked(values: Mapping[str, bytes]) -> dict[str, Iterable[bytes]]:
    def chunks(raw: bytes) -> Iterator[bytes]:
        for offset in range(0, len(raw), 3):
            yield raw[offset : offset + 3]

    return {role: chunks(raw) for role, raw in values.items()}


@contextmanager
def paused_extraction(
    database: Path, root: Path, phase: str, *, variant: bool = False
) -> Iterator[tuple[subprocess.Popen[str], int]]:
    with paused_subprocess(
        [
            sys.executable,
            "-m",
            "tests.extraction_process.publish",
            str(database),
            str(root),
            "variant" if variant else "same",
        ],
        Path(__file__).parent / "extraction_process",
        {"A3_EXTRACTION_PHASE": phase},
        "正文制品子进程未到达屏障",
        "正文制品子进程提前退出",
    ) as paused:
        yield paused


@contextmanager
def failed_registration(phase: str) -> Iterator[None]:
    """仅在 SQL/commit 外部边界制造真实 SQLite 错误。"""
    from sqlalchemy import Connection, Engine, event

    count = 0

    def fail(
        connection: Connection,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        nonlocal count
        prefix = (
            "BEGIN IMMEDIATE"
            if phase == "before_registration"
            else "INSERT INTO artifact_members"
        )
        if statement.startswith(prefix):
            count += 1
            if count == (2 if phase == "member_rows" else 1):
                connection.exec_driver_sql(
                    "INSERT INTO nonexistent_extraction_table VALUES (1)"
                )

    def fail_commit(connection: Connection) -> None:
        connection.exec_driver_sql(
            "INSERT INTO nonexistent_extraction_table VALUES (1)"
        )

    if phase == "before_commit":
        event.listen(Engine, "commit", fail_commit)
    else:
        event.listen(Engine, "before_cursor_execute", fail)
    try:
        yield
    finally:
        if phase == "before_commit":
            event.remove(Engine, "commit", fail_commit)
        else:
            event.remove(Engine, "before_cursor_execute", fail)
