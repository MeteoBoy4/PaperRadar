"""Read独立短事务与确定性序列化,不借用Screening任务内核。"""

import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from pathlib import Path

from sqlalchemy import Connection
from sqlalchemy.exc import SQLAlchemyError

from paper_radar.read_tasks.models import ReadTaskError
from paper_radar.storage.database import (
    DatabaseMode,
    open_database,
    require_current_revision,
)


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def records(values: object) -> str:
    if isinstance(values, (tuple, list)):
        return canonical(
            [
                asdict(v) if is_dataclass(v) and not isinstance(v, type) else v
                for v in values
            ]
        )
    raise ReadTaskError("corrupt_reference")


def required(*values: str) -> None:
    if any(type(v) is not str or not v.strip() or len(v) > 8192 for v in values):
        raise ReadTaskError("invalid_request")


@contextmanager
def transaction(database: Path, *, write: bool = False) -> Iterator[Connection]:
    engine = open_database(
        database, mode=DatabaseMode.READ_WRITE if write else DatabaseMode.READ_ONLY
    )
    try:
        require_current_revision(engine)
        with engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE" if write else "BEGIN")
            yield connection
            if write:
                connection.commit()
    except SQLAlchemyError:
        raise ReadTaskError("database_failed") from None
    finally:
        engine.dispose()
