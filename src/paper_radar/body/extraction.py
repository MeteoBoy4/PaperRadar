"""根锁包围持久领取与结算;解析期间没有数据库事务。"""

import fcntl
import hashlib
import json
import os
import stat
import sys
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from time import monotonic
from uuid import uuid4

from sqlalchemy import Connection, insert, select

from paper_radar.body import tables
from paper_radar.body.models import (
    BodyError,
    CanonicalParser,
    ExtractionAttempt,
    ExtractionFailure,
    ExtractionView,
    ParserFailure,
)
from paper_radar.body.repository import digest, now, replay, required, transaction
from paper_radar.config import StageName, load_config_snapshot
from paper_radar.eligibility import QualityBasis, QualityFact, QualityFailure
from paper_radar.fulltext.artifacts import FulltextArtifacts
from paper_radar.fulltext.models import FulltextError
from paper_radar.reading.context import ExtractionIdentity
from paper_radar.stage_inputs import ExtractionFacts, build_stage_input
from paper_radar.storage.artifacts import ArtifactStore

LOCK_FILENAME = ".body-docling.lock"
LAYOUT_CHECKS = frozenset(
    {
        "body_boundary",
        "reading_order",
        "sections",
        "headers_footers",
        "provenance",
        "restricted_content",
    }
)
PERMANENT = frozenset({ExtractionFailure.NO_TEXT_LAYER, ExtractionFailure.QUALITY_GATE})


