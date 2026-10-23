"""任务边界共享的 SQLite 错误分类,不回显数据库参数。"""

import sqlite3

from sqlalchemy.exc import DBAPIError, SQLAlchemyError

from paper_radar.screening_tasks.errors import TaskError, TaskReason


def database_error(error: SQLAlchemyError) -> TaskError:
    busy = (
        isinstance(error, DBAPIError)
        and isinstance(error.orig, sqlite3.Error)
        and (getattr(error.orig, "sqlite_errorcode", 0) & 0xFF) == sqlite3.SQLITE_BUSY
    )
    return TaskError(TaskReason.DATABASE_BUSY if busy else TaskReason.CORRUPT_REFERENCE)
