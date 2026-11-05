"""Body 最小持久层;独立决定、PDF 选择与冻结样本均只追加。"""

import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Connection, insert, select

from paper_radar.body import tables
from paper_radar.body.models import (
    BodyError,
    BodyReason,
    DecisionEvent,
    PdfAttachment,
    RootRegistration,
    SampleAdmission,
)
from paper_radar.body.queries import (
    current_pdf,
    decision_events,
    pdf_record,
    root_fact,
    sample_record,
)
from paper_radar.body.repository import (
    digest,
    now,
    replay,
    required,
    sequence,
    transaction,
)
from paper_radar.calibration.visibility import (
    VisibilityCapability,
    VisibilityPermission,
    evaluate_visibility,
)
from paper_radar.eligibility import RootPurpose
from paper_radar.papers.queries import load_trace
from paper_radar.runtime_logging import RuntimeLog, Sink
from paper_radar.screening.reasons import (
    ScreeningReasonInput,
    ScreeningSource,
    build_screening_reason,
)
from paper_radar.screening_tasks.tables import budgets as screening_budgets
from paper_radar.screening_tasks.tables import successes as screening_successes
from paper_radar.storage.artifacts import ArtifactStore

if TYPE_CHECKING:
    from paper_radar.body.models import BodyFacts, CanonicalParser, ExtractionView
    from paper_radar.reading.context import ExtractionIdentity


