"""A3 独立的真实 SQLite 进程中断哨兵。"""

import os

from sqlalchemy import Engine, event

from tests.a3_process_support import checkpoint

prefix = os.environ.get("A3_PAUSE_SQL")
if prefix:

    @event.listens_for(Engine, "before_cursor_execute")
    def pause(connection, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
        if statement.startswith(prefix):
            checkpoint()
