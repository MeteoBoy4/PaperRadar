"""论文观察写事务:身份核对、候选保留与引用式修订。"""

import hashlib
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Connection, Engine, func, select
from sqlalchemy.engine import RowMapping
from sqlalchemy.sql.elements import ColumnElement

from paper_radar.papers.errors import PaperError, PaperReason
from paper_radar.papers.models import (
    AbstractValue,
    CandidateInput,
    ConflictKind,
    DateValue,
    ObservationInput,
    WriteResult,
)
from paper_radar.papers.rules import (
    RankedObservation,
    choose_fields,
    digest,
    interpretation_digest,
)
from paper_radar.papers.tables import (
    acquisitions,
    authors,
    candidates,
    identifiers,
    observations,
    papers,
    revision_fields,
    revisions,
    selections,
    versions,
)


def timestamp(item: ObservationInput) -> str:
    return item.observed_at.astimezone(UTC).isoformat(timespec="microseconds")


def _conflict(category: ConflictKind) -> WriteResult:
    return WriteResult(
        status="rejected", reason=PaperReason.IDENTITY_CONFLICT, conflict=category
    )


def _insert_candidates(
    connection: Connection, observation_id: str, fields: dict[str, CandidateInput]
) -> None:
    for name, candidate in fields.items():
        candidate_id = str(uuid4())
        value = candidate.value
        connection.execute(
            candidates.insert().values(
                candidate_id=candidate_id,
                observation_id=observation_id,
                field_name=name,
                locator=candidate.locator,
                text_norm=1,
                text_value=value.text
                if isinstance(value, AbstractValue)
                else value.value
                if isinstance(value, DateValue)
                else value
                if isinstance(value, str)
                else None,
                is_truncated=value.is_truncated
                if isinstance(value, AbstractValue)
                else None,
                abstract_rule=value.rule if isinstance(value, AbstractValue) else None,
                date_precision=value.precision
                if isinstance(value, DateValue)
                else None,
            )
        )
        if isinstance(value, tuple):
            for ordinal, author in enumerate(value):
                connection.execute(
                    authors.insert().values(
                        candidate_id=candidate_id, ordinal=ordinal, name=author
                    )
                )


def request_key(item: ObservationInput, doi: str) -> tuple[ColumnElement[bool], ...]:
    return (
        acquisitions.c.doi == doi,
        acquisitions.c.source_kind == item.source_kind,
        acquisitions.c.provider == item.provider,
        acquisitions.c.query_key == item.query_key,
        acquisitions.c.observed_at == timestamp(item),
        acquisitions.c.payload_sha256 == hashlib.sha256(item.payload).hexdigest(),
        acquisitions.c.parser_version == item.parser_version,
    )


def needs_source(
    engine: Engine, item: ObservationInput, doi: str, fields: dict[str, CandidateInput]
) -> bool:
    """只读发布计划;候选只追加,复用依据不会被另一写者删除。"""
    if not fields:
        return False
    with engine.connect() as connection:
        connection.exec_driver_sql("BEGIN")
        if connection.execute(
            select(acquisitions.c.acquisition_id).where(*request_key(item, doi))
        ).first():
            return False
        source = connection.execute(
            select(observations.c.observation_id)
            .join(identifiers, observations.c.version_id == identifiers.c.version_id)
            .where(
                identifiers.c.normalized_value == doi,
                observations.c.provider == item.provider,
                observations.c.query_key == item.query_key,
                observations.c.candidate_sha256 == digest(fields),
            )
        ).first()
        return source is None


def _saved_result(connection: Connection, row: RowMapping) -> WriteResult:
    paper_id = (
        connection.execute(
            select(versions.c.paper_id).where(
                versions.c.version_id == row["version_id"]
            )
        ).scalar_one()
        if row["version_id"]
        else None
    )
    return WriteResult(
        status=row["result_status"],
        reason=PaperReason.NOT_RETAINED
        if row["result_status"] == "not_retained"
        else None,
        paper_id=paper_id,
        version_id=row["version_id"],
        revision_no=row["result_revision_no"],
        observation_id=row["source_observation_id"],
        acquisition_id=row["acquisition_id"],
    )