class BodyService:
    def __init__(
        self, database: Path, data_root: Path, *, sink: Sink | None = None
    ) -> None:
        self.database = database
        self.data_root = data_root
        self.store = ArtifactStore(database, data_root)
        self.log = RuntimeLog(sink)

    def root(self) -> RootRegistration:
        with transaction(self.database) as connection:
            return root_fact(connection)

    def register_root(self, purpose: RootPurpose | str) -> RootRegistration:
        try:
            purpose = RootPurpose(purpose)
        except ValueError:
            raise BodyError("invalid_request") from None
        if purpose is RootPurpose.UNKNOWN:
            raise BodyError("invalid_request")
        with transaction(self.database, write=True) as connection:
            previous = root_fact(connection)
            if previous.purpose is not RootPurpose.UNKNOWN:
                if previous.purpose is not purpose:
                    raise BodyError("root_conflict")
                return previous
            if connection.execute(select(tables.roots.c.singleton)).first() is not None:
                raise BodyError("root_conflict")
            saved = RootRegistration(str(uuid4()), purpose, now())
            connection.execute(
                insert(tables.roots).values(
                    singleton=1,
                    root_id=saved.root_id,
                    purpose=purpose.value,
                    registered_at=saved.registered_at,
                    registration_hash=digest(
                        [saved.root_id, purpose.value, saved.registered_at]
                    ),
                )
            )
            return saved

    def attach_pdf(
        self,
        paper_id: str,
        pdf: bytes,
        *,
        request_id: str,
        version_id: str | None = None,
    ) -> PdfAttachment:
        required(paper_id, request_id)
        if type(pdf) is not bytes or len(pdf) < 1024 or not pdf.startswith(b"%PDF-"):
            raise BodyError("invalid_pdf")
        pdf_hash = hashlib.sha256(pdf).hexdigest()
        # 缺省版本在首次附加时冻结;重放不随当前版本变化。
        request_hash = digest([paper_id, version_id, pdf_hash])
        with transaction(self.database) as connection:
            previous = replay(connection, tables.pdfs, request_id, request_hash)
            if previous is not None:
                return pdf_record(previous)
            trace = load_trace(connection, paper_id)
            selected = version_id or trace.current.version_id
            if selected not in {version.version_id for version in trace.versions}:
                raise BodyError("version_mismatch")
        artifact = self.store.publish_single(
            "original_pdf", [pdf], expected_sha256=pdf_hash
        )
        with transaction(self.database, write=True) as connection:
            previous = replay(connection, tables.pdfs, request_id, request_hash)
            if previous is not None:
                return pdf_record(previous)
            # 发布期间版本变化拒绝默认绑定漂移;已发布制品只是孤立材料,无附加事实。
            if (
                version_id is None
                and load_trace(connection, paper_id).current.version_id != selected
            ):
                raise BodyError("facts_changed")
            saved = PdfAttachment(
                str(uuid4()),
                paper_id,
                selected,
                sequence(connection, tables.pdfs, paper_id),
                artifact.artifact_id,
                pdf_hash,
                now(),
            )
            connection.execute(
                insert(tables.pdfs).values(
                    **saved.__dict__,
                    request_id=request_id,
                    request_hash=request_hash,
                    requested_version_id=version_id,
                )
            )
            return saved

    def pdfs(self, paper_id: str) -> tuple[PdfAttachment, ...]:
        with transaction(self.database) as connection:
            load_trace(connection, paper_id)
            return tuple(
                pdf_record(row)
                for row in connection.execute(
                    select(tables.pdfs)
                    .where(tables.pdfs.c.paper_id == paper_id)
                    .order_by(tables.pdfs.c.sequence)
                ).mappings()
            )

    def current_pdf(self, paper_id: str) -> PdfAttachment | None:
        with transaction(self.database) as connection:
            return current_pdf(
                connection,
                paper_id,
                load_trace(connection, paper_id).current.version_id,
            )

    def decide(
        self,
        paper_id: str,
        record: ScreeningReasonInput,
        *,
        request_id: str,
        actor: str,
        screening_references: tuple[str, ...] = (),
    ) -> DecisionEvent:
        required(paper_id, request_id, actor)
        if record.source is not ScreeningSource.DIRECT_MANUAL_DECISION:
            raise BodyError(BodyReason.SOURCE_REQUIRES_DEDICATED_PATH)
        try:
            build_screening_reason(record)
        except ValueError:
            raise BodyError("invalid_request") from None
        refs = tuple(sorted(set(screening_references)))
        request_hash = digest([paper_id, record.model_dump(mode="json"), actor, refs])
        with transaction(self.database, write=True) as connection:
            if (
                evaluate_visibility(frozenset()).permission(
                    VisibilityCapability.SET_DECISION
                )
                is not VisibilityPermission.ALLOWED
            ):
                raise BodyError("visibility_denied")
            old = replay(connection, tables.decisions, request_id, request_hash)
            if old is not None:
                return next(
                    event
                    for event in decision_events(connection, paper_id)
                    if event.fact.reference == old["decision_id"]
                )
            trace = load_trace(connection, paper_id)
            for reference in refs:
                owner = connection.execute(
                    select(screening_budgets.c.paper_id)
                    .select_from(
                        screening_successes.join(
                            screening_budgets,
                            screening_successes.c.budget_id
                            == screening_budgets.c.budget_id,
                        )
                    )
                    .where(screening_successes.c.success_id == reference)
                ).scalar_one_or_none()
                if owner != paper_id:
                    raise BodyError("screening_mismatch")
            decision_id = str(uuid4())
            connection.execute(
                insert(tables.decisions).values(
                    decision_id=decision_id,
                    request_id=request_id,
                    request_hash=request_hash,
                    paper_id=paper_id,
                    version_id=trace.current.version_id,
                    revision_no=trace.current.revision_no,
                    sequence=sequence(connection, tables.decisions, paper_id),
                    record_json=record.model_dump_json(),
                    actor=actor,
                    decided_at=now(),
                )
            )
            for reference in refs:
                connection.execute(
                    insert(tables.decision_screenings).values(
                        decision_id=decision_id, success_id=reference
                    )
                )
            return decision_events(connection, paper_id)[-1]

    def decisions(self, paper_id: str) -> tuple[DecisionEvent, ...]:
        with transaction(self.database) as connection:
            return decision_events(connection, paper_id)

    def freeze_sample(
        self,
        paper_id: str,
        *,
        feed_id: str,
        pdf_sha256: str,
        reason: str,
        request_id: str,
    ) -> SampleAdmission:
        required(paper_id, feed_id, pdf_sha256, reason, request_id)
        request_hash = digest([paper_id, feed_id, pdf_sha256, reason])
        with transaction(self.database, write=True) as connection:
            old = replay(connection, tables.samples, request_id, request_hash)
            if old is not None:
                return sample_record(old)
            trace = load_trace(connection, paper_id)
            pdf = current_pdf(connection, paper_id, trace.current.version_id)
            if root_fact(connection).purpose is not RootPurpose.EXPERIMENT:
                raise BodyError("root_unknown")
            if (
                pdf is None
                or pdf.pdf_sha256 != pdf_sha256
                or not any(
                    item.feed_id == feed_id and item.version_id == pdf.version_id
                    for item in trace.discoveries
                )
            ):
                raise BodyError("sample_mismatch")
            saved = SampleAdmission(
                str(uuid4()),
                paper_id,
                pdf.version_id,
                sequence(connection, tables.samples, paper_id),
                feed_id,
                pdf_sha256,
                now(),
                reason,
            )
            connection.execute(
                insert(tables.samples).values(
                    **saved.__dict__, request_id=request_id, request_hash=request_hash
                )
            )
            return saved

    def samples(self, paper_id: str) -> tuple[SampleAdmission, ...]:
        with transaction(self.database) as connection:
            return tuple(
                sample_record(row)
                for row in connection.execute(
                    select(tables.samples)
                    .where(tables.samples.c.paper_id == paper_id)
                    .order_by(tables.samples.c.sequence)
                ).mappings()
            )

    def extract(
        self, paper_id: str, *, snapshot_id: str, parser: "CanonicalParser"
    ) -> "ExtractionView":
        from paper_radar.body.extraction import extract

        with self.log.execution("body", controlled=(BodyError,), paper_id=paper_id):
            result = extract(
                self.database, self.data_root, self.store, paper_id, snapshot_id, parser
            )
            self.log.emit(
                "failed"
                if result.permanent_failure or not result.artifact_id
                else "succeeded",
                fingerprint=result.fingerprint,
            )
            return result

    def extraction(self, fingerprint: str) -> "ExtractionView | None":
        from paper_radar.body.extraction import extraction_view

        with transaction(self.database) as connection:
            return extraction_view(connection, fingerprint)

    def review_layout(
        self,
        identity: "ExtractionIdentity",
        *,
        passed: bool,
        checks: "Mapping[str, bool]",
        note: str,
        actor: str,
        request_id: str,
    ) -> "ExtractionView":
        from paper_radar.body.extraction import review_layout

        return review_layout(
            self.database,
            identity,
            passed=passed,
            checks=checks,
            note=note,
            actor=actor,
            request_id=request_id,
        )

    def facts_in_connection(
        self,
        connection: Connection,
        paper_id: str,
        *,
        identity: "ExtractionIdentity | None" = None,
        fingerprint: str | None = None,
        ordinary: bool = False,
    ) -> "BodyFacts":
        """同事务核验;不读取 settings、SDK 或另一个 Connection。"""
        from paper_radar.body.facts import assemble_facts

        return assemble_facts(
            connection,
            paper_id,
            identity=identity,
            fingerprint=fingerprint,
            ordinary=ordinary,
        )

    def facts(
        self,
        paper_id: str,
        *,
        identity: "ExtractionIdentity | None" = None,
        fingerprint: str | None = None,
        ordinary: bool = False,
    ) -> "BodyFacts":
        with transaction(self.database) as connection:
            return self.facts_in_connection(
                connection,
                paper_id,
                identity=identity,
                fingerprint=fingerprint,
                ordinary=ordinary,
            )

    def validate_all(self) -> None:
        from paper_radar.body.validation import validate_all

        validate_all(self.database, self.data_root)
