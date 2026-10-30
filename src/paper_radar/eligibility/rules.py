"""共享资格判定;只消费本次已加载事实。"""

from collections.abc import Iterable
from dataclasses import replace

from paper_radar.calibration.visibility import (
    HiddenCondition,
    VisibilityCapability,
    VisibilityPermission,
)
from paper_radar.eligibility.models import (
    ArtifactFact,
    Concept,
    DecisionFact,
    Eligibility,
    EligibilityReason,
    ExecutionSource,
    ExtractionState,
    GateState,
    PaperProjection,
    Presence,
    QualityBasis,
    RootPurpose,
    Support,
)
from paper_radar.screening.reasons import (
    ScreeningDecision,
    ScreeningFailureProjection,
    ScreeningResult,
    build_screening_reason,
)


def _result(
    reasons: set[EligibilityReason],
    *,
    support: Support = Support.SUPPORTED,
    scope: str = "predicate_only",
) -> Eligibility:
    return Eligibility(
        not reasons,
        tuple(reason for reason in EligibilityReason if reason in reasons),
        support,
        scope,
    )


def evaluate_paper(facts: PaperProjection) -> dict[Concept, Eligibility]:
    canonical = set[EligibilityReason]()
    if not facts.paper_id or facts.canonical_id == "":
        canonical.add(EligibilityReason.IDENTITY_CONTRADICTORY)
    if facts.canonical_id is None:
        canonical.add(EligibilityReason.CANONICAL_UNKNOWN)
    elif facts.canonical_id != facts.paper_id:
        canonical.add(EligibilityReason.NOT_CANONICAL)
    version = set[EligibilityReason]()
    if not facts.version_id or facts.current_version_id == "" or facts.revision_no < 1:
        version.add(EligibilityReason.IDENTITY_CONTRADICTORY)
    if facts.current_version_id is None:
        version.add(EligibilityReason.VERSION_UNKNOWN)
    elif facts.version_id != facts.current_version_id:
        version.add(EligibilityReason.NOT_CURRENT_VERSION)
    metadata = canonical | version
    m = facts.metadata
    if m is None:
        metadata.add(EligibilityReason.METADATA_UNKNOWN)
    else:
        missing_reasons = {
            "current_version_changed": EligibilityReason.METADATA_STALE,
            "no_title": EligibilityReason.METADATA_NO_TITLE,
            "no_abstract": EligibilityReason.METADATA_NO_ABSTRACT,
            "unknown_truncation": EligibilityReason.METADATA_UNKNOWN_TRUNCATION,
            "no_source_url": EligibilityReason.METADATA_NO_SOURCE_URL,
            "routes_incomplete": EligibilityReason.METADATA_ROUTES_INCOMPLETE,
            "agency_unknown": EligibilityReason.METADATA_AGENCY_UNKNOWN,
            "agency_unsupported": EligibilityReason.METADATA_AGENCY_UNSUPPORTED,
        }
        metadata.update(missing_reasons[missing] for missing in m.missing)
        if (
            m.minimum_complete == bool(m.missing)
            or (m.nontruncated_complete and not m.minimum_complete)
            or m.paper_id != facts.paper_id
        ):
            metadata.add(EligibilityReason.METADATA_CONTRADICTORY)
        if not m.minimum_complete:
            metadata.add(EligibilityReason.METADATA_INCOMPLETE)
        if (
            not m.current_version
            or m.version_id != facts.version_id
            or (m.revision_no != facts.revision_no)
        ):
            metadata.add(EligibilityReason.METADATA_STALE)
    screening = canonical | version
    artifact = facts.screening
    if _artifact_presence_contradictory(artifact):
        screening.add(EligibilityReason.SCREENING_CONTRADICTORY)
    if artifact.presence is Presence.ABSENT:
        screening.add(EligibilityReason.SCREENING_ABSENT)
    elif artifact.presence is Presence.UNKNOWN:
        screening.add(EligibilityReason.SCREENING_UNKNOWN)
    else:
        if (
            not artifact.reference
            or artifact.version_id is None
            or (
                artifact.version_id != facts.version_id
                and artifact.applicability == "current"
            )
        ):
            screening.add(EligibilityReason.SCREENING_CONTRADICTORY)
        if artifact.applicability == "historical":
            screening.add(EligibilityReason.SCREENING_HISTORICAL)
        elif artifact.applicability != "current":
            screening.add(EligibilityReason.SCREENING_UNKNOWN)
    effective = _decision(facts, canonical | version, screening)
    stale = set(effective.reasons)
    if effective.decision is not None:
        match effective.decision.applicability:
            case "historical":
                pass
            case "current":
                stale.add(EligibilityReason.DECISION_BASIS_CURRENT)
            case _:
                stale.add(EligibilityReason.DECISION_BASIS_UNKNOWN)
    accepted = set(effective.reasons)
    if effective.decision is not None and (
        effective.decision.record.result is not ScreeningResult.ACCEPTED
    ):
        accepted.add(EligibilityReason.DECISION_NOT_ACCEPTED)
    pdf = _pdf(facts)
    extraction = _extraction(facts)
    needs_pdf = accepted | pdf
    if facts.pdf.presence is Presence.ABSENT or EligibilityReason.PDF_HISTORICAL in pdf:
        needs_pdf.discard(EligibilityReason.PDF_ABSENT)
        needs_pdf.discard(EligibilityReason.PDF_HISTORICAL)
    elif not pdf:
        needs_pdf.add(EligibilityReason.PDF_ALREADY_PRESENT)
    needs_extraction = accepted | pdf | extraction
    if (
        facts.extraction.state is ExtractionState.ABSENT
        or EligibilityReason.EXTRACTION_HISTORICAL in extraction
    ):
        needs_extraction.discard(EligibilityReason.EXTRACTION_ABSENT)
        needs_extraction.discard(EligibilityReason.EXTRACTION_HISTORICAL)
        needs_extraction.discard(EligibilityReason.EXTRACTION_RETRY_REQUIRED)
    elif facts.extraction.state is ExtractionState.SUCCEEDED and not extraction:
        needs_extraction.add(EligibilityReason.EXTRACTION_ALREADY_PRESENT)
    failed = canonical | version | pdf | extraction
    failed.discard(EligibilityReason.EXTRACTION_RETRY_REQUIRED)
    if facts.extraction.state is not ExtractionState.FAILED:
        failed.add(EligibilityReason.EXTRACTION_NOT_FAILED)
    read = accepted | metadata | pdf | extraction | _quality(facts)
    if facts.execution_source is ExecutionSource.UNKNOWN:
        read.add(EligibilityReason.EXECUTION_SOURCE_UNKNOWN)
    elif facts.execution_source is ExecutionSource.TEST:
        read.add(EligibilityReason.TEST_EXECUTION_SOURCE)
    if facts.visibility is None:
        read.add(EligibilityReason.VISIBILITY_UNKNOWN)
    elif facts.visibility.permission(VisibilityCapability.READING_REQUEST) is not (
        VisibilityPermission.ALLOWED
    ):
        read.add(EligibilityReason.VISIBILITY_DENIED)
    auto = read.copy()
    if facts.root_purpose is RootPurpose.EXPERIMENT:
        auto.add(EligibilityReason.EXPERIMENT_NO_AUTO_QUEUE)
    manual = read.copy()
    request = facts.manual_request
    if request is None:
        manual.add(EligibilityReason.MANUAL_REQUEST_ABSENT)
    else:
        if (
            not request.reference
            or request.paper_id != facts.paper_id
            or (not request.accepted_decision_reference)
        ):
            manual.add(EligibilityReason.MANUAL_REQUEST_CONTRADICTORY)
        if effective.decision is not None and (
            request.accepted_decision_reference != effective.decision.reference
        ):
            manual.add(EligibilityReason.MANUAL_REQUEST_SUPERSEDED)
    waiting = set[EligibilityReason]()
    if facts.visibility is None:
        waiting.add(EligibilityReason.VISIBILITY_UNKNOWN)
    elif HiddenCondition.WAITING_CALIBRATION not in facts.visibility.hidden_conditions:
        waiting.add(EligibilityReason.NOT_WAITING_CALIBRATION)
    results = {
        Concept.CANONICAL_PAPER: _result(canonical),
        Concept.CURRENT_VERSION: _result(version),
        Concept.METADATA_READY: _result(
            metadata,
            support=Support.PARTIAL,
            scope="minimum_metadata_only",
        ),
        Concept.EFFECTIVE_SCREENING_DECISION: effective,
        Concept.DECISION_BASIS_STALE: _result(stale),
        Concept.CURRENT_SCREENING_ARTIFACT: _result(screening),
        Concept.NEEDS_PDF: _result(needs_pdf),
        Concept.NEEDS_EXTRACTION: _result(needs_extraction),
        Concept.EXTRACTION_FAILED: _result(failed),
        Concept.READ_PREREQUISITES: replace(
            _result(
                read,
                support=Support.PARTIAL,
                scope="read_prerequisites_only_no_rank_capacity_claim_or_budget",
            ),
            quality_failure=facts.quality.failure,
        ),
        Concept.ELIGIBLE_FOR_AUTO_READ: replace(
            _result(
                auto,
                support=Support.PARTIAL,
                scope="read_prerequisites_only_no_rank_capacity_claim_or_budget",
            ),
            quality_failure=facts.quality.failure,
        ),
        Concept.REQUESTED_MANUAL_READ: replace(
            _result(manual, scope="explicit_read_prerequisites_no_claim_or_budget"),
            quality_failure=facts.quality.failure,
        ),
        Concept.WAITING_CALIBRATION: _result(
            waiting,
            support=Support.PARTIAL,
            scope="supplied_visibility_fact_only",
        ),
    }
    deferred = {
        Concept.METADATA_UNOBTAINABLE: "C",
        Concept.CURRENT_SCREENING_SUGGESTION: "B/D",
        Concept.NEEDS_REFERENCE_HARVEST: "E",
        Concept.REFERENCE_LIST_COMPLETENESS: "E",
        Concept.NEEDS_REUSE_ASSESSMENT: "D",
        Concept.REUSE_ESCALATION_UNAVAILABLE: "D",
        Concept.MANUAL_ACCEPTED_CHANNEL: "G/H",
        Concept.ACCEPTED_READ_BACKLOG: "G/H",
        Concept.MODEL_FAILURE_QUEUE: "B",
        Concept.WAITING_REVIEW: "B/H",
        Concept.WAITING_REPORT: "B/H",
        Concept.CAPACITY_WARNING: "G/H",
    }
    for concept, owner in deferred.items():
        results[concept] = Eligibility(
            None,
            support=Support.DEFERRED,
            scope="downstream_responsibility",
            owner=owner,
        )
    return {concept: results[concept] for concept in Concept}


