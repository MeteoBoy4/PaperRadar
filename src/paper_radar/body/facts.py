"""在调用者的 Connection 中装配前置事实,不打开另一个数据库视图。"""

from sqlalchemy import Connection, select

from paper_radar.body import tables
from paper_radar.body.extraction import extraction_view
from paper_radar.body.models import BodyError, BodyFacts, BodyReason, DecisionEvent
from paper_radar.calibration.visibility import evaluate_visibility
from paper_radar.eligibility import (
    ArtifactFact,
    Concept,
    ExecutionSource,
    ExtractionFact,
    ExtractionState,
    PaperProjection,
    Presence,
    QualityBasis,
    QualityFact,
    RootPurpose,
    evaluate_paper,
)
from paper_radar.papers.queries import load_trace
from paper_radar.reading.context import ExtractionIdentity
from paper_radar.screening.reasons import ScreeningResult
from paper_radar.screening_tasks.success_rules import stored_candidate
from paper_radar.screening_tasks.tables import budgets, successes


def project_facts(facts: BodyFacts) -> PaperProjection:
    """同一 Body 事实转换,只装配共享字段,资格仍由 evaluate_paper 计算。"""
    pdf, extraction = facts.pdf, facts.extraction
    extracted = ExtractionFact(ExtractionState.ABSENT)
    if extraction is not None and pdf is not None:
        failed = bool(extraction.attempts and extraction.attempts[-1].failure)
        if failed or extraction.artifact_id is not None:
            extracted = ExtractionFact(
                ExtractionState.FAILED if failed else ExtractionState.SUCCEEDED,
                extraction.artifact_id,
                pdf.artifact_id,
                "current",
            )
    return PaperProjection(
        facts.paper_id,
        facts.version_id,
        facts.version_id,
        canonical_id=facts.paper_id,
        revision_no=facts.revision_no,
        decisions=(facts.decision.fact,) if facts.decision else (),
        pdf=ArtifactFact(Presence.PRESENT, pdf.artifact_id, pdf.version_id, "current")
        if pdf
        else ArtifactFact(Presence.ABSENT),
        extraction=extracted,
        quality=extraction.quality if extraction else QualityFact(QualityBasis.ABSENT),
        root_purpose=facts.root.purpose,
        execution_source=facts.execution_source,
        visibility=evaluate_visibility(frozenset()),
    )


def current_projection(connection: Connection, paper_id: str) -> PaperProjection:
    """当前选择优先;唯一同 PDF 失败只作诊断,多输入歧义不选第一条。"""
    from dataclasses import replace

    from paper_radar.body.queries import current_body, current_pdf

    current = load_trace(connection, paper_id).current
    body = current_body(connection, paper_id)
    fingerprint = None
    ambiguous = body.reason == "ambiguous_extractions"
    if body.identity is None and not ambiguous:
        pdf = current_pdf(connection, paper_id, current.version_id)
        if pdf is not None:
            keys = tuple(
                connection.execute(
                    select(tables.inputs.c.fingerprint).where(
                        tables.inputs.c.pdf_sha256 == pdf.pdf_sha256
                    )
                ).scalars()
            )
            if len(keys) == 1:
                fingerprint = keys[0]
            elif keys:
                ambiguous = True
    facts = assemble_facts(
        connection, paper_id, identity=body.identity, fingerprint=fingerprint
    )
    projection = project_facts(facts)
    if ambiguous:
        projection = replace(
            projection, extraction=ExtractionFact(), quality=QualityFact()
        )
    return projection


def execution_source(
    connection: Connection, paper_id: str, decision: DecisionEvent | None
) -> ExecutionSource:
    if decision is None or not decision.screening_references:
        return ExecutionSource.UNKNOWN
    kinds = []
    for reference in decision.screening_references:
        row = (
            connection.execute(
                select(successes.c.audit_json, budgets.c.paper_id)
                .select_from(
                    successes.join(
                        budgets, successes.c.budget_id == budgets.c.budget_id
                    )
                )
                .where(successes.c.success_id == reference)
            )
            .mappings()
            .first()
        )
        if row is None or row["paper_id"] != paper_id:
            raise BodyError("corrupt_reference")
        kinds.append(stored_candidate(b"", row["audit_json"]).executor_kind)
    return ExecutionSource.TEST if "test" in kinds else ExecutionSource.PRODUCTION


