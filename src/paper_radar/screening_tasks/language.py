"""Feed 归属语言来源;与预算同事务冻结,不参与阶段语义指纹。"""

import hashlib
import json
from typing import Annotated, Literal, TypedDict, cast

import sqlalchemy as sa
from pydantic import AfterValidator, ConfigDict, TypeAdapter, with_config
from sqlalchemy import Connection, select
from sqlalchemy.engine import RowMapping

from paper_radar.papers.tables import (
    feed_discoveries,
    feed_entries,
    feeds,
    papers,
    versions,
)
from paper_radar.screening_tasks.errors import TaskError, TaskReason
from paper_radar.screening_tasks.tables import budgets
from paper_radar.sources.feeds import FEED_SUBSCRIPTIONS, Journal
from paper_radar.storage.schema import metadata

ResolutionStatus = Literal["missing", "ambiguous", "resolved"]


@with_config(ConfigDict(strict=True, extra="forbid"))
class LanguageSource(TypedDict):
    discovery_id: str
    feed_id: str
    journal: Journal | None
    original_title_is_zh: bool | None


class LanguageFacts(TypedDict):
    paper_id: str
    policy_version: str
    original_title_is_zh: bool | None
    sources: list[LanguageSource]


@with_config(ConfigDict(strict=True, extra="forbid"))
class LanguageResolution(LanguageFacts):
    status: ResolutionStatus


class FrozenLanguageBasis(LanguageFacts):
    status: Literal["frozen"]


class HistoricalLanguageBasis(TypedDict):
    status: Literal["historical_unrecorded"]
    original_title_is_zh: bool | None
    sources: list[LanguageSource]


LanguageBasis = FrozenLanguageBasis | HistoricalLanguageBasis


class LanguageObservation(LanguageResolution):
    resolution_id: str


class LanguageTrace(TypedDict):
    observations: tuple[LanguageObservation, ...]


policies = sa.Table(
    "title_language_policies",
    metadata,
    sa.Column("policy_version", sa.Text(), primary_key=True),
    sa.Column("mapping_json", sa.Text(), nullable=False),
)

bindings = sa.Table(
    "feed_journal_bindings",
    metadata,
    sa.Column(
        "feed_id", sa.String(36), sa.ForeignKey("feeds.feed_id"), primary_key=True
    ),
    sa.Column("journal", sa.Text(), nullable=False),
)
resolutions = sa.Table(
    "title_language_resolutions",
    metadata,
    sa.Column("resolution_id", sa.String(64), primary_key=True),
    sa.Column(
        "paper_id", sa.String(36), sa.ForeignKey("papers.paper_id"), nullable=False
    ),
    sa.Column(
        "policy_version",
        sa.Text(),
        sa.ForeignKey("title_language_policies.policy_version"),
        nullable=False,
    ),
    sa.Column("basis_json", sa.Text(), nullable=False),
)
frozen = sa.Table(
    "screening_language_basis",
    metadata,
    sa.Column(
        "budget_id",
        sa.String(36),
        sa.ForeignKey("screening_budgets.budget_id"),
        primary_key=True,
    ),
    sa.Column(
        "resolution_id",
        sa.String(64),
        sa.ForeignKey("title_language_resolutions.resolution_id"),
        nullable=False,
    ),
)
required = sa.Table(
    "screening_language_requirements",
    metadata,
    sa.Column(
        "budget_id",
        sa.String(36),
        sa.ForeignKey("screening_budgets.budget_id"),
        primary_key=True,
    ),
)
POLICIES = {"v1": {"dqkx": True, "aies": False, "jgr": False, "qjrms": False}}
# Exact registered canonical endpoints; other Feed identities require explicit binding.
ENDPOINTS = {item.url: item.journal for item in FEED_SUBSCRIPTIONS}


def _status(values: set[bool | None]) -> ResolutionStatus:
    if not values or None in values:
        return "missing"
    return "ambiguous" if len(values) > 1 else "resolved"


