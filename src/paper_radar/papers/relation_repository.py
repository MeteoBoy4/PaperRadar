"""关系来源事实与派生归属查询;不移动已存版本。"""

import re
from typing import Literal
from uuid import uuid4

from sqlalchemy import Connection, or_, select
from sqlalchemy.engine import RowMapping

from paper_radar.papers.doi import normalize_doi
from paper_radar.papers.errors import PaperError, PaperReason
from paper_radar.papers.fact_reads import material_request_matches
from paper_radar.papers.models import (
    NormalizedRelation,
    ObservationInput,
    RelationFact,
    RelationInput,
)
from paper_radar.papers.read_checks import _utc, _uuid, corrupt
from paper_radar.papers.relations import relation_state
from paper_radar.papers.tables import (
    acquisitions,
    identifiers,
    observations,
    relation_references,
    version_relations,
    versions,
)
from paper_radar.papers.text import require_public_url
from paper_radar.papers.text_rules import normalize_text
from paper_radar.storage.schema import artifact_members, artifacts


def matching_relation(connection: Connection, relation: RelationInput) -> str | None:
    return connection.execute(
        select(version_relations.c.relation_id).where(
            version_relations.c.preprint_doi == relation.source_doi,
            version_relations.c.journal_doi == relation.target_doi,
        )
    ).scalar_one_or_none()


def has_new_relations(connection: Connection, item: ObservationInput) -> bool:
    return any(
        matching_relation(connection, NormalizedRelation.model_validate(value)) is None
        for value in item.relations
    )


def related_papers(
    connection: Connection, doi: str, item: ObservationInput
) -> set[str]:
    endpoints: set[str] = set()
    for row in connection.execute(
        select(version_relations).where(
            or_(
                version_relations.c.preprint_doi == doi,
                version_relations.c.journal_doi == doi,
            )
        )
    ).mappings():
        endpoints.update((row["preprint_doi"], row["journal_doi"]))
    for value in item.relations:
        relation = NormalizedRelation.model_validate(value)
        endpoints.update((relation.source_doi, relation.target_doi))
    endpoints.discard(doi)
    return set(
        connection.execute(
            select(identifiers.c.paper_id).where(
                identifiers.c.normalized_value.in_(endpoints)
            )
        ).scalars()
    )


def save_relations(
    connection: Connection,
    item: ObservationInput,
    acquisition_id: str,
    artifact_id: str | None,
) -> bool:
    retained = False
    for value in item.relations:
        relation = NormalizedRelation.model_validate(value)
        relation_id = matching_relation(connection, relation)
        if relation_id is None:
            if artifact_id is None:
                raise corrupt()
            relation_id = str(uuid4())
            connection.execute(
                version_relations.insert().values(
                    relation_id=relation_id,
                    preprint_doi=relation.source_doi,
                    journal_doi=relation.target_doi,
                    acquisition_id=acquisition_id,
                    artifact_id=artifact_id,
                    locator=relation.locator,
                )
            )
            retained = True
        connection.execute(
            relation_references.insert().values(
                acquisition_id=acquisition_id,
                relation_id=relation_id,
                raw_source_doi=relation.raw_source_doi,
                raw_target_doi=relation.raw_target_doi,
                raw_kind=relation.raw_kind,
                locator=relation.locator,
            )
        )
    return retained


def relation_roles(connection: Connection) -> dict[str, str]:
    """即使端点未登记,全部保留关系也必须声明同一种版本类别。"""
    expected: dict[str, str] = {}
    for preprint, journal in connection.execute(
        select(version_relations.c.preprint_doi, version_relations.c.journal_doi)
    ):
        for doi, kind in ((preprint, "preprint"), (journal, "journal")):
            if doi in expected and expected[doi] != kind:
                raise corrupt()
            expected[doi] = kind
    return expected


