"""Feed 原文发现、连续条目身份和完整解释的原子写入。"""

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import Engine, func, select

from paper_radar.papers.errors import PaperError, PaperReason
from paper_radar.papers.models import CandidateInput, ObservationInput, WriteResult
from paper_radar.papers.repository import (
    _conflict,
    _insert_candidates,
    _saved_result,
    timestamp,
    update_revision,
)
from paper_radar.papers.rules import digest, interpretation_digest
from paper_radar.papers.tables import (
    acquisitions,
    feed_discoveries,
    feed_entries,
    feed_interpretations,
    feeds,
    identifiers,
    observations,
    papers,
    revisions,
    selections,
    versions,
)
from paper_radar.storage.artifacts import ArtifactStore


def submit_feed(
    engine: Engine,
    database: Path,
    data_root: Path,
    item: ObservationInput,
    doi: str | None,
    fields: dict[str, CandidateInput],
) -> WriteResult:
    fingerprint = hashlib.sha256(item.payload).hexdigest()
    artifact_id = (
        ArtifactStore(database, data_root)
        .publish_single("source_snapshot", (item.payload,))
        .artifact_id
    )
    with engine.connect() as connection:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            if (
                connection.execute(
                    select(feeds).where(feeds.c.feed_id == item.feed_id)
                ).first()
                is None
            ):
                raise PaperError(PaperReason.INVALID_OBSERVATION, path="feed_id")
            entry = (
                connection.execute(
                    select(feed_entries).where(
                        feed_entries.c.feed_id == item.feed_id,
                        feed_entries.c.entry_id == item.entry_id,
                    )
                )
                .mappings()
                .first()
            )
            identity = (
                connection.execute(
                    select(identifiers).where(identifiers.c.normalized_value == doi)
                )
                .mappings()
                .first()
                if doi
                else None
            )
            version_id = (
                entry["version_id"]
                if entry
                else identity["version_id"]
                if identity
                else None
            )
            version = (
                connection.execute(
                    select(versions).where(versions.c.version_id == version_id)
                )
                .mappings()
                .first()
                if version_id
                else None
            )
            current_doi = (
                connection.execute(
                    select(identifiers.c.normalized_value).where(
                        identifiers.c.version_id == version_id
                    )
                ).scalar()
                if version_id
                else None
            )
            if version and version["version_kind"] != item.version_kind:
                return _conflict("version_kind_conflict")
            if item.target_version_id and (
                version is None
                or item.target_version_id != version_id
                or item.target_paper_id != version["paper_id"]
            ):
                return _conflict("target_mismatch")
            if entry and doi and current_doi and doi != current_doi:
                return _conflict("entry_doi_changed")
            if entry and identity and identity["version_id"] != version_id:
                return _conflict("doi_owner_conflict")
            if item.target_version_id and doi and current_doi != doi:
                return _conflict("target_mismatch")
            found = (
                connection.execute(
                    select(feed_discoveries).where(
                        feed_discoveries.c.item_fingerprint == fingerprint
                    )
                )
                .mappings()
                .first()
            )
            if found and (found["feed_id"], found["entry_id"]) != (
                item.feed_id,
                item.entry_id,
            ):
                raise PaperError(PaperReason.INVALID_OBSERVATION, path="payload")
            prior = (
                connection.execute(
                    select(acquisitions)
                    .join(
                        feed_interpretations,
                        acquisitions.c.acquisition_id
                        == feed_interpretations.c.acquisition_id,
                    )
                    .where(feed_interpretations.c.discovery_id == found["discovery_id"])
                )
                .mappings()
                .all()
                if found
                else []
            )
            same = next(
                (row for row in prior if row["parser_version"] == item.parser_version),
                None,
            )
            if same:
                assert found is not None
                submitted_at = connection.execute(
                    select(feed_interpretations.c.submitted_at).where(
                        feed_interpretations.c.acquisition_id == same["acquisition_id"]
                    )
                ).scalar_one()
                if (
                    item.parser_version < max(row["parser_version"] for row in prior)
                    and timestamp(item) != submitted_at
                ):
                    raise PaperError(
                        PaperReason.INVALID_OBSERVATION, path="parser_version"
                    )
                if (
                    same["interpretation_sha256"] != interpretation_digest(item)
                    or same["doi"] != doi
                ):
                    raise PaperError(
                        PaperReason.INVALID_OBSERVATION, path="parser_version"
                    )
                # An exact retained request is replayable after an upgrade.
                connection.execute(
                    feed_discoveries.update()
                    .where(feed_discoveries.c.discovery_id == found["discovery_id"])
                    .values(last_seen=max(found["last_seen"], timestamp(item)))
                )
                result = _saved_result(connection, same).model_copy(
                    update={"discovery_id": found["discovery_id"]}
                )
                connection.commit()
                return result
            if item.parser_version < max(
                (row["parser_version"] for row in prior), default=0
            ):
                raise PaperError(PaperReason.INVALID_OBSERVATION, path="parser_version")
            now = datetime.now(UTC).isoformat(timespec="microseconds")
            if version is None:
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
                    selections.insert().values(
                        selection_id=str(uuid4()),
                        paper_id=paper_id,
                        version_id=version_id,
                        reason="initial",
                        selected_at=now,
                    )
                )
            else:
                paper_id = version["paper_id"]
            if not isinstance(version_id, str):
                raise PaperError(PaperReason.CORRUPT_REFERENCE)
            if doi and current_doi is None:
                connection.execute(
                    identifiers.insert().values(
                        scheme="doi",
                        normalized_value=doi,
                        paper_id=paper_id,
                        version_id=version_id,
                    )
                )
            if entry is None:
                connection.execute(
                    feed_entries.insert().values(
                        feed_id=item.feed_id,
                        entry_id=item.entry_id,
                        version_id=version_id,
                    )
                )
            discovery_id = found["discovery_id"] if found else str(uuid4())
            first_seen = found["first_seen"] if found else timestamp(item)
            if found:
                connection.execute(
                    feed_discoveries.update()
                    .where(feed_discoveries.c.discovery_id == discovery_id)
                    .values(last_seen=max(found["last_seen"], timestamp(item)))
                )
            else:
                connection.execute(
                    feed_discoveries.insert().values(
                        discovery_id=discovery_id,
                        feed_id=item.feed_id,
                        entry_id=item.entry_id,
                        item_fingerprint=fingerprint,
                        artifact_id=artifact_id,
                        first_seen=first_seen,
                        last_seen=first_seen,
                    )
                )
            source_id = None
            retained = bool(fields) or not found
            if retained:
                source_id = str(uuid4())
                connection.execute(
                    observations.insert().values(
                        observation_id=source_id,
                        version_id=version_id,
                        source_kind="feed",
                        provider=item.feed_id,
                        query_key=item.entry_id,
                        observed_at=first_seen,
                        parser_version=item.parser_version,
                        artifact_id=artifact_id,
                        payload_sha256=fingerprint,
                        candidate_sha256=digest(fields),
                    )
                )
                _insert_candidates(connection, source_id, fields)
            acquisition_id = str(uuid4())
            current_no = connection.execute(
                select(func.max(revisions.c.revision_no)).where(
                    revisions.c.version_id == version_id
                )
            ).scalar()
            event_no = (
                connection.execute(
                    select(func.max(acquisitions.c.event_no)).where(
                        acquisitions.c.version_id == version_id
                    )
                ).scalar()
                or 0
            ) + 1
            status = "retained" if retained else "not_retained"
            connection.execute(
                acquisitions.insert().values(
                    acquisition_id=acquisition_id,
                    version_id=version_id,
                    doi=doi,
                    raw_doi=item.doi,
                    version_kind=item.version_kind,
                    source_kind="feed",
                    provider=item.feed_id,
                    query_key=item.entry_id,
                    observed_at=first_seen,
                    parser_version=item.parser_version,
                    payload_sha256=fingerprint,
                    interpretation_sha256=interpretation_digest(item),
                    parsed_sha256=digest(item.fields),
                    interpretation=item.interpretation,
                    source_observation_id=source_id,
                    response_bytes_retained=retained,
                    event_no=event_no,
                    result_status=status,
                    result_revision_no=current_no,
                )
            )
            connection.execute(
                feed_interpretations.insert().values(
                    discovery_id=discovery_id,
                    parser_version=item.parser_version,
                    submitted_at=timestamp(item),
                    acquisition_id=acquisition_id,
                )
            )
            current_no = update_revision(connection, version_id, acquisition_id, now)
            connection.commit()
            return WriteResult(
                status="retained" if retained else "not_retained",
                reason=None if retained else PaperReason.NOT_RETAINED,
                paper_id=paper_id,
                version_id=version_id,
                revision_no=current_no,
                observation_id=source_id,
                acquisition_id=acquisition_id,
                discovery_id=discovery_id,
            )
        except BaseException:
            connection.rollback()
            raise