def evaluate_concept(
    concept: Concept,
    papers: Iterable[PaperProjection],
) -> dict[str, Eligibility]:
    """按概念批量投影;没有查询或领取副作用,重复身份仅拒绝其自身。"""
    results: dict[str, Eligibility] = {}
    for paper in papers:
        if paper.paper_id in results:
            previous = results[paper.paper_id]
            results[paper.paper_id] = replace(
                previous,
                eligible=None if previous.support is Support.DEFERRED else False,
                decision=None,
                quality_failure=None,
                reasons=(EligibilityReason.DUPLICATE_PAPER,),
            )
        else:
            results[paper.paper_id] = evaluate_paper(paper)[concept]
    return dict(sorted(results.items()))


def _decision(
    facts: PaperProjection,
    prerequisites: set[EligibilityReason],
    screening: set[EligibilityReason],
) -> Eligibility:
    reasons = prerequisites.copy()
    humans: list[DecisionFact] = []
    systems: list[DecisionFact] = []
    projections = False
    for item in facts.decisions:
        if (
            item.paper_id != facts.paper_id
            or not item.reference
            or item.sequence < 0
            or item.record.invalid_combination_fields()
        ):
            reasons.add(EligibilityReason.DECISION_CONTRADICTORY)
            continue
        record = build_screening_reason(item.record)
        if isinstance(record, ScreeningDecision):
            humans.append(item)
        elif isinstance(record, ScreeningFailureProjection):
            projections = True
        else:
            systems.append(item)
    candidates = humans or systems
    chosen = None
    if candidates:
        latest = max(item.sequence for item in candidates)
        winners = [item for item in candidates if item.sequence == latest]
        if len(winners) != 1:
            reasons.add(EligibilityReason.DECISION_CONTRADICTORY)
        else:
            chosen = winners[0]
        if not humans:
            reasons.update(screening)
            if chosen is not None and chosen.screening_reference != (
                facts.screening.reference
            ):
                reasons.add(EligibilityReason.DECISION_CONTRADICTORY)
            if chosen is not None and chosen.applicability != "current":
                reasons.add(EligibilityReason.DECISION_NOT_CURRENT)
            if facts.visibility is None:
                reasons.add(EligibilityReason.VISIBILITY_UNKNOWN)
            elif facts.visibility.permission(
                VisibilityCapability.AGENT_CONTENT
            ) is not (VisibilityPermission.ALLOWED):
                reasons.add(EligibilityReason.VISIBILITY_DENIED)
            gate_reason = {
                GateState.PAUSED: EligibilityReason.GATE_PAUSED,
                GateState.DISABLED: EligibilityReason.GATE_DISABLED,
                GateState.UNKNOWN: EligibilityReason.GATE_UNKNOWN,
            }.get(facts.gate)
            if gate_reason is not None:
                reasons.add(gate_reason)
    else:
        reasons.add(EligibilityReason.DECISION_ABSENT)
        if projections:
            reasons.add(EligibilityReason.PROJECTION_NOT_DECISION)
    return replace(_result(reasons), decision=chosen if not reasons else None)


