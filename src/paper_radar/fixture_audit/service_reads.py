"""审计服务共享的只读事务、计划查找和保留材料读取。"""

from collections.abc import Callable
from pathlib import Path

from sqlalchemy import Connection
from sqlalchemy.exc import SQLAlchemyError

from paper_radar.fixture_audit.acquisition_models import AuditView, RouteExecution
from paper_radar.fixture_audit.errors import FixtureError, FixtureReason
from paper_radar.storage.artifacts import ArtifactStore
from paper_radar.storage.database import (
    DatabaseMode,
    open_database,
    require_current_revision,
)


def read_snapshot[Value](
    database: Path, loader: Callable[[Connection], Value], *, path: str
) -> Value:
    engine = open_database(database, mode=DatabaseMode.READ_ONLY)
    try:
        require_current_revision(engine)
        with engine.connect() as connection:
            connection.exec_driver_sql("BEGIN")
            return loader(connection)
    except SQLAlchemyError:
        raise FixtureError(FixtureReason.CORRUPT_REFERENCE, path=path) from None
    finally:
        engine.dispose()


def find_plan[View: AuditView](views: tuple[View, ...], plan_id: str) -> View:
    for view in views:
        if view.plan.plan_id == plan_id:
            return view
    raise FixtureError(FixtureReason.RECORD_NOT_FOUND, path="plan_id")


def read_material(
    database: Path,
    data_root: Path | None,
    execution: RouteExecution,
    *,
    path: str,
) -> bytes:
    if (
        data_root is None
        or execution.settlement is None
        or execution.settlement.artifact_id is None
    ):
        raise FixtureError(FixtureReason.EVIDENCE_REQUIRED, path=path)
    return ArtifactStore(database, data_root).read_artifact(
        execution.settlement.artifact_id
    )["payload"]
