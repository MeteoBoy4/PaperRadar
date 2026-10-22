"""同库历史配置与单次论文一致读组合。不保存载荷或推导任务资格。"""

import re
import sqlite3
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, SQLAlchemyError

from paper_radar.config import ConfigError, StageName, load_config_snapshot
from paper_radar.papers.errors import PaperError, PaperReason
from paper_radar.papers.mapping_models import (
    MappingEvidence,
    ScreeningMappingResult,
    StageMappingResult,
)
from paper_radar.papers.models import AbstractValue
from paper_radar.papers.queries import resolve_revision
from paper_radar.stage_inputs import (
    BuildReason,
    ScreeningFacts,
    StageInputError,
    build_stage_input,
)
from paper_radar.storage.database import (
    DatabaseMode,
    open_database,
    require_current_revision,
)
from paper_radar.storage.errors import StorageError
from paper_radar.storage.schema import runtime_config_snapshots


def _facts(evidence: MappingEvidence) -> ScreeningFacts:
    title = evidence.fields.get("title")
    abstract = evidence.fields.get("abstract")
    if title is None:
        raise PaperError(PaperReason.MISSING_TITLE)
    if abstract is None:
        raise PaperError(PaperReason.MISSING_ABSTRACT)
    if not isinstance(title.value, str) or not isinstance(
        abstract.value, AbstractValue
    ):
        raise PaperError(PaperReason.CORRUPT_REFERENCE)
    if abstract.value.is_truncated is None:
        raise PaperError(PaperReason.TRUNCATION_UNKNOWN)
    return ScreeningFacts(
        title=title.value,
        abstract=abstract.value.text,
        abstract_truncated=abstract.value.is_truncated,
    )


def map_screening_inputs(
    database: Path,
    *,
    snapshot_id: str,
    paper_id: str | None = None,
    version_id: str | None = None,
    revision_no: int | None = None,
) -> ScreeningMappingResult:
    """明确当前 Paper 或完整历史修订;拒绝外部配置对象代替登记身份。"""
    evidence = None

    def failed(reason: PaperReason) -> ScreeningMappingResult:
        stage = StageMappingResult(None, reason, evidence, snapshot_id)
        return ScreeningMappingResult(snapshot_id, evidence, stage, stage)

    if (
        type(snapshot_id) is not str
        or re.fullmatch(r"[0-9a-f]{64}", snapshot_id) is None
    ):
        return failed(PaperReason.SNAPSHOT_NOT_FOUND)
    try:
        engine = open_database(database, mode=DatabaseMode.READ_ONLY)
        try:
            require_current_revision(engine)
            with engine.connect() as connection:
                connection.exec_driver_sql("BEGIN")
                revision = resolve_revision(
                    connection,
                    paper_id=paper_id,
                    version_id=version_id,
                    revision_no=revision_no,
                )
                evidence = MappingEvidence(
                    **revision.model_dump(), snapshot_id=snapshot_id
                )
                if (
                    connection.execute(
                        select(runtime_config_snapshots.c.snapshot_id).where(
                            runtime_config_snapshots.c.snapshot_id == snapshot_id
                        )
                    ).first()
                    is None
                ):
                    return failed(PaperReason.SNAPSHOT_NOT_FOUND)
                snapshot = load_config_snapshot(database, snapshot_id)
                facts = _facts(evidence)
                stages = []
                for name in (StageName.BOUNDARY, StageName.VALUE):
                    try:
                        value = build_stage_input(snapshot, name, facts)
                    except StageInputError as error:
                        reason = (
                            PaperReason.CONFIG_NOT_READY
                            if error.reason == BuildReason.NOT_READY
                            else PaperReason.CORRUPT_REFERENCE
                        )
                        stages.append(
                            StageMappingResult(None, reason, evidence, snapshot_id)
                        )
                    else:
                        stages.append(
                            StageMappingResult(value, None, evidence, snapshot_id)
                        )
                return ScreeningMappingResult(snapshot_id, evidence, *stages)
        finally:
            engine.dispose()
    except PaperError as error:
        return failed(error.reason)
    except (StorageError, ConfigError, StageInputError):
        return failed(PaperReason.CORRUPT_REFERENCE)
    except SQLAlchemyError as error:
        busy = (
            isinstance(error, DBAPIError)
            and isinstance(error.orig, sqlite3.Error)
            and (getattr(error.orig, "sqlite_errorcode", 0) & 0xFF)
            == sqlite3.SQLITE_BUSY
        )
        return failed(
            PaperReason.DATABASE_BUSY if busy else PaperReason.CORRUPT_REFERENCE
        )