def save_observation(
    engine: Engine,
    item: ObservationInput,
    doi: str,
    fields: dict[str, CandidateInput],
    artifact_id: str | None,
) -> WriteResult:
    from paper_radar.papers.queries import observation_fields

    with engine.connect() as connection:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            retry = (
                connection.execute(select(acquisitions).where(*request_key(item, doi)))
                .mappings()
                .first()
            )
            if retry and retry["interpretation_sha256"] == interpretation_digest(item):
                return _saved_result(connection, retry)
            identity = (
                connection.execute(
                    select(identifiers).where(identifiers.c.normalized_value == doi)
                )
                .mappings()
                .first()
            )
            if item.target_version_id:
                target = (
                    connection.execute(
                        select(versions).where(
                            versions.c.version_id == item.target_version_id
                        )
                    )
                    .mappings()
                    .first()
                )
                if target is None or target["paper_id"] != item.target_paper_id:
                    return _conflict("target_mismatch")
                if identity is None or identity["version_id"] != item.target_version_id:
                    return _conflict(
                        "doi_owner_conflict" if identity else "target_mismatch"
                    )
            if identity:
                paper_id, version_id = identity["paper_id"], identity["version_id"]
                if (
                    connection.execute(
                        select(versions.c.version_kind).where(
                            versions.c.version_id == version_id
                        )
                    ).scalar_one()
                    != item.version_kind
                ):
                    return _conflict("version_kind_conflict")
            else:
                paper_id = version_id = None
            retry = (
                connection.execute(select(acquisitions).where(*request_key(item, doi)))
                .mappings()
                .first()
            )
            if retry:
                if retry["interpretation_sha256"] != interpretation_digest(item):
                    raise PaperError(PaperReason.INVALID_OBSERVATION)
                return _saved_result(connection, retry)
            if (
                version_id
                and connection.execute(
                    select(observations.c.observation_id).where(
                        observations.c.version_id == version_id,
                        ~(
                            (observations.c.provider == item.provider)
                            & (observations.c.query_key == item.query_key)
                        ),
                    )
                ).first()
            ):
                raise PaperError(PaperReason.UNSUPPORTED_SOURCE, path="source_stream")
            now = datetime.now(UTC).isoformat(timespec="microseconds")
            if version_id is None and fields:
                paper_id, version_id = str(uuid4()), str(uuid4())
                connection.execute(papers.insert().values(paper_id=paper_id))
                connection.execute(
                    versions.insert().values(
                        version_id=version_id,
                        paper_id=paper_id,
                        version_kind=item.version_kind,
                    )
                )
                connection.execute(
                    identifiers.insert().values(
                        scheme="doi",
                        normalized_value=doi,
                        paper_id=paper_id,
                        version_id=version_id,
                    )
                )
                connection.execute(
                    selections.insert().values(
                        selection_id=str(uuid4()),
                        paper_id=paper_id,
                        version_id=version_id,
                        reason="initial",
                        selected_at=now,
                    )
                )
            source_id = None
            retained = False
            if fields:
                source_id = (
                    connection.execute(
                        select(observations.c.observation_id)
                        .where(
                            observations.c.version_id == version_id,
                            observations.c.provider == item.provider,
                            observations.c.query_key == item.query_key,
                            observations.c.candidate_sha256 == digest(fields),
                        )
                        .order_by(observations.c.observation_id)
                    )
                    .scalars()
                    .first()
                )
                if source_id is None:
                    if artifact_id is None:
                        raise PaperError(PaperReason.CORRUPT_REFERENCE)
                    source_id = str(uuid4())
                    connection.execute(
                        observations.insert().values(
                            observation_id=source_id,
                            version_id=version_id,
                            source_kind=item.source_kind,
                            provider=item.provider,
                            query_key=item.query_key,
                            observed_at=timestamp(item),
                            parser_version=item.parser_version,
                            artifact_id=artifact_id,
                            payload_sha256=hashlib.sha256(item.payload).hexdigest(),
                            candidate_sha256=digest(fields),
                        )
                    )
                    _insert_candidates(connection, source_id, fields)
                    retained = True
            acquisition_id = str(uuid4())
            current_no = (
                connection.execute(
                    select(func.max(revisions.c.revision_no)).where(
                        revisions.c.version_id == version_id
                    )
                ).scalar()
                if version_id
                else None
            )
            event_no = (
                1
                + (
                    connection.execute(
                        select(func.max(acquisitions.c.event_no)).where(
                            acquisitions.c.version_id == version_id
                        )
                    ).scalar()
                    or 0
                )
                if version_id
                else None
            )
            status = "retained" if retained else "not_retained"
            connection.execute(
                acquisitions.insert().values(
                    acquisition_id=acquisition_id,
                    version_id=version_id,
                    doi=doi,
                    version_kind=item.version_kind,
                    source_kind=item.source_kind,
                    provider=item.provider,
                    query_key=item.query_key,
                    observed_at=timestamp(item),
                    parser_version=item.parser_version,
                    payload_sha256=hashlib.sha256(item.payload).hexdigest(),
                    interpretation_sha256=interpretation_digest(item),
                    source_observation_id=source_id,
                    response_bytes_retained=retained,
                    event_no=event_no,
                    result_status=status,
                    result_revision_no=current_no,
                )
            )
            if version_id:
                rows = (
                    connection.execute(
                        select(acquisitions).where(
                            acquisitions.c.version_id == version_id
                        )
                    )
                    .mappings()
                    .all()
                )
                ranks = []
                for row in rows:
                    if row["source_observation_id"]:
                        source_fields = observation_fields(
                            connection, row["source_observation_id"]
                        )
                        ranks.append(
                            RankedObservation(
                                row["observed_at"],
                                row["payload_sha256"],
                                row["parser_version"],
                                {
                                    name: (fact.candidate_id, row["acquisition_id"])
                                    for name, fact in source_fields.items()
                                },
                            )
                        )
                winners = choose_fields(tuple(ranks))
                old_winners = {
                    row.field_name: (row.candidate_id, row.acquisition_id)
                    for row in connection.execute(
                        select(revision_fields).where(
                            revision_fields.c.version_id == version_id,
                            revision_fields.c.revision_no == current_no,
                        )
                    )
                }
                if winners != old_winners:
                    current_no = (current_no or 0) + 1
                    connection.execute(
                        revisions.insert().values(
                            version_id=version_id,
                            revision_no=current_no,
                            revised_at=now,
                            acquisition_id=acquisition_id,
                        )
                    )
                    for name, (candidate_id, acquired_id) in winners.items():
                        connection.execute(
                            revision_fields.insert().values(
                                version_id=version_id,
                                revision_no=current_no,
                                field_name=name,
                                candidate_id=candidate_id,
                                acquisition_id=acquired_id,
                                rule_version=1,
                            )
                        )
                    connection.execute(
                        acquisitions.update()
                        .where(acquisitions.c.acquisition_id == acquisition_id)
                        .values(result_revision_no=current_no)
                    )
            connection.commit()
            return WriteResult(
                status="retained" if retained else "not_retained",
                reason=None if retained else PaperReason.NOT_RETAINED,
                paper_id=paper_id,
                version_id=version_id,
                revision_no=current_no,
                observation_id=source_id,
                acquisition_id=acquisition_id,
            )
        except BaseException:
            connection.rollback()
            raise
