"""Body 最小持久层;独立决定、PDF 选择与冻结样本均只追加。"""

import hashlib
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Literal
from uuid import uuid4

from sqlalchemy import Connection, insert, select

from paper_radar.body import tables
from paper_radar.body.models import (
    BodyError,
    BodyReason,
    CurrentBody,
    DecisionEvent,
    DecisionMetadata,
    PdfAttachment,
    RootRegistration,
    SampleAdmission,
)
from paper_radar.body.pdf import valid_pdf_bytes
from paper_radar.body.queries import (
    current_pdf,
    decision_events,
    decision_metadata,
    pdf_record,
    root_fact,
    sample_record,
)
from paper_radar.body.read_basis import ReadBasis
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
from paper_radar.eligibility import ExecutionSource, QualityBasis, RootPurpose
from paper_radar.papers.queries import load_trace
from paper_radar.runtime_logging import RuntimeLog, Sink
from paper_radar.screening.reasons import (
    ScreeningReasonInput,
    ScreeningSource,
    build_screening_reason,
)
from paper_radar.screening_tasks.tables import budgets as screening_budgets
from paper_radar.screening_tasks.tables import successes as screening_successes
from paper_radar.stage_inputs import StageInput
from paper_radar.storage.artifacts import ArtifactStore
from paper_radar.storage.history import (
    HistoryBoundary,
    HistoryKeys,
    HistoryPage,
    history_boundaries,
    history_page,
)
from paper_radar.storage.schema import (
    experiment_frozen_samples,
    experiment_layout_recordings,
)

if TYPE_CHECKING:
    from paper_radar.body.models import (
        BodyFacts,
        CanonicalParser,
        ExtractionObserver,
        ExtractionView,
    )
    from paper_radar.eligibility import PaperProjection
    from paper_radar.reading.context import ExtractionIdentity


def _decision_request(
    paper_id: str,
    record: ScreeningReasonInput,
    request_id: str,
    actor: str,
    screening_references: tuple[str, ...],
    delegation_kind: Literal["stage_b_preselection"] | None = None,
) -> tuple[tuple[str, ...], str]:
    required(paper_id, request_id, actor)
    if record.source is not ScreeningSource.DIRECT_MANUAL_DECISION:
        raise BodyError(BodyReason.SOURCE_REQUIRES_DEDICATED_PATH)
    try:
        build_screening_reason(record)
    except ValueError:
        raise BodyError("invalid_request") from None
    refs = tuple(sorted(set(screening_references)))
    if delegation_kind not in {None, "stage_b_preselection"}:
        raise BodyError("invalid_request")
    payload: list[object] = [paper_id, record.model_dump(mode="json"), actor, refs]
    if delegation_kind is not None:
        payload.append(delegation_kind)
    return refs, digest(payload)