@contextmanager
def root_lock(root: Path) -> Iterator[None]:
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        fd = os.open(
            root / LOCK_FILENAME,
            os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o600,
        )
    except OSError:
        raise BodyError("unsafe_lock") from None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise BodyError("unsafe_lock")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(
                "另一个 Docling 转换正在进行,等待其结束后继续",
                file=sys.stderr,
                flush=True,
            )
            fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def extraction_view(connection: Connection, fingerprint: str) -> ExtractionView | None:
    row = (
        connection.execute(
            select(tables.inputs).where(tables.inputs.c.fingerprint == fingerprint)
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    attempts = []
    identity = None
    artifact = None
    quality = QualityFact(QualityBasis.ABSENT)
    permanent = False
    for entry in connection.execute(
        select(tables.attempts, tables.outcomes)
        .select_from(
            tables.attempts.outerjoin(
                tables.outcomes,
                tables.attempts.c.attempt_id == tables.outcomes.c.attempt_id,
            )
        )
        .where(tables.attempts.c.fingerprint == fingerprint)
        .order_by(tables.attempts.c.ordinal)
    ).mappings():
        failure = ExtractionFailure(entry["failure"]) if entry["failure"] else None
        attempts.append(
            ExtractionAttempt(
                entry["attempt_id"],
                entry["ordinal"],
                entry["claimed_at"],
                failure,
                entry["settled_at"],
                entry["artifact_id"],
                entry["elapsed_seconds"],
                entry["peak_memory_bytes"],
            )
        )
        permanent |= failure in PERMANENT
        if entry["artifact_id"] is not None:
            artifact = entry["artifact_id"]
            identity = ExtractionIdentity(
                fingerprint, entry["reading_sha256"], entry["evidence_map_sha256"]
            )
            if entry["quality_failure"]:
                quality = QualityFact(
                    QualityBasis.FAILED,
                    artifact,
                    QualityFailure(entry["quality_failure"]),
                )
    success = connection.execute(
        select(tables.successes.c.attempt_id).where(
            tables.successes.c.fingerprint == fingerprint
        )
    ).scalar_one_or_none()
    if success is not None and (
        not attempts
        or attempts[-1].attempt_id != success
        or attempts[-1].failure is not None
        or identity is None
    ):
        raise BodyError("corrupt_reference")
    if success is not None and identity is not None:
        reviews = (
            connection.execute(
                select(tables.reviews).where(
                    tables.reviews.c.fingerprint == fingerprint
                )
            )
            .mappings()
            .all()
        )
        for review in reviews:
            if (review["reading_sha256"], review["evidence_map_sha256"]) != (
                identity.reading_sha256,
                identity.evidence_map_sha256,
            ):
                raise BodyError("corrupt_reference")
        if any(not review["passed"] for review in reviews):
            quality = QualityFact(
                QualityBasis.FAILED, artifact, QualityFailure.LAYOUT_REVIEW
            )
            permanent = True
        elif reviews:
            quality = QualityFact(QualityBasis.EXPERIMENT_DOCUMENT_GATE, artifact)
    return ExtractionView(
        fingerprint,
        row["backend"],
        row["pdf_sha256"],
        tuple(attempts),
        artifact,
        identity,
        quality,
        permanent,
    )


def settle_failure(
    connection: Connection,
    attempt_id: str,
    failure: ExtractionFailure,
    elapsed: float,
    peak: int,
) -> None:
    connection.execute(
        insert(tables.outcomes).values(
            attempt_id=attempt_id,
            failure=failure.value,
            elapsed_seconds=elapsed,
            peak_memory_bytes=max(0, peak),
            settled_at=now(),
        )
    )


def extract(
    database: Path,
    root: Path,
    store: ArtifactStore,
    paper_id: str,
    snapshot_id: str,
    parser: CanonicalParser,
) -> ExtractionView:
    from paper_radar.body.queries import current_pdf
    from paper_radar.papers.queries import load_trace

    snapshot = load_config_snapshot(database, snapshot_id)
    with transaction(database) as connection:
        trace = load_trace(connection, paper_id)
        pdf = current_pdf(connection, paper_id, trace.current.version_id)
        if pdf is None:
            raise BodyError("pdf_absent")
    raw_pdf = store.read_artifact(pdf.artifact_id)["payload"]
    if (
        len(raw_pdf) < 1024
        or not raw_pdf.startswith(b"%PDF-")
        or hashlib.sha256(raw_pdf).hexdigest() != pdf.pdf_sha256
    ):
        raise BodyError("corrupt_reference")
    stage_input = build_stage_input(
        snapshot, StageName.EXTRACTION, ExtractionFacts(pdf_sha256=pdf.pdf_sha256)
    )
    semantics = snapshot.extraction
    assert semantics is not None and semantics.model_artifacts_hash is not None
    fingerprint = stage_input.fingerprint
    backend = semantics.backend.backend_id
    # 前置 probe / 模型逐文件核验没有领取事实,也不进入根锁等待。
    parser.preflight(semantics)
    with root_lock(root):
        with transaction(database, write=True) as connection:
            selected = current_pdf(
                connection,
                paper_id,
                load_trace(connection, paper_id).current.version_id,
            )
            if selected != pdf:
                raise BodyError("facts_changed")
            existing = extraction_view(connection, fingerprint)
            if existing is not None:
                if existing.backend != backend or existing.pdf_sha256 != pdf.pdf_sha256:
                    raise BodyError("corrupt_reference")
                # 持锁后仍未结算的领取者已经失联;只追加未知结算,不退预算。
                for attempt in existing.attempts:
                    if attempt.settled_at is None:
                        settle_failure(
                            connection,
                            attempt.attempt_id,
                            ExtractionFailure.OUTCOME_UNKNOWN,
                            0,
                            0,
                        )
                existing = extraction_view(connection, fingerprint)
                assert existing is not None
                if (
                    existing.artifact_id is not None
                    or existing.permanent_failure
                    or existing.remaining_attempts == 0
                ):
                    return existing
            else:
                connection.execute(
                    insert(tables.inputs).values(
                        fingerprint=fingerprint,
                        backend=backend,
                        pdf_sha256=pdf.pdf_sha256,
                        snapshot_id=snapshot_id,
                        payload=stage_input.payload_bytes,
                    )
                )
            attempt_id = str(uuid4())
            ordinal = len(existing.attempts) + 1 if existing else 1
            connection.execute(
                insert(tables.attempts).values(
                    attempt_id=attempt_id,
                    fingerprint=fingerprint,
                    backend=backend,
                    ordinal=ordinal,
                    claimed_at=now(),
                )
            )
        start = monotonic()
        try:
            result = parser.convert(raw_pdf, semantics)
            published = FulltextArtifacts(store).publish(
                result.document,
                extraction_fingerprint=fingerprint,
                backend_config_hash=semantics.backend_config_hash,
                model_artifacts_hash=semantics.model_artifacts_hash,
                elapsed_seconds=max(0, monotonic() - start),
                peak_memory_bytes=result.peak_memory_bytes,
                document_json=result.document_json,
                warnings=result.warnings,
            )
        except FulltextError:
            with transaction(database, write=True) as connection:
                settle_failure(
                    connection,
                    attempt_id,
                    ExtractionFailure.QUALITY_GATE,
                    max(0, monotonic() - start),
                    result.peak_memory_bytes,
                )
        except ParserFailure as error:
            with transaction(database, write=True) as connection:
                settle_failure(
                    connection,
                    attempt_id,
                    error.failure,
                    max(0, monotonic() - start),
                    error.peak_memory_bytes,
                )
        except Exception:
            with transaction(database, write=True) as connection:
                settle_failure(
                    connection,
                    attempt_id,
                    ExtractionFailure.EXECUTOR_ERROR,
                    max(0, monotonic() - start),
                    0,
                )
        else:
            failure = (
                published.quality.issues[0].failure
                if published.quality.issues
                else None
            )
            with transaction(database, write=True) as connection:
                connection.execute(
                    insert(tables.outcomes).values(
                        attempt_id=attempt_id,
                        failure=(
                            ExtractionFailure.NO_TEXT_LAYER.value
                            if failure is QualityFailure.PDF_TEXT_LAYER
                            else ExtractionFailure.QUALITY_GATE.value
                        )
                        if failure
                        else None,
                        artifact_id=published.artifact_id,
                        reading_sha256=published.identity.reading_sha256,
                        evidence_map_sha256=published.identity.evidence_map_sha256,
                        quality_failure=failure.value if failure else None,
                        elapsed_seconds=max(0, monotonic() - start),
                        peak_memory_bytes=result.peak_memory_bytes,
                        settled_at=now(),
                    )
                )
                if failure is None:
                    connection.execute(
                        insert(tables.successes).values(
                            fingerprint=fingerprint, attempt_id=attempt_id
                        )
                    )
        with transaction(database) as connection:
            view = extraction_view(connection, fingerprint)
            assert view is not None
            return view


def review_layout(
    database: Path,
    identity: ExtractionIdentity,
    *,
    passed: bool,
    checks: Mapping[str, bool],
    note: str,
    actor: str,
    request_id: str,
) -> ExtractionView:
    required(note, actor, request_id)
    if (
        type(passed) is not bool
        or set(checks) != LAYOUT_CHECKS
        or any(type(v) is not bool for v in checks.values())
        or passed != all(checks.values())
    ):
        raise BodyError("invalid_request")
    request_hash = digest(
        [
            identity.extraction_fingerprint,
            identity.reading_sha256,
            identity.evidence_map_sha256,
            passed,
            dict(checks),
            note,
            actor,
        ]
    )
    with transaction(database, write=True) as connection:
        old = replay(connection, tables.reviews, request_id, request_hash)
        view = extraction_view(connection, identity.extraction_fingerprint)
        if view is None or view.identity != identity or view.artifact_id is None:
            raise BodyError("corrupt_reference")
        if old is not None:
            return view
        if view.permanent_failure and (
            passed or view.quality.failure is not QualityFailure.LAYOUT_REVIEW
        ):
            raise BodyError("layout_conflict")
        connection.execute(
            insert(tables.reviews).values(
                review_id=str(uuid4()),
                request_id=request_id,
                request_hash=request_hash,
                fingerprint=identity.extraction_fingerprint,
                reading_sha256=identity.reading_sha256,
                evidence_map_sha256=identity.evidence_map_sha256,
                passed=int(passed),
                checks_json=json.dumps(dict(checks), sort_keys=True),
                note=note,
                actor=actor,
                reviewed_at=now(),
            )
        )
        updated = extraction_view(connection, identity.extraction_fingerprint)
        assert updated is not None
        return updated
