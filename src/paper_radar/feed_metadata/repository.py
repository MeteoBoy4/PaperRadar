"""短事务与哈希绑定的元数据执行记录。"""

import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import Connection, select

from paper_radar.feed_metadata.models import MetadataBasis, MetadataRoute
from paper_radar.feed_metadata.tables import routes, runs
from paper_radar.papers.errors import PaperError, PaperReason
from paper_radar.storage.database import (
    DatabaseMode,
    open_database,
    require_current_revision,
)


def sha(value: str | bytes) -> str:
    return hashlib.sha256(
        value.encode() if isinstance(value, str) else value
    ).hexdigest()


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def corrupt() -> PaperError:
    return PaperError(PaperReason.CORRUPT_REFERENCE, path="metadata")


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
    finally:
        engine.dispose()


def load_run(connection: Connection, key: str) -> tuple[dict[str, Any], int | None]:
    row = (
        connection.execute(select(runs).where(runs.c.request_key == key))
        .mappings()
        .first()
    )
    if row is None or sha(row["basis_json"]) != row["basis_sha256"]:
        raise corrupt()
    try:
        basis = MetadataBasis.model_validate_json(row["basis_json"]).model_dump()
        if (
            basis["paper_id"] != row["paper_id"]
            or basis["request_id"] != row["request_id"]
            or sha(canonical([row["paper_id"], row["request_id"]])) != key
        ):
            raise ValueError
        return basis, row["revision_no"]
    except (TypeError, ValueError, KeyError):
        raise corrupt() from None


def load_routes(connection: Connection, key: str) -> tuple[MetadataRoute, ...]:
    result = []
    for row in connection.execute(
        select(routes).where(routes.c.request_key == key).order_by(routes.c.route)
    ).mappings():
        try:
            if sha(key + row["view_json"]) != row["view_sha256"]:
                raise ValueError
            value = MetadataRoute.model_validate_json(row["view_json"])
            if (
                value.route != row["route"]
                or value.artifact_id != row["artifact_id"]
                or value.acquisition_id != row["acquisition_id"]
            ):
                raise ValueError
            result.append(value)
        except (TypeError, ValueError):
            raise corrupt() from None
    return tuple(result)


def put_route(
    connection: Connection, key: str, view: MetadataRoute, *, replace: bool = False
) -> None:
    old = connection.execute(
        select(routes.c.route).where(
            routes.c.request_key == key, routes.c.route == view.route
        )
    ).first()
    values = dict(
        view_json=view.model_dump_json(),
        artifact_id=view.artifact_id,
        acquisition_id=view.acquisition_id,
    )
    values["view_sha256"] = sha(key + view.model_dump_json())
    if old is None:
        connection.execute(
            routes.insert().values(request_key=key, route=view.route, **values)
        )
    elif replace:
        connection.execute(
            routes.update()
            .where(routes.c.request_key == key, routes.c.route == view.route)
            .values(**values)
        )