def load_relations(
    connection: Connection, paper_id: str | None = None
) -> tuple[RelationFact, ...]:
    relation_roles(connection)
    result = []
    for row in connection.execute(select(version_relations)).mappings():
        _uuid(row["relation_id"])
        acquired = (
            connection.execute(
                select(acquisitions).where(
                    acquisitions.c.acquisition_id == row["acquisition_id"]
                )
            )
            .mappings()
            .one()
        )
        _uuid(acquired["acquisition_id"])
        _utc(acquired["observed_at"])
        if acquired["source_kind"] not in {"publisher", "registry"} or acquired[
            "doi"
        ] not in {row["preprint_doi"], row["journal_doi"]}:
            raise corrupt()
        if (acquired["doi"] == row["preprint_doi"]) != (
            acquired["version_kind"] == "preprint"
        ):
            raise corrupt()
        if (
            not normalize_text(row["locator"])
            or normalize_text(row["locator"]) != row["locator"]
            or len(row["locator"].encode()) > 2048
            or row["preprint_doi"] == row["journal_doi"]
            or any(
                normalize_doi(row[key]) != row[key]
                for key in ("preprint_doi", "journal_doi")
            )
        ):
            raise corrupt()
        material = connection.execute(
            select(artifacts.c.kind, artifact_members.c.sha256)
            .join(
                artifact_members,
                artifacts.c.artifact_id == artifact_members.c.artifact_id,
            )
            .where(
                artifacts.c.artifact_id == row["artifact_id"],
                artifact_members.c.role == "payload",
            )
        ).one()
        if (
            material.kind != "source_snapshot"
            or material.sha256 != acquired["payload_sha256"]
        ):
            raise corrupt()
        if (
            connection.execute(
                select(relation_references).where(
                    relation_references.c.relation_id == row["relation_id"],
                    relation_references.c.acquisition_id == row["acquisition_id"],
                )
            ).first()
            is None
        ):
            raise corrupt()
        endpoints = []
        for key, kind in (("preprint_doi", "preprint"), ("journal_doi", "journal")):
            endpoint = (
                connection.execute(
                    select(
                        identifiers.c.version_id,
                        identifiers.c.paper_id,
                        versions.c.version_kind,
                    )
                    .join(versions, versions.c.version_id == identifiers.c.version_id)
                    .where(identifiers.c.normalized_value == row[key])
                )
                .mappings()
                .first()
            )
            if endpoint and endpoint["version_kind"] != kind:
                raise corrupt()
            endpoints.append(endpoint)
        pre, journal = endpoints
        if paper_id is not None and not any(
            endpoint and endpoint["paper_id"] == paper_id for endpoint in endpoints
        ):
            continue
        result.append(
            RelationFact.model_validate(
                {
                    "relation_id": row["relation_id"],
                    "preprint_doi": row["preprint_doi"],
                    "journal_doi": row["journal_doi"],
                    "preprint_version_id": pre["version_id"] if pre else None,
                    "preprint_paper_id": pre["paper_id"] if pre else None,
                    "journal_version_id": journal["version_id"] if journal else None,
                    "journal_paper_id": journal["paper_id"] if journal else None,
                    "state": relation_state(
                        pre["paper_id"] if pre else None,
                        journal["paper_id"] if journal else None,
                    ),
                    **{
                        key: acquired[key]
                        for key in (
                            "acquisition_id",
                            "source_kind",
                            "provider",
                            "query_key",
                            "observed_at",
                            "parser_version",
                        )
                    },
                    "artifact_id": row["artifact_id"],
                    "locator": row["locator"],
                    "assertions": relation_assertions(connection, row),
                }
            )
        )
    return tuple(
        sorted(
            result,
            key=lambda item: (item.preprint_doi, item.journal_doi, item.relation_id),
        )
    )


def validate_relation_references(connection: Connection) -> None:
    load_relations(connection)
    for ref in connection.execute(select(relation_references)).mappings():
        acquired = (
            connection.execute(
                select(acquisitions).where(
                    acquisitions.c.acquisition_id == ref["acquisition_id"]
                )
            )
            .mappings()
            .one()
        )
        relation = (
            connection.execute(
                select(version_relations).where(
                    version_relations.c.relation_id == ref["relation_id"]
                )
            )
            .mappings()
            .one()
        )
        validate_assertion(connection, ref, relation, acquired)
    interpretations: dict[tuple[object, ...], tuple[tuple[str, str, str], ...]] = {}
    for acquired in connection.execute(select(acquisitions)).mappings():
        key = tuple(
            acquired[name]
            for name in (
                "doi",
                "version_kind",
                "source_kind",
                "provider",
                "query_key",
                "payload_sha256",
                "parser_version",
            )
        )
        signature = saved_relation_signature(connection, acquired["acquisition_id"])
        if key in interpretations and interpretations[key] != signature:
            raise corrupt()
        interpretations[key] = signature


