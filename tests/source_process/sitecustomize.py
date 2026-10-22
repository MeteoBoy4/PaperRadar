"""来源仲裁真实进程屏障;仅测试子进程加载。"""

import os
import runpy
from pathlib import Path

from sqlalchemy import Engine, event

from tests.a3_process_support import checkpoint

runpy.run_path(str(Path(__file__).parents[1] / "deny_network/sitecustomize.py"))
phase = os.environ.get("SOURCE_PAUSE", "")
begins = 0
paused = False
business = False


@event.listens_for(Engine, "before_cursor_execute")
def before(connection, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
    global begins, paused, business
    if statement == "BEGIN IMMEDIATE":
        begins += 1
        if phase in {"begin", "published"} and begins == 2 and not paused:
            paused = True
            checkpoint()
    if statement.startswith("INSERT INTO paper_source_acquisitions"):
        business = True
    if (
        phase == "middle"
        and statement.startswith("INSERT INTO paper_field_candidates")
        and not paused
    ):
        paused = True
        checkpoint()
    if phase == "read" and statement.startswith("SELECT paper_versions") and not paused:
        paused = True
        checkpoint()


@event.listens_for(Engine, "commit")
def commit(connection):  # type: ignore[no-untyped-def]
    if phase == "committed" and business:
        connection.connection.driver_connection.commit()
        checkpoint()
