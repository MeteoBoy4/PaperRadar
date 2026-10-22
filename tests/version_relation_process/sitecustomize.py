"""关系原子写的确定 SQL 屏障。"""

import os
import runpy
from pathlib import Path

from sqlalchemy import Engine, event

from tests.a3_process_support import checkpoint

runpy.run_path(str(Path(__file__).parents[1] / "deny_network/sitecustomize.py"))
phase = os.environ.get("RELATION_PAUSE", "")
paused = False
business = False


@event.listens_for(Engine, "before_cursor_execute")
def before(connection, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
    global paused, business
    if statement.startswith("INSERT INTO paper_source_acquisitions"):
        business = True
    prefix = {
        "ready": "BEGIN IMMEDIATE",
        "begin": "SELECT external_identifiers",
        "version": "INSERT INTO paper_versions",
        "selection": "INSERT INTO paper_selection_events",
        "relation": "INSERT INTO paper_relation_references",
    }.get(phase)
    if prefix and statement.startswith(prefix) and not paused:
        paused = True
        checkpoint()


@event.listens_for(Engine, "commit")
def commit(connection):  # type: ignore[no-untyped-def]
    if phase == "committed" and business:
        connection.connection.driver_connection.commit()
        checkpoint()