def validate_assertion(
    connection: Connection, ref: RowMapping, relation: RowMapping, acquired: RowMapping
) -> None:
    _uuid(acquired["acquisition_id"])
    _utc(acquired["observed_at"])
    require_public_url(ref["locator"])
    if acquired["response_bytes_retained"] != (
        response_artifact(connection, acquired) is not None
    ):
        raise corrupt()
    for key in ("provider", "query_key"):
        require_public_url(acquired[key])
        if not normalize_text(acquired[key]) or len(acquired[key].encode()) > 2048:
            raise corrupt()
    if (
        acquired["parser_version"] < 1
        or re.fullmatch(r"[0-9a-f]{64}", acquired["payload_sha256"]) is None
    ):
        raise corrupt()
    if (
        acquired["source_kind"] == "registry"
        and normalize_doi(acquired["query_key"]) != acquired["doi"]
    ):
        raise corrupt()
    if acquired["version_id"] is not None:
        endpoint = connection.execute(
            select(identifiers.c.normalized_value).where(
                identifiers.c.version_id == acquired["version_id"]
            )
        ).scalar_one_or_none()
        if endpoint != acquired["doi"]:
            raise corrupt()

    if ref["raw_kind"] not in {"is-preprint-of", "has-preprint"}:
        raise corrupt()
    raw_pre, raw_journal = (
        (ref["raw_source_doi"], ref["raw_target_doi"])
        if ref["raw_kind"] == "is-preprint-of"
        else (ref["raw_target_doi"], ref["raw_source_doi"])
    )
    if (
        normalize_doi(raw_pre) != relation["preprint_doi"]
        or normalize_doi(raw_journal) != relation["journal_doi"]
    ):
        raise corrupt()
    if (
        acquired["source_kind"] not in {"publisher", "registry"}
        or acquired["doi"] not in {relation["preprint_doi"], relation["journal_doi"]}
        or (acquired["doi"] == relation["preprint_doi"])
        != (acquired["version_kind"] == "preprint")
        or not normalize_text(ref["locator"])
        or normalize_text(ref["locator"]) != ref["locator"]
        or len(ref["locator"].encode()) > 2048
    ):
        raise corrupt()


def validate_endpoint_kinds(
    connection: Connection, item: ObservationInput, doi: str
) -> None:
    expected = relation_roles(connection)
    for value in item.relations:
        relation = NormalizedRelation.model_validate(value)
        for endpoint_doi, kind in (
            (relation.source_doi, "preprint"),
            (relation.target_doi, "journal"),
        ):
            if endpoint_doi in expected and expected[endpoint_doi] != kind:
                raise PaperError(
                    PaperReason.INVALID_RELATION, path="relations.version_kind"
                )
            expected[endpoint_doi] = kind
    for endpoint_doi, kind in expected.items():
        actual = connection.execute(
            select(versions.c.version_kind)
            .join(identifiers, versions.c.version_id == identifiers.c.version_id)
            .where(identifiers.c.normalized_value == endpoint_doi)
        ).scalar_one_or_none()
        if (actual is not None and actual != kind) or (
            endpoint_doi == doi and item.version_kind != kind
        ):
            raise PaperError(
                PaperReason.INVALID_RELATION, path="relations.version_kind"
            )


def has_relations(connection: Connection, doi: str) -> bool:
    return (
        connection.execute(
            select(version_relations.c.relation_id).where(
                or_(
                    version_relations.c.preprint_doi == doi,
                    version_relations.c.journal_doi == doi,
                )
            )
        ).first()
        is not None
    )


