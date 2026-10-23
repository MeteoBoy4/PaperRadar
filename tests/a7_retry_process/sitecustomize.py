"""retry 写事务与真实提交后丢回包的进程屏障。"""

import os
import runpy
from pathlib import Path

from sqlalchemy import Engine, event

from tests.a3_process_support import checkpoint

runpy.run_path(str(Path(__file__).parents[1] / "deny_network/sitecustomize.py"))
phase = os.environ.get("A7_RETRY_PAUSE", "")
paused = False
business = False


@event.listens_for(Engine, "before_cursor_execute")
def before(connection, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
    global paused, business
    if statement.startswith("INSERT INTO screening_tasks"):
        business = True
    if phase == "begin" and statement.startswith("BEGIN IMMEDIATE") and not paused:
        paused = True
        checkpoint()


@event.listens_for(Engine, "after_cursor_execute")
def after(connection, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
    global paused
    if (
        phase == "middle"
        and statement.startswith("INSERT INTO screening_tasks")
        and not paused
    ):
        paused = True
        checkpoint()


@event.listens_for(Engine, "commit")
def commit(connection):  # type: ignore[no-untyped-def]
    if phase == "committed" and business:
        connection.connection.driver_connection.commit()
        checkpoint()
