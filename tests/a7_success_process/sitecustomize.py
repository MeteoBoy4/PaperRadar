"""成功发布、写事务、提交回包处的真实进程屏障。"""

import os
import runpy
from pathlib import Path

from sqlalchemy import Engine, event

from paper_radar.storage.artifacts import ArtifactStore
from tests.a3_process_support import checkpoint

runpy.run_path(str(Path(__file__).parents[1] / "deny_network/sitecustomize.py"))
phase = os.environ.get("A7_SUCCESS_PAUSE", "")
paused = False
published = False
business = False
original_publish = ArtifactStore.publish_single


def publish(self, kind, chunks, **kwargs):  # type: ignore[no-untyped-def]
    global published, paused
    result = original_publish(self, kind, chunks, **kwargs)
    if kind == "model_success_response":
        published = True
        if phase == "published" and not paused:
            paused = True
            checkpoint()
    return result


ArtifactStore.publish_single = publish  # type: ignore[method-assign]


@event.listens_for(Engine, "before_cursor_execute")
def before(connection, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
    global paused, business
    if statement.startswith("INSERT INTO screening_successes"):
        business = True
    if phase == "begin" and statement.startswith("BEGIN IMMEDIATE") and not paused:
        paused = True
        checkpoint()
    if (
        phase == "business_begin"
        and published
        and statement.startswith("BEGIN IMMEDIATE")
        and not paused
    ):
        paused = True
        checkpoint()


@event.listens_for(Engine, "after_cursor_execute")
def after(connection, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
    global paused
    if (
        phase == "middle"
        and statement.startswith("INSERT INTO screening_successes")
        and not paused
    ):
        paused = True
        checkpoint()


@event.listens_for(Engine, "commit")
def commit(connection):  # type: ignore[no-untyped-def]
    if phase == "committed" and business:
        connection.connection.driver_connection.commit()
        checkpoint()
