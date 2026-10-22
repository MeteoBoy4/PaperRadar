"""真实进程的 SQL/提交屏障;生产代码无需测试钩子。"""

import os
import runpy
from pathlib import Path

from sqlalchemy import Engine, event

from tests.a3_process_support import checkpoint

runpy.run_path(str(Path(__file__).parents[1] / "deny_network/sitecustomize.py"))
phase = os.environ.get("PAPER_PAUSE", "")
paused = False
business = False


@event.listens_for(Engine, "before_cursor_execute")
def before(connection, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
    global paused, business
    if statement.startswith("INSERT INTO papers"):
        business = True
    match = {
        "published": "SELECT external_identifiers",
        "middle": "INSERT INTO paper_field_candidates",
        "read": "SELECT paper_versions",
        "begin": "BEGIN IMMEDIATE",
    }.get(phase)
    if match and statement.startswith(match) and not paused:
        paused = True
        checkpoint()


@event.listens_for(Engine, "commit")
def commit(connection):  # type: ignore[no-untyped-def]
    if phase == "committed" and business:
        # This event precedes DBAPI commit, so pause immediately after the real
        # commit using the driver connection, before caller receives a result.
        connection.connection.driver_connection.commit()
        checkpoint()
