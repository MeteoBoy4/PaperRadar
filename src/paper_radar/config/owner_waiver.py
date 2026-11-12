"""所有者显式豁免的版本记录;业务库内追加,不产生任何 Live 证据。"""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import Connection, or_, select
from sqlalchemy.exc import SQLAlchemyError

from paper_radar.storage.database import (
    DatabaseMode,
    open_database,
    require_current_revision,
)
from paper_radar.storage.errors import StorageError
from paper_radar.storage.schema import config_versions

OWNER_WAIVER_REASON = "owner_evidence_prerequisite_waived"
OWNER_WAIVER_NOTICE = "证据前提已由所有者豁免（ADR-0068）"
_KIND, _NAME = "owner_waiver", "live-evidence"


class OwnerWaiverError(ValueError):
    def __init__(
        self,
        reason: Literal[
            "owner_waiver_action_invalid",
            "owner_waiver_history_invalid",
            "owner_waiver_unavailable",
            "owner_waiver_clock_invalid",
        ],
    ) -> None:
        self.reason = reason
        super().__init__(reason)


class OwnerWaiverRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    format_version: Literal[1]
    policy: Literal["live-evidence-prerequisite-v1"]
    version: int = Field(ge=1)
    enabled: bool
    actor: Literal["owner"]
    reason: str = Field(min_length=1, max_length=1000)
    recorded_at: datetime
    previous_sha256: str | None

    @field_validator("format_version", mode="before")
    @classmethod
    def exact_format(cls, value: object) -> object:
        if type(value) is not int or value != 1:
            raise ValueError("owner_waiver_history_invalid")
        return value


@dataclass(frozen=True, slots=True)
class OwnerWaiver:
    enabled: bool = False
    version: int = 0
    record_sha256: str | None = None
    strict_since: datetime | None = None
    recorded_at: datetime | None = None


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise OwnerWaiverError("owner_waiver_clock_invalid")
    return value.astimezone(UTC)


@contextmanager
def _connection(database: Path, *, write: bool) -> Iterator[Connection]:
    try:
        engine = open_database(
            database, mode=DatabaseMode.READ_WRITE if write else DatabaseMode.READ_ONLY
        )
        try:
            require_current_revision(engine)
            with engine.connect() as connection:
                if write:
                    connection.exec_driver_sql("BEGIN IMMEDIATE")
                yield connection
                if write:
                    connection.commit()
        finally:
            engine.dispose()
    except (StorageError, SQLAlchemyError, OSError):
        raise OwnerWaiverError("owner_waiver_unavailable") from None


def _read(connection: Connection) -> OwnerWaiver:
    state = OwnerWaiver()
    rows = connection.execute(
        select(config_versions).where(
            or_(config_versions.c.kind == _KIND, config_versions.c.name == _NAME)
        )
    ).mappings()
    records = []
    try:
        for row in rows:
            raw = bytes(row["raw_content"])
            record = OwnerWaiverRecord.model_validate_json(raw)
            digest = sha256(raw).hexdigest()
            if (
                row["kind"] != _KIND
                or row["name"] != _NAME
                or digest != row["raw_sha256"]
                or str(record.version) != row["declared_version"]
                or not record.reason.strip()
            ):
                raise ValueError
            records.append((record, digest))
        for record, digest in sorted(records, key=lambda pair: pair[0].version):
            recorded_at = _utc(record.recorded_at)
            if (
                record.version != state.version + 1
                or record.previous_sha256 != state.record_sha256
                or (state.recorded_at is not None and recorded_at < state.recorded_at)
            ):
                raise ValueError
            state = OwnerWaiver(
                record.enabled,
                record.version,
                digest,
                state.strict_since if record.enabled else recorded_at,
                recorded_at,
            )
    except (ValueError, TypeError, ValidationError):
        raise OwnerWaiverError("owner_waiver_history_invalid") from None
    return state


def owner_waiver(database: Path, *, now: datetime | None = None) -> OwnerWaiver:
    """只读;没有版本记录即关闭,未知格式/损坏不得退回默认值。"""
    with _connection(database, write=False) as connection:
        state = _read(connection)
    if (
        now is not None
        and state.recorded_at is not None
        and _utc(now) < state.recorded_at
    ):
        raise OwnerWaiverError("owner_waiver_clock_invalid")
    return state


def record_owner_waiver(
    database: Path,
    *,
    enabled: bool,
    reason: str,
    actor: Literal["owner"],
    now: datetime,
) -> OwnerWaiver:
    """仅所有者命令调用;每次动作新增版本,不改已有字节或证据账本。"""
    if type(enabled) is not bool or actor != "owner" or not reason.strip():
        raise OwnerWaiverError("owner_waiver_action_invalid")
    recorded_at = _utc(now)
    with _connection(database, write=True) as connection:
        previous = _read(connection)
        if previous.recorded_at is not None and recorded_at < previous.recorded_at:
            raise OwnerWaiverError("owner_waiver_clock_invalid")
        try:
            record = OwnerWaiverRecord(
                format_version=1,
                policy="live-evidence-prerequisite-v1",
                version=previous.version + 1,
                enabled=enabled,
                actor=actor,
                reason=reason.strip(),
                recorded_at=recorded_at,
                previous_sha256=previous.record_sha256,
            )
        except ValidationError:
            raise OwnerWaiverError("owner_waiver_action_invalid") from None
        raw = record.model_dump_json().encode()
        connection.execute(
            config_versions.insert().values(
                kind=_KIND,
                name=_NAME,
                declared_version=str(record.version),
                raw_sha256=sha256(raw).hexdigest(),
                raw_content=raw,
            )
        )
        return _read(connection)
