"""人工修正:版本内请求幂等,原子追加事件,不具备撤销语义。"""

import hashlib
import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from paper_radar.papers.models import ObservationFact, PaperTrace

from sqlalchemy import Connection, Engine, func, select

from paper_radar.papers.errors import PaperError, PaperReason
from paper_radar.papers.models import (
    CandidateInput,
    ManualCorrectionInput,
    ObservationInput,
    WriteResult,
)
from paper_radar.papers.repository import (
    insert_candidates,
    saved_acquisition_result,
    update_revision,
)
from paper_radar.papers.rules import digest, interpretation_digest
from paper_radar.papers.tables import (
    acquisitions,
    identifiers,
    manual_corrections,
    observations,
    revisions,
    versions,
)
from paper_radar.papers.text import normalize_fields
from paper_radar.papers.text_rules import normalize_text


def parse_correction(value: object) -> tuple[ManualCorrectionInput, bytes]:
    try:
        item = ManualCorrectionInput.model_validate(value)
        for text in (item.version_id, item.request_id, item.actor, item.reason):
            if not normalize_text(text) or len(text.encode("utf-8")) > 2048:
                raise PaperError(PaperReason.INVALID_MANUAL_CORRECTION)
        fields = normalize_fields(item.fields)
        if not fields or set(fields) != set(item.fields):
            raise PaperError(PaperReason.INVALID_MANUAL_CORRECTION)
        # Bind the request identity to all submitted content.
        payload = json.dumps(
            item.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        if len(payload) > 8 * 1024 * 1024:
            raise PaperError(PaperReason.INVALID_MANUAL_CORRECTION)
        return item, payload
    except PaperError as error:
        if error.reason in {PaperReason.INVALID_OBSERVATION, PaperReason.INVALID_TEXT}:
            raise PaperError(PaperReason.INVALID_MANUAL_CORRECTION) from None
        raise


def retry_correction(
    connection: Connection, item: ManualCorrectionInput, payload: bytes
) -> WriteResult | None:
    row = (
        connection.execute(
            select(manual_corrections).where(
                manual_corrections.c.version_id == item.version_id,
                manual_corrections.c.request_id == item.request_id,
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    if row["request_sha256"] != hashlib.sha256(payload).hexdigest():
        raise PaperError(PaperReason.INVALID_MANUAL_CORRECTION, path="request_id")
    saved = (
        connection.execute(
            select(acquisitions).where(
                acquisitions.c.acquisition_id == row["acquisition_id"]
            )
        )
        .mappings()
        .one()
    )
    return saved_acquisition_result(connection, saved)


def save_correction(
    engine: Engine, item: ManualCorrectionInput, payload: bytes, artifact_id: str
) -> WriteResult:
    with engine.connect() as connection:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        retry = retry_correction(connection, item, payload)
        if retry:
            return retry
        version = (
            connection.execute(
                select(versions).where(versions.c.version_id == item.version_id)
            )
            .mappings()
            .first()
        )
        if version is None:
            raise PaperError(PaperReason.VERSION_NOT_FOUND)
        doi = connection.execute(
            select(identifiers.c.normalized_value).where(
                identifiers.c.version_id == item.version_id
            )
        ).scalar_one_or_none()
        now = datetime.now(UTC)
        stamp = now.isoformat(timespec="microseconds")
        parsed = normalize_fields(item.fields)
        observation_id, acquisition_id = str(uuid4()), str(uuid4())
        event_no = 1 + (
            connection.execute(
                select(func.max(acquisitions.c.event_no)).where(
                    acquisitions.c.version_id == item.version_id
                )
            ).scalar()
            or 0
        )
        interpretation_input = ObservationInput(
            doi=doi,
            version_kind=version["version_kind"],
            source_kind="manual",
            provider=item.actor,
            query_key=item.request_id,
            observed_at=now,
            parser_version=1,
            payload=payload,
            fields=item.fields,
            interpretation="complete",
            target_paper_id=version["paper_id"],
            target_version_id=item.version_id,
        )
        connection.execute(
            observations.insert().values(
                observation_id=observation_id,
                version_id=item.version_id,
                source_kind="manual",
                provider=item.actor,
                query_key=item.request_id,
                observed_at=stamp,
                parser_version=1,
                artifact_id=artifact_id,
                payload_sha256=hashlib.sha256(payload).hexdigest(),
                candidate_sha256=digest(parsed),
            )
        )
        insert_candidates(connection, observation_id, parsed)
        current = connection.execute(
            select(func.max(revisions.c.revision_no)).where(
                revisions.c.version_id == item.version_id
            )
        ).scalar()
        connection.execute(
            acquisitions.insert().values(
                acquisition_id=acquisition_id,
                version_id=item.version_id,
                doi=doi,
                raw_doi=doi,
                version_kind=version["version_kind"],
                source_kind="manual",
                provider=item.actor,
                query_key=item.request_id,
                observed_at=stamp,
                parser_version=1,
                payload_sha256=hashlib.sha256(payload).hexdigest(),
                interpretation_sha256=interpretation_digest(interpretation_input),
                interpretation="complete",
                parsed_sha256=digest(item.fields),
                source_observation_id=observation_id,
                response_bytes_retained=True,
                event_no=event_no,
                result_status="retained",
                result_revision_no=current,
            )
        )
        connection.execute(
            manual_corrections.insert().values(
                version_id=item.version_id,
                request_id=item.request_id,
                acquisition_id=acquisition_id,
                actor=item.actor,
                reason=item.reason,
                request_sha256=hashlib.sha256(payload).hexdigest(),
            )
        )
        revision_no = update_revision(
            connection, item.version_id, acquisition_id, stamp
        )
        connection.commit()
        return WriteResult(
            status="retained",
            paper_id=version["paper_id"],
            version_id=item.version_id,
            revision_no=revision_no,
            observation_id=observation_id,
            acquisition_id=acquisition_id,
        )


def validate_manual_payload(
    trace: "PaperTrace", source: "ObservationFact", payload: bytes
) -> None:
    """显式字节核验/备份从不可变原始请求核对人工审计及规范候选。"""
    try:
        decoded = json.loads(payload)
        if not isinstance(decoded, dict) or not isinstance(decoded.get("fields"), dict):
            raise PaperError(PaperReason.CORRUPT_REFERENCE)
        author = decoded["fields"].get("authors")
        if isinstance(author, dict) and isinstance(author.get("value"), list):
            author["value"] = tuple(author["value"])
        original = ManualCorrectionInput.model_validate(decoded)
        _, canonical = parse_correction(original)
        event = next(
            item
            for item in trace.corrections
            if item.acquisition_id
            in {
                acquired.acquisition_id
                for acquired in trace.acquisitions
                if acquired.source_observation_id == source.observation_id
            }
        )
        acquired = next(
            item
            for item in trace.acquisitions
            if item.acquisition_id == event.acquisition_id
        )
        normalized = normalize_fields(original.fields)
        if (
            acquired.parsed_sha256 != digest(original.fields)
            or acquired.parser_version != 1
            or canonical != payload
            or original.version_id != source.version_id
            or original.request_id != event.request_id
            or original.actor != event.actor
            or original.reason != event.reason
            or normalized
            != {
                name: CandidateInput(value=fact.value, locator=fact.locator)
                for name, fact in source.fields.items()
            }
        ):
            raise PaperError(PaperReason.CORRUPT_REFERENCE)
    except (ValueError, TypeError, StopIteration, PaperError):
        raise PaperError(PaperReason.CORRUPT_REFERENCE) from None