def saved_relation_signature(
    connection: Connection, acquisition_id: str
) -> tuple[tuple[str, str, str], ...]:
    return tuple(
        sorted(
            set(
                connection.execute(
                    select(
                        version_relations.c.preprint_doi,
                        version_relations.c.journal_doi,
                        relation_references.c.locator,
                    )
                    .join(
                        relation_references,
                        relation_references.c.relation_id
                        == version_relations.c.relation_id,
                    )
                    .where(relation_references.c.acquisition_id == acquisition_id)
                ).tuples()
            )
        )
    )


def save_acquisition_result(
    connection: Connection, acquisition_id: str, doi: str | None, retained: bool
) -> tuple[Literal["retained", "not_retained"], PaperReason | None]:
    """字段与 Feed 共用关系冲突成功语义,材料保留仍由各写路径判定。"""
    connection.execute(
        acquisitions.update()
        .where(acquisitions.c.acquisition_id == acquisition_id)
        .values(response_bytes_retained=retained)
    )
    requires_merge = any(
        relation.state == "requires_merge"
        for relation in load_relations(connection)
        if doi in {relation.preprint_doi, relation.journal_doi}
    )
    reason = (
        PaperReason.REQUIRES_MERGE
        if requires_merge
        else None
        if retained
        else PaperReason.NOT_RETAINED
    )
    status: Literal["retained", "not_retained"] = (
        "retained" if retained or requires_merge else "not_retained"
    )
    connection.execute(
        acquisitions.update()
        .where(acquisitions.c.acquisition_id == acquisition_id)
        .values(
            result_status=status,
            result_reason=reason.value if reason else None,
            response_bytes_retained=retained,
        )
    )
    return status, reason


def retained_relation_result(connection: Connection, row: RowMapping) -> bool:
    if row["result_reason"] == "requires_merge":
        return any(
            relation.state == "requires_merge"
            for relation in load_relations(connection)
            if row["doi"] in {relation.preprint_doi, relation.journal_doi}
        )
    return (
        connection.execute(
            select(relation_references).where(
                relation_references.c.acquisition_id == row["acquisition_id"]
            )
        ).first()
        is not None
    )


def relation_assertions(
    connection: Connection, relation: RowMapping
) -> tuple[dict[str, object], ...]:
    result = []
    for ref in connection.execute(
        select(relation_references)
        .where(relation_references.c.relation_id == relation["relation_id"])
        .order_by(
            relation_references.c.acquisition_id,
            relation_references.c.raw_kind,
            relation_references.c.raw_source_doi,
            relation_references.c.raw_target_doi,
            relation_references.c.locator,
        )
    ).mappings():
        acquired = (
            connection.execute(
                select(acquisitions).where(
                    acquisitions.c.acquisition_id == ref["acquisition_id"]
                )
            )
            .mappings()
            .one()
        )
        validate_assertion(connection, ref, relation, acquired)
        result.append(
            {
                **{
                    key: ref[key]
                    for key in (
                        "acquisition_id",
                        "raw_source_doi",
                        "raw_target_doi",
                        "raw_kind",
                        "locator",
                    )
                },
                **{
                    key: acquired[key]
                    for key in (
                        "source_kind",
                        "provider",
                        "query_key",
                        "observed_at",
                        "parser_version",
                        "payload_sha256",
                        "response_bytes_retained",
                    )
                },
                "artifact_id": response_artifact(connection, acquired),
            }
        )
    return tuple(result)


def relation_material_retained(connection: Connection, acquisition_id: str) -> bool:
    return (
        connection.execute(
            select(version_relations.c.relation_id).where(
                version_relations.c.acquisition_id == acquisition_id
            )
        ).first()
        is not None
    )


def response_artifact(connection: Connection, acquired: RowMapping) -> str | None:
    relation_artifact = (
        connection.execute(
            select(version_relations.c.artifact_id).where(
                version_relations.c.acquisition_id == acquired["acquisition_id"]
            )
        )
        .scalars()
        .first()
    )
    if relation_artifact is not None:
        return str(relation_artifact)
    if acquired["source_observation_id"] is not None:
        source = (
            connection.execute(
                select(observations).where(
                    observations.c.observation_id == acquired["source_observation_id"]
                )
            )
            .mappings()
            .one_or_none()
        )
        if source is not None and material_request_matches(source, acquired):
            return str(source["artifact_id"])
    return None