def assemble_facts(
    connection: Connection,
    paper_id: str,
    *,
    identity: ExtractionIdentity | None = None,
    fingerprint: str | None = None,
    ordinary: bool = False,
) -> BodyFacts:
    from paper_radar.body.queries import (
        current_body,
        current_pdf,
        decision_events,
        root_fact,
        sample_record,
    )

    trace = load_trace(connection, paper_id)
    current = trace.current
    root = root_fact(connection)
    decisions = decision_events(connection, paper_id)
    projection = PaperProjection(
        paper_id,
        current.version_id,
        current.version_id,
        canonical_id=paper_id,
        revision_no=current.revision_no,
        decisions=tuple(item.fact for item in decisions),
        visibility=evaluate_visibility(frozenset()),
    )
    effective = evaluate_paper(projection)[Concept.EFFECTIVE_SCREENING_DECISION]
    chosen = next(
        (
            item
            for item in decisions
            if effective.decision is not None
            and item.fact.reference == effective.decision.reference
        ),
        None,
    )
    source = execution_source(connection, paper_id, chosen)
    pdf = current_pdf(connection, paper_id, current.version_id)
    key = identity.extraction_fingerprint if identity else fingerprint
    extraction = extraction_view(connection, key) if key else None
    row = (
        connection.execute(
            select(tables.samples)
            .where(tables.samples.c.paper_id == paper_id)
            .order_by(tables.samples.c.sequence.desc())
        )
        .mappings()
        .first()
    )
    sample = sample_record(row) if row else None
    reasons: set[BodyReason] = set()
    if chosen is None or chosen.fact.record.result is not ScreeningResult.ACCEPTED:
        reasons.add(BodyReason.DECISION_NOT_ACCEPTED)
    if root.purpose is RootPurpose.UNKNOWN:
        reasons.add(BodyReason.ROOT_UNKNOWN)
    if source is ExecutionSource.UNKNOWN:
        reasons.add(BodyReason.EXECUTION_SOURCE_UNKNOWN)
    elif source is ExecutionSource.TEST:
        reasons.add(BodyReason.TEST_EXECUTION_SOURCE)
    if pdf is None:
        reasons.add(BodyReason.PDF_ABSENT)
    if extraction is None:
        reasons.add(BodyReason.EXTRACTION_ABSENT)
        reasons.add(BodyReason.QUALITY_ABSENT)
    else:
        if (
            extraction.identity is not None
            and current_body(connection, paper_id).identity != extraction.identity
        ):
            reasons.add(BodyReason.FACTS_CHANGED)
        if identity is not None and extraction.identity != identity:
            reasons.add(BodyReason.FACTS_CHANGED)
        if pdf is None or pdf.pdf_sha256 != extraction.pdf_sha256:
            reasons.add(BodyReason.FACTS_CHANGED)
        if extraction.artifact_id is None or any(
            attempt.failure is not None for attempt in extraction.attempts[-1:]
        ):
            reasons.add(BodyReason.EXTRACTION_FAILED)
        if extraction.quality.basis is QualityBasis.FAILED:
            reasons.add(BodyReason.QUALITY_FAILED)
        elif extraction.quality.basis in {QualityBasis.ABSENT, QualityBasis.UNKNOWN}:
            reasons.add(BodyReason.QUALITY_ABSENT)
        elif (
            root.purpose is RootPurpose.PRODUCTION
            and extraction.quality.basis is not QualityBasis.FORMAL_GATE
        ):
            reasons.add(BodyReason.ORDINARY_CONSUMPTION_DENIED)
    if root.purpose is RootPurpose.EXPERIMENT:
        if (
            sample is None
            or pdf is None
            or (sample.version_id, sample.pdf_sha256)
            != (pdf.version_id, pdf.pdf_sha256)
        ):
            reasons.add(BodyReason.SAMPLE_MISMATCH)
        if ordinary:
            reasons.add(BodyReason.ORDINARY_CONSUMPTION_DENIED)
    return BodyFacts(
        paper_id,
        current.version_id,
        current.revision_no,
        root,
        chosen,
        source,
        pdf,
        extraction,
        sample,
        tuple(reason for reason in BodyReason if reason in reasons),
    )
