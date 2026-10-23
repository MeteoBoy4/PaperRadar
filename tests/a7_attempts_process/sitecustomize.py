"""尝试领取/租约事务和提交回包窗口的管道屏障。"""

import os
import runpy
from pathlib import Path

from sqlalchemy import Engine, event

from tests.a3_process_support import checkpoint

runpy.run_path(str(Path(__file__).parents[1] / "deny_network/sitecustomize.py"))
phase = os.environ.get("A7_ATTEMPTS_PAUSE", "")
paused = False
business = False


@event.listens_for(Engine, "before_cursor_execute")
def before(connection, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
    global paused, business
    if statement.startswith("INSERT INTO screening_attempts"):
        business = True
    match = {
        "begin": "BEGIN IMMEDIATE",
        "middle": "INSERT INTO screening_attempts",
    }.get(phase)
    if match and statement.startswith(match) and not paused:
        paused = True
        checkpoint()


@event.listens_for(Engine, "commit")
def commit(connection):  # type: ignore[no-untyped-def]
    if phase == "committed" and business:
        connection.connection.driver_connection.commit()
        checkpoint()
