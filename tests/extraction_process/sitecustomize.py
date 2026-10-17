"""只在测试子进程启用的文件/SQLite 真实中断屏障。"""

import os
from typing import Any

from sqlalchemy import Engine, event

from tests.a3_process_support import checkpoint

phase = os.environ.get("A3_EXTRACTION_PHASE")


if phase == "partial_files":
    original_link = os.link
    links = 0

    def controlled_link(*args: Any, **kwargs: Any) -> None:
        global links
        links += 1
        if links == 2:
            checkpoint()
        original_link(*args, **kwargs)

    os.link = controlled_link

if phase in ("before_registration", "member_rows"):
    prefix = (
        "BEGIN IMMEDIATE"
        if phase == "before_registration"
        else "INSERT INTO artifact_members"
    )
    statements = 0

    @event.listens_for(Engine, "before_cursor_execute")
    def pause(
        connection: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        global statements
        if statement.startswith(prefix):
            statements += 1
            if statements == (2 if phase == "member_rows" else 1):
                checkpoint()


if phase == "before_commit":

    @event.listens_for(Engine, "commit")
    def commit(connection: Any) -> None:
        checkpoint()