def checked_mapping(value: object) -> dict[Journal, bool]:
    """封闭期刊集合与严格 bool;不决定真实来源政策。"""
    if (
        type(value) is not dict
        or set(value) != set(POLICIES["v1"])
        or any(type(flag) is not bool for flag in value.values())
    ):
        raise ValueError("invalid language mapping")
    return cast(dict[Journal, bool], value)


def _policy_mapping(connection: Connection, version: str) -> dict[Journal, bool]:
    payload = connection.execute(
        select(policies.c.mapping_json).where(policies.c.policy_version == version)
    ).scalar_one_or_none()
    if payload is None:
        raise TaskError(TaskReason.CORRUPT_REFERENCE)
    try:
        mapping = checked_mapping(json.loads(payload))
        if version == "v1" and mapping != POLICIES["v1"]:
            raise ValueError("immutable v1 mapping")
        return mapping
    except (ValueError, TypeError):
        raise TaskError(TaskReason.CORRUPT_REFERENCE) from None


def _require_policy(connection: Connection, basis: LanguageResolution) -> None:
    mapping = _policy_mapping(connection, basis["policy_version"])
    if any(
        source["original_title_is_zh"]
        is not (mapping[source["journal"]] if source["journal"] is not None else None)
        for source in basis["sources"]
    ):
        raise TaskError(TaskReason.CORRUPT_REFERENCE)


def _require_sources(connection: Connection, basis: LanguageResolution) -> None:
    for source in basis["sources"]:
        found = connection.execute(
            select(feed_discoveries.c.discovery_id)
            .select_from(feed_discoveries.join(feed_entries).join(versions))
            .where(
                feed_discoveries.c.discovery_id == source["discovery_id"],
                feed_discoveries.c.feed_id == source["feed_id"],
                versions.c.paper_id == basis["paper_id"],
            )
        ).first()
        if found is None:
            raise TaskError(TaskReason.CORRUPT_REFERENCE)


def _read_resolution(connection: Connection, row: RowMapping) -> LanguageResolution:
    try:
        basis = _resolution_adapter.validate_json(row["basis_json"])
        if (
            hashlib.sha256(encode(basis).encode()).hexdigest() != row["resolution_id"]
            or basis["paper_id"] != row["paper_id"]
            or basis["policy_version"] != row["policy_version"]
        ):
            raise ValueError
        _require_policy(connection, basis)
        _require_sources(connection, basis)
        return basis
    except (ValueError, TypeError, KeyError):
        raise TaskError(TaskReason.CORRUPT_REFERENCE) from None


def _consistent_resolution(basis: LanguageResolution) -> LanguageResolution:
    values = {source["original_title_is_zh"] for source in basis["sources"]}
    expected = _status(values)
    if basis["status"] != expected or basis["original_title_is_zh"] is not (
        next(iter(values)) if expected == "resolved" else None
    ):
        raise ValueError("invalid language resolution")
    return basis


_resolution_adapter: TypeAdapter[LanguageResolution] = TypeAdapter(
    Annotated[LanguageResolution, AfterValidator(_consistent_resolution)]
)


def _checked_resolution(value: object) -> LanguageResolution:
    try:
        return _resolution_adapter.validate_python(value)
    except (ValueError, TypeError):
        raise TaskError(TaskReason.CORRUPT_REFERENCE) from None


