"""一致视图下重建候选与取得事实双引用,验证完整历史。"""

import re
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import Connection, select
from sqlalchemy.engine import RowMapping

from paper_radar.papers.doi import normalize_doi
from paper_radar.papers.errors import PaperError, PaperReason
from paper_radar.papers.models import (
    AbstractValue,
    AcquisitionFact,
    CandidateInput,
    DateValue,
    DiscoveryFact,
    FieldFact,
    ObservationFact,
    PaperTrace,
    PaperView,
    RevisionFact,
    SelectionFact,
    VersionKind,
)
from paper_radar.papers.rules import RankedObservation, choose_fields, digest
from paper_radar.papers.tables import (
    acquisitions,
    authors,
    candidates,
    feed_entries,
    feeds,
    identifiers,
    observations,
    papers,
    revision_fields,
    revisions,
    selections,
    versions,
)
from paper_radar.papers.text import normalize_fields, require_public_url
from paper_radar.storage.schema import artifact_members, artifacts


def corrupt() -> PaperError:
    return PaperError(PaperReason.CORRUPT_REFERENCE)


def _utc(value: str) -> None:
    instant = datetime.fromisoformat(value)
    if (
        instant.tzinfo is None
        or instant.astimezone(UTC).isoformat(timespec="microseconds") != value
    ):
        raise corrupt()


def _uuid(value: str) -> None:
    if str(UUID(value)) != value:
        raise corrupt()


def _candidate(
    connection: Connection, candidate_id: str, acquisition_id: str | None = None
) -> tuple[str, FieldFact]:
    row = (
        connection.execute(
            select(candidates).where(candidates.c.candidate_id == candidate_id)
        )
        .mappings()
        .one()
    )
    _uuid(candidate_id)
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
    return dict(_candidate(connection, candidate_id) for candidate_id in ids)


def _acquisition(row: RowMapping) -> AcquisitionFact:
    _uuid(row["acquisition_id"])
    _utc(row["observed_at"])
    if row["source_kind"] == "publisher":
        require_public_url(row["provider"])
        require_public_url(row["query_key"])
    if (
        (row["doi"] is not None and normalize_doi(row["doi"]) != row["doi"])
        or (row["source_kind"] == "publisher" and row["doi"] is None)
        or (row["raw_doi"] is not None and normalize_doi(row["raw_doi"]) != row["doi"])
        or row["source_kind"] not in {"publisher", "feed"}
        or row["version_kind"] not in {"journal", "preprint"}
    ):
        raise corrupt()
    if row["parser_version"] < 1 or any(
        re.fullmatch(r"[0-9a-f]{64}", row[name]) is None
        for name in ("payload_sha256", "interpretation_sha256", "parsed_sha256")
    ):
        raise corrupt()
    return AcquisitionFact.model_validate(
        {key: row[key] for key in AcquisitionFact.model_fields}
    )


def _material_key(row: RowMapping) -> tuple[str, str, str, str, str, str]:
    return (
        row["doi"],
        row["version_kind"],
        row["source_kind"],
        row["provider"],
        row["query_key"],
        row["payload_sha256"],
    )


def _validate_parser_history(
    connection: Connection, rows: tuple[RowMapping, ...], doi: str | None, kind: str
) -> None:
    unbound = (
        connection.execute(
            select(acquisitions).where(
                acquisitions.c.version_id.is_(None),
                acquisitions.c.doi == doi,
                acquisitions.c.version_kind == kind,
            )
        )
        .mappings()
        .all()
    )
    highest: dict[tuple[str, ...], int] = {}
    interpretations: dict[tuple[tuple[str, ...], int], str] = {}
    for row in (*unbound, *rows):
        key = _material_key(row)
        version = row["parser_version"]
        identity = (key, version)
        if (row["version_id"] is not None and version < highest.get(key, 0)) or (
            identity in interpretations
            and interpretations[identity] != row["parsed_sha256"]
        ):
            raise corrupt()
        highest[key] = max(highest.get(key, 0), version)
        interpretations[identity] = row["parsed_sha256"]