def _artifact_presence_contradictory(artifact: ArtifactFact) -> bool:
    return artifact.presence is not Presence.PRESENT and (
        artifact.reference is not None
        or artifact.version_id is not None
        or artifact.applicability != "undeterminable"
    )


def _pdf(facts: PaperProjection) -> set[EligibilityReason]:
    pdf = facts.pdf
    reasons = set[EligibilityReason]()
    if _artifact_presence_contradictory(pdf):
        reasons.add(EligibilityReason.PDF_CONTRADICTORY)
    if pdf.presence is Presence.ABSENT:
        reasons.add(EligibilityReason.PDF_ABSENT)
    elif pdf.presence is Presence.UNKNOWN:
        reasons.add(EligibilityReason.PDF_UNKNOWN)
    else:
        if not pdf.reference or pdf.version_id is None:
            reasons.add(EligibilityReason.PDF_CONTRADICTORY)
        elif pdf.applicability == "historical":
            reasons.add(EligibilityReason.PDF_HISTORICAL)
        elif pdf.version_id != facts.version_id:
            reasons.add(EligibilityReason.PDF_CONTRADICTORY)
        if pdf.applicability not in {"current", "historical"}:
            reasons.add(EligibilityReason.PDF_UNKNOWN)
    return reasons


def _extraction(facts: PaperProjection) -> set[EligibilityReason]:
    item = facts.extraction
    reasons = set[EligibilityReason]()
    if item.state in {ExtractionState.ABSENT, ExtractionState.UNKNOWN} and (
        item.reference is not None
        or item.pdf_reference is not None
        or item.applicability != "undeterminable"
    ):
        reasons.add(EligibilityReason.EXTRACTION_CONTRADICTORY)
    match item.state:
        case ExtractionState.ABSENT:
            reasons.add(EligibilityReason.EXTRACTION_ABSENT)
        case ExtractionState.UNKNOWN:
            reasons.add(EligibilityReason.EXTRACTION_UNKNOWN)
        case _:
            if item.state is ExtractionState.FAILED:
                reasons.add(EligibilityReason.EXTRACTION_RETRY_REQUIRED)
            elif not item.reference:
                reasons.add(EligibilityReason.EXTRACTION_CONTRADICTORY)
            if item.pdf_reference is None:
                reasons.add(EligibilityReason.EXTRACTION_CONTRADICTORY)
            elif item.applicability == "historical":
                reasons.add(EligibilityReason.EXTRACTION_HISTORICAL)
            elif item.pdf_reference != facts.pdf.reference:
                reasons.add(EligibilityReason.EXTRACTION_CONTRADICTORY)
            if item.applicability not in {"current", "historical"}:
                reasons.add(EligibilityReason.EXTRACTION_UNKNOWN)
    return reasons


