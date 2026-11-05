"""短事务与追加事件公共支撑;不执行 parser 或加载 SDK。"""

import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import Connection, TableClause, func, select
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import SQLAlchemyError

from paper_radar.body.models import BodyError, BodyReason
from paper_radar.storage.database import (
    DatabaseMode,
    open_database,
    require_current_revision,
)


def now() -> str:
    return datetime.now(UTC).isoformat()


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def required(*values: str) -> None:
    if any(
        type(value) is not str or not value.strip() or len(value) > 8192
        for value in values
    ):
        raise BodyError(BodyReason.INVALID_REQUEST)


def sequence(connection: Connection, table: TableClause, paper_id: str) -> int:
    return (
        int(
            connection.execute(
                select(func.coalesce(func.max(table.c.sequence), 0)).where(
                    table.c.paper_id == paper_id
                )
            ).scalar_one()
        )
        + 1
    )


def replay(
    connection: Connection, table: TableClause, request_id: str, request_hash: str
) -> RowMapping | None:
    row = (
        connection.execute(select(table).where(table.c.request_id == request_id))
        .mappings()
        .first()
    )
    if row is not None and row["request_hash"] != request_hash:
        raise BodyError(BodyReason.REQUEST_CONFLICT)
    return row


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
        raise BodyError(BodyReason.DATABASE_FAILED) from None
    finally:
        engine.dispose()
