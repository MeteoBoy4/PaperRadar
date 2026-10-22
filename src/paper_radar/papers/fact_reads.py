"""从单个连接重建字段与来源流;不依赖聚合查询或写服务。"""

from sqlalchemy import Connection, select
from sqlalchemy.engine import RowMapping

from paper_radar.papers.models import (
    AbstractValue,
    CandidateInput,
    DateValue,
    FieldFact,
)
from paper_radar.papers.read_checks import corrupt, require_uuid
from paper_radar.papers.tables import (
    acquisitions,
    authors,
    candidates,
    feeds,
    observations,
)
from paper_radar.papers.text import normalize_fields, require_public_url


def load_candidate(
    connection: Connection, candidate_id: str, acquisition_id: str | None = None
) -> tuple[str, FieldFact]:
    row = (
        connection.execute(
            select(candidates).where(candidates.c.candidate_id == candidate_id)
        )
        .mappings()
        .one()
    )
    require_uuid(candidate_id)
    name = row["field_name"]
    value: str | tuple[str, ...] | AbstractValue | DateValue
    if name == "abstract":
        value = AbstractValue(
            text=row["text_value"],
            is_truncated=row["is_truncated"],
            rule=row["abstract_rule"],
        )
    elif name == "authors":
        members = (
            connection.execute(
                select(authors)
                .where(authors.c.candidate_id == candidate_id)
                .order_by(authors.c.ordinal)
            )
            .mappings()
            .all()
        )
        if (
            not members
            or [r["ordinal"] for r in members] != list(range(len(members)))
            or row["text_value"] is not None
        ):
            raise corrupt()
        value = tuple(r["name"] for r in members)
    elif name in {"online_date", "print_date"}:
        value = DateValue.model_validate(
            {"value": row["text_value"], "precision": row["date_precision"]}
        )
    else:
        value = row["text_value"]
    source = (
        connection.execute(
            select(observations).where(
                observations.c.observation_id == row["observation_id"]
            )
        )
        .mappings()
        .one()
    )
    acquired = (
        connection.execute(
            select(acquisitions).where(acquisitions.c.acquisition_id == acquisition_id)
        )
        .mappings()
        .one()
        if acquisition_id
        else source
    )
    if acquisition_id and (
        acquired["source_observation_id"] != source["observation_id"]
        or acquired["version_id"] != source["version_id"]
    ):
        raise corrupt()
    if source["source_kind"] == "publisher":
        require_public_url(source["provider"])
        require_public_url(source["query_key"])
    fact = FieldFact(
        acquisition_id=acquisition_id,
        source_observed_at=source["observed_at"],
        source_kind=source["source_kind"],
        provider=source["provider"],
        query_key=source["query_key"],
        observed_at=acquired["observed_at"],
        parser_version=acquired["parser_version"],
        artifact_id=source["artifact_id"],
        candidate_id=candidate_id,
        observation_id=source["observation_id"],
        value=value,
        locator=row["locator"],
        text_norm=row["text_norm"],
    )
    normalized = normalize_fields(
        {name: CandidateInput(value=fact.value, locator=fact.locator)}
    )
    if name not in normalized or normalized[name].value != value:
        raise corrupt()
    if name != "abstract" and (
        row["is_truncated"] is not None or row["abstract_rule"] is not None
    ):
        raise corrupt()
    if name not in {"online_date", "print_date"} and row["date_precision"] is not None:
        raise corrupt()
    return name, fact


def source_stream(connection: Connection, row: RowMapping) -> tuple[str, str]:
    provider = row["provider"]
    if row["source_kind"] == "feed":
        provider = connection.execute(
            select(feeds.c.url).where(feeds.c.feed_id == provider)
        ).scalar_one()
    return provider, row["query_key"]


def observation_fields(
    connection: Connection, observation_id: str
) -> dict[str, FieldFact]:
    ids = connection.execute(
        select(candidates.c.candidate_id)
        .where(candidates.c.observation_id == observation_id)
        .order_by(candidates.c.field_name)
    ).scalars()
    return dict(load_candidate(connection, candidate_id) for candidate_id in ids)


def material_request_matches(material: RowMapping, acquired: RowMapping) -> bool:
    """材料所属请求身份,独立于公开的整次响应保留标志。"""
    return all(
        material[key] == acquired[key]
        for key in (
            "version_id",
            "source_kind",
            "provider",
            "query_key",
            "observed_at",
            "payload_sha256",
            "parser_version",
        )
    )