def _quality(facts: PaperProjection) -> set[EligibilityReason]:
    quality = facts.quality
    reasons = set[EligibilityReason]()
    if quality.basis in {QualityBasis.ABSENT, QualityBasis.UNKNOWN} and (
        quality.extraction_reference is not None or quality.failure is not None
    ):
        reasons.add(EligibilityReason.QUALITY_CONTRADICTORY)
    if facts.root_purpose is RootPurpose.UNKNOWN:
        reasons.add(EligibilityReason.ROOT_UNKNOWN)
    match quality.basis:
        case QualityBasis.FAILED:
            reasons.add(EligibilityReason.QUALITY_FAILED)
            if quality.failure is None:
                reasons.add(EligibilityReason.QUALITY_CONTRADICTORY)
        case QualityBasis.ABSENT:
            reasons.add(EligibilityReason.QUALITY_ABSENT)
        case QualityBasis.UNKNOWN:
            reasons.add(EligibilityReason.QUALITY_UNKNOWN)
        case _:
            if (
                not quality.extraction_reference
                or (quality.extraction_reference != facts.extraction.reference)
                or quality.failure is not None
            ):
                reasons.add(EligibilityReason.QUALITY_CONTRADICTORY)
            if quality.basis is QualityBasis.EXPERIMENT_DOCUMENT_GATE and (
                facts.root_purpose is RootPurpose.PRODUCTION
            ):
                reasons.add(EligibilityReason.QUALITY_NOT_FORMAL)
    return reasons
