"""登记事务与回包窗口的真实进程屏障;链式禁止联网。"""

import os
import runpy
from pathlib import Path

from sqlalchemy import Engine, event

from tests.a3_process_support import checkpoint

runpy.run_path(str(Path(__file__).parents[1] / "deny_network/sitecustomize.py"))
phase = os.environ.get("A7_REGISTRATION_PAUSE", "")
paused = False
business = False


@event.listens_for(Engine, "before_cursor_execute")
def before(connection, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
    global paused, business
    if statement.startswith("INSERT INTO screening_requests"):
        business = True
    match = {
        "begin": "BEGIN IMMEDIATE",
        "middle": "INSERT INTO screening_requests",
    }.get(phase)
    if match and statement.startswith(match) and not paused:
        paused = True
        checkpoint()


@event.listens_for(Engine, "commit")
def commit(connection):  # type: ignore[no-untyped-def]
    if phase == "committed" and business:
        connection.connection.driver_connection.commit()
        checkpoint()