def validate_unbound_acquisitions(connection: Connection) -> None:
    """空观察也有可回放重试结果,但不得制造空论文身份。"""
    try:
        interpretations: dict[tuple[tuple[str, ...], int], str] = {}
        for row in connection.execute(
            select(acquisitions).where(acquisitions.c.version_id.is_(None))
        ).mappings():
            item = _acquisition(row)
            identity = (_material_key(row), item.parser_version)
            if (
                identity in interpretations
                and interpretations[identity] != item.parsed_sha256
            ):
                raise corrupt()
            interpretations[identity] = item.parsed_sha256
            if (
                item.source_observation_id is not None
                or item.event_no is not None
                or item.response_bytes_retained
                or item.result_status != "not_retained"
                or item.result_revision_no is not None
            ):
                raise corrupt()
    except (ValueError, TypeError, KeyError, PaperError):
        raise corrupt() from None


def load_trace(connection: Connection, paper_id: str) -> PaperTrace:
    if (
        connection.execute(
            select(papers.c.paper_id).where(papers.c.paper_id == paper_id)
        ).first()
        is None
    ):
        raise PaperError(PaperReason.PAPER_NOT_FOUND, path="paper_id")
    try:
        _uuid(paper_id)
        version_rows = (
            connection.execute(
                select(versions)
                .where(versions.c.paper_id == paper_id)
                .order_by(versions.c.version_id)
            )
            .mappings()
            .all()
        )
        selection_rows = (
            connection.execute(
                select(selections).where(selections.c.paper_id == paper_id)
            )
            .mappings()
            .all()
        )
        if len(selection_rows) != 1 or not version_rows:
            raise corrupt()
        selection = SelectionFact.model_validate(
            {key: selection_rows[0][key] for key in SelectionFact.model_fields}
        )
        _uuid(selection.selection_id)
        _utc(selection.selected_at)
        all_sources, all_acquired, all_revisions, views = [], [], [], []
        all_discoveries: list[DiscoveryFact] = []
        for version in version_rows:
            version_id = version["version_id"]
            _uuid(version_id)
            identity = (
                connection.execute(
                    select(identifiers).where(identifiers.c.version_id == version_id)
                )
                .mappings()
                .all()
            )
            if len(identity) > 1 or (
                identity
                and (
                    identity[0]["paper_id"] != paper_id
                    or identity[0]["scheme"] != "doi"
                    or normalize_doi(identity[0]["normalized_value"])
                    != identity[0]["normalized_value"]
                )
            ):
                raise corrupt()
            if (
                not identity
                and connection.execute(
                    select(feed_entries).where(feed_entries.c.version_id == version_id)
                ).first()
                is None
            ):
                raise corrupt()
            doi = identity[0]["normalized_value"] if identity else None
            from paper_radar.papers.feed_queries import load_discoveries

            all_discoveries.extend(load_discoveries(connection, version_id))
            source_rows = (
                connection.execute(
                    select(observations)
                    .where(observations.c.version_id == version_id)
                    .order_by(
                        observations.c.observed_at,
                        observations.c.payload_sha256,
                        observations.c.parser_version,
                    )
                )
                .mappings()
                .all()
            )
            source_fields = {}
            for row in source_rows:
                _uuid(row["observation_id"])
                _utc(row["observed_at"])
                source = connection.execute(
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
                    source.kind != "source_snapshot"
                    or source.sha256 != row["payload_sha256"]
                ):
                    raise corrupt()
                fields = observation_fields(connection, row["observation_id"])
                if (not fields and row["source_kind"] != "feed") or digest(
                    {
                        name: CandidateInput(value=fact.value, locator=fact.locator)
                        for name, fact in fields.items()
                    }
                ) != row["candidate_sha256"]:
                    raise corrupt()
                source_fields[row["observation_id"]] = fields
                all_sources.append(
                    ObservationFact.model_validate(
                        {
                            **{
                                key: row[key]
                                for key in ObservationFact.model_fields
                                if key != "fields"
                            },
                            "fields": fields,
                        }
                    )
                )
            event_rows = (
                connection.execute(
                    select(acquisitions)
                    .where(acquisitions.c.version_id == version_id)
                    .order_by(acquisitions.c.event_no)
                )
                .mappings()
                .all()
            )
            _validate_parser_history(
                connection, tuple(event_rows), doi, version["version_kind"]
            )
            if [row["event_no"] for row in event_rows] != list(
                range(1, len(event_rows) + 1)
            ):
                raise corrupt()
            sources_by_id = {row["observation_id"]: row for row in source_rows}
            creators = set()
            ranks = []
            previous_winners: dict[str, tuple[str, str]] = {}
            expected_history: list[tuple[str, dict[str, tuple[str, str]]]] = []
            for row in event_rows:
                acquired = _acquisition(row)
                if (
                    acquired.doi != doi
                    and not (acquired.source_kind == "feed" and acquired.doi is None)
                ) or row["version_kind"] != version["version_kind"]:
                    raise corrupt()
                all_acquired.append(acquired)
                source_id = acquired.source_observation_id
                if source_id:
                    material = sources_by_id.get(source_id)
                    if material is None or (
                        material["source_kind"],
                        material["provider"],
                        material["query_key"],
                    ) != (
                        acquired.source_kind,
                        acquired.provider,
                        acquired.query_key,
                    ):
                        raise corrupt()
                    if acquired.response_bytes_retained:
                        if (
                            source_id in creators
                            or (
                                material["observed_at"],
                                material["payload_sha256"],
                                material["parser_version"],
                            )
                            != (
                                acquired.observed_at,
                                acquired.payload_sha256,
                                acquired.parser_version,
                            )
                            or acquired.result_status != "retained"
                        ):
                            raise corrupt()
                        creators.add(source_id)
                    elif acquired.result_status != "not_retained":
                        raise corrupt()
                    ranks.append(
                        RankedObservation(
                            acquired.observed_at,
                            acquired.payload_sha256,
                            acquired.parser_version,
                            {
                                name: (fact.candidate_id, acquired.acquisition_id)
                                for name, fact in source_fields[source_id].items()
                            },
                            source_kind=row["source_kind"],
                            stream=source_stream(connection, row),
                        )
                    )
                elif (
                    acquired.response_bytes_retained
                    or acquired.result_status != "not_retained"
                ):
                    raise corrupt()
                winners = choose_fields(tuple(ranks))
                if winners != previous_winners or not expected_history:
                    expected_history.append((acquired.acquisition_id, winners))
                    previous_winners = winners
                if acquired.result_revision_no != len(expected_history):
                    raise corrupt()
            if creators != set(sources_by_id):
                raise corrupt()
            revision_rows = (
                connection.execute(
                    select(revisions)
                    .where(revisions.c.version_id == version_id)
                    .order_by(revisions.c.revision_no)
                )
                .mappings()
                .all()
            )
            if not revision_rows or [
                row["revision_no"] for row in revision_rows
            ] != list(range(1, len(expected_history) + 1)):
                raise corrupt()
            for row, (trigger, expected_winners) in zip(
                revision_rows, expected_history, strict=True
            ):
                _utc(row["revised_at"])
                if row["acquisition_id"] != trigger:
                    raise corrupt()
                fields = {}
                for ref in connection.execute(
                    select(revision_fields).where(
                        revision_fields.c.version_id == version_id,
                        revision_fields.c.revision_no == row["revision_no"],
                    )
                ).mappings():
                    name, fact = _candidate(
                        connection, ref["candidate_id"], ref["acquisition_id"]
                    )
                    if name != ref["field_name"] or ref["rule_version"] != 1:
                        raise corrupt()
                    fields[name] = fact
                if {
                    name: (fact.candidate_id, fact.acquisition_id)
                    for name, fact in fields.items()
                } != expected_winners:
                    raise corrupt()
                all_revisions.append(
                    RevisionFact(
                        version_id=version_id,
                        revision_no=row["revision_no"],
                        revised_at=row["revised_at"],
                        fields=fields,
                    )
                )
            latest = all_revisions[-1]
            views.append(
                PaperView(
                    paper_id=paper_id,
                    version_id=version_id,
                    revision_no=latest.revision_no,
                    version_kind=cast(VersionKind, version["version_kind"]),
                    doi=doi,
                    fields=latest.fields,
                    selection=selection,
                )
            )
        current = next(
            (view for view in views if view.version_id == selection.version_id), None
        )
        if current is None:
            raise corrupt()
        return PaperTrace(
            current=current,
            versions=tuple(views),
            revisions=tuple(all_revisions),
            selections=(selection,),
            observations=tuple(all_sources),
            discoveries=tuple(all_discoveries),
            acquisitions=tuple(
                sorted(
                    all_acquired,
                    key=lambda event: (
                        event.observed_at,
                        event.payload_sha256,
                        event.parser_version,
                    ),
                )
            ),
        )
    except (ValueError, TypeError, KeyError, StopIteration, PaperError):
        raise corrupt() from None