class BodyService:
    def __init__(
        self, database: Path, data_root: Path, *, sink: Sink | None = None
    ) -> None:
        self.database = database
        self.data_root = data_root
        self.store = ArtifactStore(database, data_root)
        self.log = RuntimeLog(sink)

    def exposure_scope_in_connection(
        self, connection: Connection
    ) -> dict[str, HistoryBoundary]:
        """短写事务使用的只读事件范围元数据;不加载历史或文件。"""
        return history_boundaries(connection, (tables.decisions, tables.pdfs))

    def exposure_history_in_connection(
        self, connection: Connection, through: dict[str, HistoryKeys] | None = None
    ) -> tuple[HistoryPage, ...]:
        """全部人工决定与 PDF 附件;不依赖有效决定或当前 PDF。"""
        return (
            history_page(
                connection,
                tables.decisions,
                (
                    "decision_id",
                    "paper_id",
                    "version_id",
                    "revision_no",
                    "sequence",
                    "record_json",
                ),
                through=through,
                hashed=("record_json",),
            ),
            history_page(
                connection,
                tables.pdfs,
                (
                    "attachment_id",
                    "paper_id",
                    "version_id",
                    "artifact_id",
                    "pdf_sha256",
                    "sequence",
                ),
                through=through,
            ),
        )

    def root_in_connection(self, connection: Connection) -> RootRegistration:
        """调用方一致读事务内的唯一根事实。"""
        return root_fact(connection)

    def root(self) -> RootRegistration:
        with transaction(self.database) as connection:
            return root_fact(connection)

    def current_body_in_connection(
        self, connection: Connection, paper_id: str
    ) -> CurrentBody:
        """当前版本最新 PDF 的显式选择或唯一成功,与资格共用同一查询。"""
        from paper_radar.body.queries import current_body

        return current_body(connection, paper_id)

    def current_body(self, paper_id: str) -> CurrentBody:
        """保留链路缺失与多成功歧义的受控原因,不读取配置或触发提取。"""
        with transaction(self.database) as connection:
            return self.current_body_in_connection(connection, paper_id)

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
            return self.attach_pdf_in_connection(
                connection,
                paper_id,
                pdf_sha256=pdf_hash,
                artifact_id=artifact.artifact_id,
                request_id=request_id,
                version_id=version_id,
                selected_version_id=selected,
            )

    def attach_pdf_in_connection(
        self,
        connection: Connection,
        paper_id: str,
        *,
        pdf_sha256: str,
        artifact_id: str,
        request_id: str,
        version_id: str | None,
        selected_version_id: str,
        confirmation_id: str | None = None,
    ) -> PdfAttachment:
        """调用方已发布并校验 PDF;在其写事务追加,不提交连接。"""
        required(paper_id, pdf_sha256, artifact_id, request_id, selected_version_id)
        request_hash = digest(
            [paper_id, version_id, pdf_sha256]
            + ([confirmation_id] if confirmation_id is not None else [])
        )
        selected = selected_version_id
        if selected not in {
            v.version_id for v in load_trace(connection, paper_id).versions
        }:
            raise BodyError("version_mismatch")
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
            artifact_id,
            pdf_sha256,
            now(),
        )
        connection.execute(
            insert(tables.pdfs).values(
                **saved.__dict__,
                request_id=request_id,
                request_hash=request_hash,
                requested_version_id=version_id,
                confirmation_id=confirmation_id,
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
        refs, _ = _decision_request(
            paper_id, record, request_id, actor, screening_references
        )
        with transaction(self.database, write=True) as connection:
            return self.decide_in_connection(
                connection,
                paper_id,
                record,
                request_id=request_id,
                actor=actor,
                screening_references=refs,
            )

    def decide_in_connection(
        self,
        connection: Connection,
        paper_id: str,
        record: ScreeningReasonInput,
        *,
        request_id: str,
        actor: str,
        screening_references: tuple[str, ...] = (),
        delegation_kind: Literal["stage_b_preselection"] | None = None,
    ) -> DecisionEvent:
        """调用方持有写事务;保留 decide 校验/重放/顺序,不提交连接。"""
        refs, request_hash = _decision_request(
            paper_id, record, request_id, actor, screening_references, delegation_kind
        )
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
                delegation_kind=delegation_kind,
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

    def decision_metadata_in_connection(
        self, connection: Connection, paper_id: str
    ) -> tuple[DecisionMetadata, ...]:
        """只读当前事务的决定ID/序号/结果;不加载完整来源或上层关联。"""
        return decision_metadata(connection, paper_id)

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
        with transaction(self.database, write=True) as connection:
            return self.freeze_sample_in_connection(
                connection,
                paper_id,
                feed_id=feed_id,
                pdf_sha256=pdf_sha256,
                reason=reason,
                request_id=request_id,
            )

    def freeze_sample_in_connection(
        self,
        connection: Connection,
        paper_id: str,
        *,
        feed_id: str,
        pdf_sha256: str,
        reason: str,
        request_id: str,
    ) -> SampleAdmission:
        """复用冻结规则,允许产品关联与样本在同一事务追加。"""
        required(paper_id, feed_id, pdf_sha256, reason, request_id)
        request_hash = digest([paper_id, feed_id, pdf_sha256, reason])
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
        self,
        paper_id: str,
        *,
        snapshot_id: str,
        parser: "CanonicalParser",
        claim_guard: Callable[[Connection], None] | None = None,
        observer: "ExtractionObserver | None" = None,
    ) -> "ExtractionView":
        from paper_radar.body.extraction import extract

        with self.log.execution("body", controlled=(BodyError,), paper_id=paper_id):
            result = extract(
                self.database,
                self.data_root,
                self.store,
                paper_id,
                snapshot_id,
                parser,
                claim_guard=claim_guard,
                observer=observer,
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

    def extractions(self, paper_id: str) -> "tuple[ExtractionView, ...]":
        """该论文所有显式 PDF 的提取历史;不选最新成功或改变质量。"""
        from paper_radar.body.extraction import extraction_view

        with transaction(self.database) as connection:
            hashes = select(tables.pdfs.c.pdf_sha256).where(
                tables.pdfs.c.paper_id == paper_id
            )
            fingerprints = connection.execute(
                select(tables.inputs.c.fingerprint)
                .where(tables.inputs.c.pdf_sha256.in_(hashes))
                .order_by(tables.inputs.c.fingerprint)
            ).scalars()
            views = tuple(
                extraction_view(connection, fingerprint) for fingerprint in fingerprints
            )
            return tuple(view for view in views if view is not None)

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

    def review_layout_in_connection(
        self,
        connection: Connection,
        identity: "ExtractionIdentity",
        *,
        passed: bool,
        checks: "Mapping[str, bool]",
        note: str,
        actor: str,
        request_id: str,
        recording_kind: str | None = None,
    ) -> "ExtractionView":
        from paper_radar.body.extraction import review_layout_in_connection

        return review_layout_in_connection(
            connection,
            identity,
            passed=passed,
            checks=checks,
            note=note,
            actor=actor,
            request_id=request_id,
            recording_kind=recording_kind,
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

    def current_projection(self, paper_id: str) -> "PaperProjection":
        """根中性当前全文事实投影;只读,不领取任务或放宽歧义/质量守卫。"""
        from paper_radar.body.facts import current_projection

        with transaction(self.database) as connection:
            return current_projection(connection, paper_id)

    def extraction_input_in_connection(
        self, connection: Connection, fingerprint: str
    ) -> "StageInput":
        """读取首次持久提取配方,供同事务消费者严格回放;不读当前配置。"""
        from paper_radar.body import tables
        from paper_radar.stage_inputs import replay_stage_input

        row = (
            connection.execute(
                select(tables.inputs).where(tables.inputs.c.fingerprint == fingerprint)
            )
            .mappings()
            .first()
        )
        if row is None:
            raise BodyError("extraction_absent")
        return replay_stage_input(row["payload"], fingerprint)

    def read_basis_in_connection(
        self, connection: Connection, facts: "BodyFacts"
    ) -> dict[str, str | None]:
        """绑定领取时的真实用途依据,由历史核验口再次解引用。"""
        from datetime import UTC, datetime

        if (
            not facts.eligible
            or facts.extraction is None
            or facts.extraction.identity is None
            or facts.pdf is None
            or facts.decision is None
        ):
            raise BodyError("corrupt_reference")
        identity = facts.extraction.identity
        review_query = select(tables.reviews.c.review_id).where(
            tables.reviews.c.fingerprint == identity.extraction_fingerprint,
            tables.reviews.c.reading_sha256 == identity.reading_sha256,
            tables.reviews.c.evidence_map_sha256 == identity.evidence_map_sha256,
            tables.reviews.c.passed == 1,
        )
        if (
            facts.sample is not None
            and connection.execute(
                select(experiment_frozen_samples.c.sample_id).where(
                    experiment_frozen_samples.c.sample_id == facts.sample.sample_id
                )
            ).first()
            is not None
        ):
            # 同正文可由多个确认样本引用;只取本次样本的结构化所有者依据。
            review_query = review_query.join(
                experiment_layout_recordings,
                experiment_layout_recordings.c.review_id == tables.reviews.c.review_id,
            ).where(
                experiment_layout_recordings.c.sample_id == facts.sample.sample_id,
                tables.reviews.c.recording_kind == "stage_b_owner_review",
            )
        review_id = connection.execute(
            review_query.order_by(tables.reviews.c.reviewed_at.desc())
        ).scalar()
        result = ReadBasis(
            root_id=facts.root.root_id,
            purpose=facts.root.purpose.value,
            decision_id=facts.decision.fact.reference,
            pdf_id=facts.pdf.attachment_id,
            sample_id=facts.sample.sample_id if facts.sample else None,
            quality_basis=facts.extraction.quality.basis.value,
            review_id=review_id,
            execution_source=facts.execution_source.value,
            recorded_at=datetime.now(UTC).isoformat(),
        ).encode()
        self.validate_read_basis_in_connection(
            connection, facts.paper_id, identity, result
        )
        return result

    def validate_read_basis_in_connection(
        self,
        connection: Connection,
        paper_id: str,
        identity: "ExtractionIdentity",
        basis: dict[str, str | None],
    ) -> None:
        """核验历史领取的独立依据;不要求它仍是当前人工决定或当前PDF。"""
        from datetime import datetime

        from paper_radar.body.extraction import extraction_view
        from paper_radar.body.facts import execution_source
        from paper_radar.screening.reasons import ScreeningResult

        record = ReadBasis.decode(basis)
        root = root_fact(connection)
        decision = next(
            (
                d
                for d in decision_events(connection, paper_id)
                if d.fact.reference == record.decision_id
            ),
            None,
        )
        pdf = (
            connection.execute(
                select(tables.pdfs).where(tables.pdfs.c.attachment_id == record.pdf_id)
            )
            .mappings()
            .first()
        )
        extraction = extraction_view(connection, identity.extraction_fingerprint)
        if (
            (root.root_id, root.purpose.value) != (record.root_id, record.purpose)
            or decision is None
            or decision.fact.record.result is not ScreeningResult.ACCEPTED
            or execution_source(connection, paper_id, decision).value
            != record.execution_source
            or record.execution_source != ExecutionSource.PRODUCTION
        ):
            raise BodyError("corrupt_reference")
        if (
            pdf is None
            or pdf["paper_id"] != paper_id
            or extraction is None
            or extraction.identity != identity
            or extraction.pdf_sha256 != pdf["pdf_sha256"]
        ):
            raise BodyError("corrupt_reference")
        raw_pdf = self.store.read_artifact_in_connection(
            connection, pdf["artifact_id"]
        )["payload"]
        if not valid_pdf_bytes(raw_pdf, pdf["pdf_sha256"]):
            raise BodyError("corrupt_reference")
        if record.purpose == RootPurpose.EXPERIMENT:
            sample = (
                connection.execute(
                    select(tables.samples).where(
                        tables.samples.c.sample_id == record.sample_id
                    )
                )
                .mappings()
                .first()
            )
            if sample is None or (
                sample["paper_id"],
                sample["version_id"],
                sample["pdf_sha256"],
            ) != (paper_id, pdf["version_id"], pdf["pdf_sha256"]):
                raise BodyError("corrupt_reference")
        if record.quality_basis == QualityBasis.EXPERIMENT_DOCUMENT_GATE:
            review = (
                connection.execute(
                    select(tables.reviews).where(
                        tables.reviews.c.review_id == record.review_id
                    )
                )
                .mappings()
                .first()
            )
            if (
                review is None
                or review["passed"] != 1
                or (
                    review["fingerprint"],
                    review["reading_sha256"],
                    review["evidence_map_sha256"],
                )
                != (
                    identity.extraction_fingerprint,
                    identity.reading_sha256,
                    identity.evidence_map_sha256,
                )
            ):
                raise BodyError("corrupt_reference")
            if record.recorded_at is None or datetime.fromisoformat(
                review["reviewed_at"]
            ) > datetime.fromisoformat(record.recorded_at):
                raise BodyError("corrupt_reference")
        elif (
            record.quality_basis != QualityBasis.FORMAL_GATE
            or record.purpose != RootPurpose.PRODUCTION
            or extraction.quality.basis is not QualityBasis.FORMAL_GATE
        ):
            raise BodyError("corrupt_reference")

    def validate_all(self) -> None:
        from paper_radar.body.validation import validate_all

        validate_all(self.database, self.data_root)