def encode(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def derive(
    connection: Connection, paper_id: str, policy_version: str
) -> LanguageResolution:
    if type(policy_version) is not str or type(paper_id) is not str:
        raise TaskError(TaskReason.INVALID_REQUEST)
    if (
        connection.execute(
            select(papers.c.paper_id).where(papers.c.paper_id == paper_id)
        ).first()
        is None
    ):
        raise TaskError(TaskReason.INVALID_REQUEST)
    mapping_json = connection.execute(
        select(policies.c.mapping_json).where(
            policies.c.policy_version == policy_version
        )
    ).scalar_one_or_none()
    if mapping_json is None:
        raise TaskError(TaskReason.INVALID_REQUEST)
    mapping = _policy_mapping(connection, policy_version)
    sources: list[LanguageSource] = []
    query = (
        select(
            feed_discoveries.c.discovery_id,
            feeds.c.feed_id,
            feeds.c.url,
            bindings.c.journal,
        )
        .select_from(
            feed_discoveries.join(feed_entries)
            .join(versions)
            .join(feeds)
            .outerjoin(bindings)
        )
        .where(versions.c.paper_id == paper_id)
        .order_by(feed_discoveries.c.discovery_id)
    )
    for row in connection.execute(query).mappings():
        journal = row["journal"] or ENDPOINTS.get(row["url"])
        sources.append(
            {
                "discovery_id": row["discovery_id"],
                "feed_id": row["feed_id"],
                "journal": journal,
                "original_title_is_zh": mapping.get(journal)
                if journal is not None
                else None,
            }
        )
    values = {s["original_title_is_zh"] for s in sources}
    status = _status(values)
    return _checked_resolution(
        {
            "paper_id": paper_id,
            "policy_version": policy_version,
            "status": status,
            "original_title_is_zh": next(iter(values))
            if status == "resolved"
            else None,
            "sources": sources,
        }
    )


def retain(connection: Connection, basis: LanguageResolution) -> str:
    basis = _checked_resolution(basis)
    _require_policy(connection, basis)
    _require_sources(connection, basis)
    payload = encode(basis)
    identifier = hashlib.sha256(payload.encode()).hexdigest()
    if (
        connection.execute(
            select(resolutions.c.resolution_id).where(
                resolutions.c.resolution_id == identifier
            )
        ).first()
        is None
    ):
        connection.execute(
            resolutions.insert().values(
                resolution_id=identifier,
                paper_id=basis["paper_id"],
                policy_version=basis["policy_version"],
                basis_json=payload,
            )
        )
    return identifier


def load(connection: Connection, budget_id: str) -> LanguageBasis:
    budget = (
        connection.execute(select(budgets).where(budgets.c.budget_id == budget_id))
        .mappings()
        .one()
    )
    row = (
        connection.execute(
            select(resolutions).join(frozen).where(frozen.c.budget_id == budget_id)
        )
        .mappings()
        .first()
    )
    needs_basis = (
        connection.execute(
            select(required.c.budget_id).where(required.c.budget_id == budget_id)
        ).first()
        is not None
    )
    if needs_basis != (row is not None) or (needs_basis and budget["stage"] != "value"):
        raise TaskError(TaskReason.CORRUPT_REFERENCE)
    if row is None:
        return {
            "status": "historical_unrecorded",
            "original_title_is_zh": budget["original_title_is_zh"],
            "sources": [],
        }
    basis = _read_resolution(connection, row)
    if (
        basis["status"] != "resolved"
        or basis["paper_id"] != budget["paper_id"]
        or type(basis["original_title_is_zh"]) is not bool
        or basis["original_title_is_zh"] != budget["original_title_is_zh"]
        or not basis["sources"]
    ):
        raise TaskError(TaskReason.CORRUPT_REFERENCE)
    return {**basis, "status": "frozen"}


def validate(connection: Connection) -> None:
    for version in connection.execute(select(policies.c.policy_version)).scalars():
        _policy_mapping(connection, version)
    for identifier in connection.execute(
        select(frozen.c.budget_id).union(select(required.c.budget_id))
    ).scalars():
        load(connection, identifier)
    for paper_id in connection.execute(
        select(resolutions.c.paper_id).distinct()
    ).scalars():
        observations(connection, paper_id)


def observations(
    connection: Connection, paper_id: str
) -> tuple[LanguageObservation, ...]:
    results: list[LanguageObservation] = []
    for row in connection.execute(
        select(resolutions)
        .where(resolutions.c.paper_id == paper_id)
        .order_by(resolutions.c.resolution_id)
    ).mappings():
        basis = _read_resolution(connection, row)
        results.append({**basis, "resolution_id": row["resolution_id"]})
    return tuple(results)
