"""实验外发授权:既有 config_versions 上只追加的所有者范围决定。"""

import json
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError
from sqlalchemy import Connection, or_, select
from sqlalchemy.exc import SQLAlchemyError

from paper_radar.body.queries import root_fact
from paper_radar.config import RuntimeConfigSnapshot, StageName, project_config
from paper_radar.experiment.reasons import EgressReason
from paper_radar.experiment.root import ExperimentRoot
from paper_radar.storage.database import (
    DatabaseMode,
    open_database,
    require_current_revision,
)
from paper_radar.storage.errors import StorageError
from paper_radar.storage.schema import config_versions

Stage = Literal["boundary", "value", "read"]
Category = Literal["profile", "title_abstract", "legal_body"]
_KIND, _NAME = "experiment_egress", "stage-b-egress"


class EgressError(ValueError):
    def __init__(self, reason: EgressReason | str) -> None:
        self.reason = reason = EgressReason(reason)
        super().__init__(reason)


class Grant(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    stage: Stage
    provider: str = Field(min_length=1, max_length=200)
    model: str = Field(min_length=1, max_length=200)
    categories: tuple[Category, ...] = Field(min_length=1)


class EgressAuthorization(BaseModel):
    """安全投影不携带所有者理由或根路径。"""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    enabled: bool = False
    version: int = 0
    record_sha256: str | None = None
    grants: tuple[Grant, ...] = ()


class _Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    format_version: Literal[1]
    policy: Literal["stage-b-egress-v1"]
    version: int = Field(ge=1)
    enabled: bool
    actor: Literal["owner"]
    reason: str = Field(min_length=1, max_length=1000, repr=False)
    root_id: str
    root_path: str = Field(repr=False)
    grants: tuple[Grant, ...]
    recorded_at: datetime
    previous_sha256: str | None


def parse_stages(stages: Sequence[str]) -> tuple[Stage, ...]:
    """CLI 等未类型化输入先做封闭校验,非法值只返回受控原因。"""
    try:
        return TypeAdapter(tuple[Stage, ...]).validate_python(
            tuple(stages), strict=True
        )
    except ValidationError:
        raise EgressError("egress_scope_mismatch") from None


def required_categories(stage: Stage) -> tuple[Category, ...]:
    if stage not in {"boundary", "value", "read"}:
        raise EgressError("egress_scope_mismatch")
    return (
        ("profile", "title_abstract", "legal_body")
        if stage == "read"
        else ("profile", "title_abstract")
    )


def selected_grants(
    snapshot: RuntimeConfigSnapshot, stages: Sequence[Stage]
) -> tuple[Grant, ...]:
    result = []
    if not stages or len(set(stages)) != len(stages):
        raise EgressError("egress_action_invalid")
    projections = project_config(snapshot).projections
    for stage in stages:
        categories = required_categories(stage)
        model = json.loads(projections[StageName(stage)].payload_json)["components"][
            "model"
        ]
        slot = "reading" if stage == "read" else "screening"
        if model is None or snapshot.model_slots[slot] != "configured":
            raise EgressError("egress_model_unconfigured")
        result.append(
            Grant.model_validate(
                dict(
                    stage=stage,
                    provider=model["provider"],
                    model=model["model"],
                    categories=categories,
                )
            )
        )
    return tuple(result)


@contextmanager
def _connection(database: Path, *, write: bool) -> Iterator[Connection]:
    try:
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
    except (StorageError, SQLAlchemyError, OSError):
        raise EgressError("egress_unavailable") from None


def _read(connection: Connection) -> tuple[EgressAuthorization, _Record | None]:
    state = EgressAuthorization()
    last = None
    try:
        records = []
        rows = connection.execute(
            select(config_versions).where(
                or_(config_versions.c.kind == _KIND, config_versions.c.name == _NAME)
            )
        ).mappings()
        for row in rows:
            raw = bytes(row["raw_content"])
            record = _Record.model_validate_json(raw)
            digest = sha256(raw).hexdigest()
            if (
                row["kind"] != _KIND
                or row["name"] != _NAME
                or row["raw_sha256"] != digest
                or row["declared_version"] != str(record.version)
                or not record.reason.strip()
                or not record.grants
                or len({g.stage for g in record.grants}) != len(record.grants)
                or type(json.loads(raw)["format_version"]) is not int
                or record.recorded_at.tzinfo is None
                or not Path(record.root_path).is_absolute()
            ):
                raise ValueError
            records.append((record, digest))
        for record, digest in sorted(records, key=lambda item: item[0].version):
            if (
                record.version != state.version + 1
                or record.previous_sha256 != state.record_sha256
                or (
                    last is not None
                    and (
                        record.recorded_at < last.recorded_at
                        or record.root_id != last.root_id
                        or record.root_path != last.root_path
                    )
                )
            ):
                raise ValueError
            state = EgressAuthorization(
                enabled=record.enabled,
                version=record.version,
                record_sha256=digest,
                grants=record.grants,
            )
            last = record
    except (ValueError, TypeError, ValidationError):
        raise EgressError("egress_history_invalid") from None
    return state, last


def egress_authorization(
    database: Path, *, connection: Connection | None = None
) -> EgressAuthorization:
    """读取并验证完整链;没有记录仅表示未授权,损坏拒绝。"""
    if connection is not None:
        return _read(connection)[0]
    with _connection(database, write=False) as opened:
        return _read(opened)[0]


def record_egress_authorization(
    root: ExperimentRoot,
    *,
    enabled: bool,
    reason: str,
    grants: tuple[Grant, ...],
    now: datetime,
) -> EgressAuthorization:
    registered = root.require()
    if registered.root_id is None:
        raise EgressError("egress_scope_mismatch")
    if type(enabled) is not bool or not reason.strip() or now.tzinfo is None:
        raise EgressError("egress_action_invalid")
    with _connection(root.database, write=True) as connection:
        previous, last = _read(connection)
        if last is not None and (
            last.root_id != registered.root_id
            or last.root_path != str(root.root.resolve())
        ):
            raise EgressError("egress_scope_mismatch")
        if last is not None and now < last.recorded_at:
            raise EgressError("egress_clock_invalid")
        try:
            record = _Record(
                format_version=1,
                policy="stage-b-egress-v1",
                version=previous.version + 1,
                enabled=enabled,
                actor="owner",
                reason=reason.strip(),
                root_id=registered.root_id,
                root_path=str(root.root.resolve()),
                grants=grants,
                recorded_at=now.astimezone(UTC),
                previous_sha256=previous.record_sha256,
            )
            if not grants or len({g.stage for g in grants}) != len(grants):
                raise ValueError
        except (ValidationError, ValueError):
            raise EgressError("egress_action_invalid") from None
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
        return _read(connection)[0]


def require_egress_authorization(
    root: ExperimentRoot,
    *,
    stage: str,
    provider: str,
    model: str,
    categories: tuple[str, ...],
    connection: Connection | None = None,
) -> EgressAuthorization:
    """认证/领取前及领取短事务内复核;只读,不领取或占预算。"""
    if connection is None:
        root.require()
        with _connection(root.database, write=False) as opened:
            return require_egress_authorization(
                root,
                stage=stage,
                provider=provider,
                model=model,
                categories=categories,
                connection=opened,
            )
    needed = required_categories(parse_stages((stage,))[0])
    registered = root_fact(connection)
    state, record = _read(connection)
    if record is None or not state.enabled:
        raise EgressError("egress_not_authorized")
    if (
        registered.purpose.value != "experiment"
        or record.root_id != registered.root_id
        or record.root_path != str(root.root.resolve())
    ):
        raise EgressError("egress_scope_mismatch")
    grant = next((g for g in state.grants if g.stage == stage), None)
    if grant is None:
        raise EgressError("egress_scope_mismatch")
    if (provider, model) != (grant.provider, grant.model):
        raise EgressError("egress_model_mismatch")
    if not set(needed) <= set(categories) <= set(grant.categories):
        raise EgressError("egress_category_mismatch")
    return state
