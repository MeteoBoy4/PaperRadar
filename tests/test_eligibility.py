"""共享资格公共边界的合成事实证据;不进入历史固定分母。"""

from dataclasses import replace

import pytest

from paper_radar.calibration.visibility import HiddenCondition, evaluate_visibility
from paper_radar.eligibility import (
    ArtifactFact,
    Concept,
    DecisionFact,
    ExecutionSource,
    ExtractionFact,
    ExtractionState,
    GateState,
    ManualReadRequest,
    MetadataFacts,
    PaperProjection,
    Presence,
    QualityBasis,
    QualityFact,
    QualityFailure,
    RootPurpose,
    evaluate_concept,
    evaluate_paper,
)
from paper_radar.feed_metadata.models import MetadataResult
from paper_radar.screening.reasons import (
    DecisionReason,
    ScreeningReasonInput,
    build_screening_reason,
)
from paper_radar.screening_tasks.success_models import Applicability


def test_identity_is_evaluated_without_inventing_a_merge_state() -> None:
    result = evaluate_paper(
        PaperProjection(paper_id="paper-a", version_id="v1", current_version_id="v1")
    )
    assert result[Concept.CANONICAL_PAPER].eligible is False
    assert result[Concept.CANONICAL_PAPER].reasons == ("canonical_unknown",)
    assert result[Concept.CURRENT_VERSION].eligible is True
    assert result[Concept.CURRENT_VERSION].reasons == ()


def test_minimum_metadata_consumes_authority_without_reparsing_text() -> None:

    # 安全 trace 会剥离 title;minimum_complete 仍是元数据服务的权威结论。
    metadata = MetadataResult(
        request_key="metadata-1",
        paper_id="paper-a",
        version_id="v1",
        revision_no=1,
        minimum_complete=True,
        nontruncated_complete=False,
    )
    facts = PaperProjection(
        paper_id="paper-a",
        version_id="v1",
        current_version_id="v1",
        canonical_id="paper-a",
        metadata=MetadataFacts.from_result(metadata),
    )
    result = evaluate_paper(facts)[Concept.METADATA_READY]
    assert result.eligible is True
    assert result.reasons == ()
    assert result.support == "partial"
    assert result.scope == "minimum_metadata_only"


def test_old_human_decision_wins_over_system_and_projection() -> None:

    def decision(
        reference: str,
        sequence: int,
        result: str,
        source: str,
        reason: str,
        applicability: Applicability,
    ) -> DecisionFact:
        return DecisionFact(
            reference=reference,
            paper_id="paper-a",
            sequence=sequence,
            record=build_screening_reason(
                ScreeningReasonInput.model_validate(
                    dict(result=result, source=source, reason=reason)
                )
            ),
            applicability=applicability,
        )

    facts = PaperProjection(
        paper_id="paper-a",
        version_id="v2",
        current_version_id="v2",
        canonical_id="paper-a",
        gate=GateState.ENABLED,
        decisions=(
            decision(
                "human",
                1,
                "accepted",
                "direct_manual_decision",
                "user_judgment",
                "historical",
            ),
            decision("system", 2, "denied", "suggestion_rule", "low_value", "current"),
            decision(
                "projection",
                3,
                "pending",
                "failure_queue_projection",
                "model_failure",
                "current",
            ),
        ),
    )
    results = evaluate_paper(facts)
    decision_result = results[Concept.EFFECTIVE_SCREENING_DECISION].decision
    assert decision_result is not None
    assert decision_result.reference == "human"
    assert results[Concept.EFFECTIVE_SCREENING_DECISION].eligible is True
    assert results[Concept.DECISION_BASIS_STALE].eligible is True
    assert results[Concept.DECISION_BASIS_STALE].reasons == ()


def test_current_screening_artifact_uses_a7_applicability_not_historical_success() -> (
    None
):

    facts = PaperProjection(
        paper_id="paper-a",
        version_id="v1",
        current_version_id="v1",
        canonical_id="paper-a",
        screening=ArtifactFact(
            presence=Presence.PRESENT,
            reference="success-1",
            version_id="v1",
            applicability="historical",
        ),
    )
    assert evaluate_paper(facts)[Concept.CURRENT_SCREENING_ARTIFACT].reasons == (
        "screening_historical",
    )
    current = replace(
        facts, screening=replace(facts.screening, applicability="current")
    )
    assert evaluate_paper(current)[Concept.CURRENT_SCREENING_ARTIFACT].eligible is True


def accepted_paper() -> PaperProjection:
    return PaperProjection(
        paper_id="paper-a",
        version_id="v1",
        current_version_id="v1",
        canonical_id="paper-a",
        metadata=MetadataFacts("paper-a", "v1", 1, True, True, True, ()),
        decisions=(
            DecisionFact(
                "human",
                "paper-a",
                1,
                ScreeningReasonInput.model_validate(
                    dict(
                        result="accepted",
                        source="direct_manual_decision",
                        reason="user_judgment",
                    )
                ),
                "current",
            ),
        ),
    )


def test_accepted_pdf_and_extraction_demands_are_independent() -> None:

    facts = replace(accepted_paper(), pdf=ArtifactFact(presence=Presence.ABSENT))
    result = evaluate_paper(facts)
    assert result[Concept.NEEDS_PDF].eligible is True
    assert result[Concept.NEEDS_EXTRACTION].reasons == (
        "pdf_absent",
        "extraction_unknown",
    )
    pdf = ArtifactFact(Presence.PRESENT, "pdf-1", "v1", "current")
    facts = replace(
        facts, pdf=pdf, extraction=ExtractionFact(state=ExtractionState.ABSENT)
    )
    result = evaluate_paper(facts)
    assert result[Concept.NEEDS_PDF].reasons == ("pdf_already_present",)
    assert result[Concept.NEEDS_EXTRACTION].eligible is True
    failed = replace(
        facts,
        extraction=ExtractionFact(
            state=ExtractionState.FAILED, pdf_reference="pdf-1", applicability="current"
        ),
    )
    assert evaluate_paper(failed)[Concept.EXTRACTION_FAILED].eligible is True
    assert evaluate_paper(failed)[Concept.NEEDS_EXTRACTION].reasons == (
        "extraction_retry_required",
    )


def read_paper() -> PaperProjection:
    return replace(
        accepted_paper(),
        gate=GateState.DISABLED,
        root_purpose=RootPurpose.PRODUCTION,
        visibility=evaluate_visibility(frozenset()),
        execution_source=ExecutionSource.PRODUCTION,
        pdf=ArtifactFact(Presence.PRESENT, "pdf-1", "v1", "current"),
        extraction=ExtractionFact(
            ExtractionState.SUCCEEDED, "body-1", "pdf-1", "current"
        ),
        quality=QualityFact(QualityBasis.FORMAL_GATE, "body-1"),
    )


def test_human_accepted_auto_prerequisites_and_explicit_read_request_are_distinct() -> (
    None
):

    facts = read_paper()
    auto = evaluate_paper(facts)[Concept.ELIGIBLE_FOR_AUTO_READ]
    assert auto.eligible is True  # 人工决定不依赖系统校准 enable。
    assert auto.support == "partial"
    assert auto.scope == "read_prerequisites_only_no_rank_capacity_claim_or_budget"
    assert evaluate_paper(facts)[Concept.REQUESTED_MANUAL_READ].reasons == (
        "manual_request_absent",
    )
    requested = replace(
        facts, manual_request=ManualReadRequest("request-1", "paper-a", "human")
    )
    assert evaluate_paper(requested)[Concept.REQUESTED_MANUAL_READ].eligible is True


def test_old_fulltext_triggers_new_demand_and_cannot_supply_current_read() -> None:
    facts = read_paper()
    previous_pdf = replace(
        facts, pdf=replace(facts.pdf, version_id="old", applicability="historical")
    )
    assert evaluate_paper(previous_pdf)[Concept.NEEDS_PDF].eligible is True
    assert (
        "pdf_historical"
        in evaluate_paper(previous_pdf)[Concept.ELIGIBLE_FOR_AUTO_READ].reasons
    )
    previous_body = replace(
        facts,
        extraction=replace(
            facts.extraction, pdf_reference="old-pdf", applicability="historical"
        ),
    )
    assert evaluate_paper(previous_body)[Concept.NEEDS_EXTRACTION].eligible is True
    assert (
        "extraction_historical"
        in evaluate_paper(previous_body)[Concept.ELIGIBLE_FOR_AUTO_READ].reasons
    )
    historical_failure = replace(
        previous_body,
        extraction=replace(previous_body.extraction, state=ExtractionState.FAILED),
    )
    assert (
        evaluate_paper(historical_failure)[Concept.EXTRACTION_FAILED].eligible is False
    )


def test_absent_facts_carrying_success_references_are_contradictory() -> None:
    facts = read_paper()
    contradictory = replace(
        facts,
        pdf=replace(facts.pdf, presence=Presence.ABSENT),
        extraction=replace(facts.extraction, state=ExtractionState.ABSENT),
    )
    result = evaluate_paper(contradictory)
    assert result[Concept.NEEDS_PDF].reasons == ("pdf_contradictory",)
    assert result[Concept.NEEDS_EXTRACTION].reasons == (
        "pdf_absent",
        "pdf_contradictory",
        "extraction_contradictory",
    )


def test_batch_matches_trace_in_any_order_and_isolates_bad_paper() -> None:
    good = read_paper()
    bad = replace(read_paper(), paper_id="paper-b")
    for concept in Concept:
        trace = {
            paper.paper_id: evaluate_paper(paper)[concept] for paper in (good, bad)
        }
        assert evaluate_concept(concept, (good, bad)) == trace
        assert evaluate_concept(concept, (bad, good)) == trace
    assert evaluate_paper(good)[Concept.CURRENT_SCREENING_SUGGESTION].eligible is None
    assert (
        evaluate_paper(good)[Concept.CURRENT_SCREENING_SUGGESTION].support == "deferred"
    )
    assert evaluate_paper(good)[Concept.CURRENT_SCREENING_SUGGESTION].owner == "B/D"


def test_system_decision_requires_current_artifact_basis_and_explicit_gate_enable() -> (
    None
):
    system = DecisionFact(
        "system",
        "paper-a",
        1,
        ScreeningReasonInput.model_validate(
            dict(
                result="accepted",
                source="suggestion_rule",
                reason="high_research_value",
            )
        ),
        "current",
    )
    facts = replace(read_paper(), decisions=(system,), gate=GateState.ENABLED)
    assert evaluate_paper(facts)[Concept.EFFECTIVE_SCREENING_DECISION].eligible is False
    system = replace(system, screening_reference="success-1")
    facts = replace(
        facts,
        decisions=(system,),
        screening=ArtifactFact(Presence.PRESENT, "success-1", "v1", "current"),
    )
    assert evaluate_paper(facts)[Concept.ELIGIBLE_FOR_AUTO_READ].eligible is True
    for state, reason in (
        (GateState.PAUSED, "gate_paused"),
        (GateState.DISABLED, "gate_disabled"),
        (GateState.UNKNOWN, "gate_unknown"),
    ):
        assert evaluate_paper(replace(facts, gate=state))[
            Concept.ELIGIBLE_FOR_AUTO_READ
        ].reasons == (reason,)


def test_metadata_reports_all_authoritative_missing_reasons_in_declaration_order() -> (
    None
):
    facts = replace(
        accepted_paper(),
        metadata=MetadataFacts(
            "paper-a",
            "v1",
            1,
            False,
            False,
            True,
            (
                "agency_unsupported",
                "routes_incomplete",
                "no_source_url",
                "no_abstract",
                "no_title",
            ),
        ),
    )
    assert evaluate_paper(facts)[Concept.METADATA_READY].reasons == (
        "metadata_incomplete",
        "metadata_no_title",
        "metadata_no_abstract",
        "metadata_no_source_url",
        "metadata_routes_incomplete",
        "metadata_agency_unsupported",
    )


# D4: 质量依据与根用途独立;实验根的可读正例属于显式单篇请求。


@pytest.mark.parametrize(
    ("purpose", "basis", "expected"),
    [
        ("production", "formal_gate", ()),
        ("experiment", "formal_gate", ()),
        ("production", "experiment_document_gate", ("quality_not_formal",)),
        ("experiment", "experiment_document_gate", ()),
        ("production", "failed", ("quality_failed",)),
        ("experiment", "failed", ("quality_failed",)),
        ("production", "absent", ("quality_absent",)),
        ("experiment", "absent", ("quality_absent",)),
        ("production", "unknown", ("quality_unknown",)),
        ("experiment", "unknown", ("quality_unknown",)),
    ],
)
def test_read_quality_and_root_purpose_matrix(
    purpose: str,
    basis: str,
    expected: tuple[str, ...],
) -> None:
    failure = QualityFailure.EVIDENCE_REPLAY if basis == "failed" else None
    facts = replace(
        read_paper(),
        root_purpose=RootPurpose(purpose),
        manual_request=ManualReadRequest("request-1", "paper-a", "human"),
        quality=QualityFact(
            QualityBasis(basis),
            "body-1" if basis not in {"absent", "unknown"} else None,
            failure,
        ),
    )
    result = evaluate_paper(facts)[Concept.REQUESTED_MANUAL_READ]
    assert result.reasons == expected
    assert result.eligible is (not expected)
    assert result.quality_failure == failure


@pytest.mark.parametrize(
    ("source", "reason"),
    [
        ("production", ()),
        ("test", ("test_execution_source",)),
        ("unknown", ("execution_source_unknown",)),
    ],
)
def test_execution_source_does_not_follow_experiment_purpose_or_quality(
    source: str,
    reason: tuple[str, ...],
) -> None:
    facts = replace(
        read_paper(),
        root_purpose=RootPurpose.EXPERIMENT,
        execution_source=ExecutionSource(source),
        manual_request=ManualReadRequest("request-1", "paper-a", "human"),
        quality=QualityFact(QualityBasis.EXPERIMENT_DOCUMENT_GATE, "body-1"),
    )
    result = evaluate_paper(facts)
    assert result[Concept.REQUESTED_MANUAL_READ].reasons == reason
    assert "experiment_no_auto_queue" in result[Concept.ELIGIBLE_FOR_AUTO_READ].reasons


@pytest.mark.parametrize("hidden", ["waiting_calibration", "unrevealed"])
def test_read_consumes_visibility_and_does_not_reimplement_hidden_action_rules(
    hidden: str,
) -> None:
    facts = replace(
        read_paper(),
        manual_request=ManualReadRequest("r", "paper-a", "human"),
        visibility=evaluate_visibility(frozenset({HiddenCondition(hidden)})),
    )
    results = evaluate_paper(facts)
    assert results[Concept.REQUESTED_MANUAL_READ].reasons == ("visibility_denied",)
    assert results[Concept.ELIGIBLE_FOR_AUTO_READ].reasons == ("visibility_denied",)
    assert results[Concept.WAITING_CALIBRATION].eligible is (
        hidden == "waiting_calibration"
    )


@pytest.mark.parametrize(
    "source", ["fixed_calibration_member_projection", "failure_queue_projection"]
)
def test_failure_projections_never_become_effective_decisions(source: str) -> None:
    facts = replace(
        read_paper(),
        gate=GateState.ENABLED,
        decisions=(
            DecisionFact(
                "projection",
                "paper-a",
                1,
                ScreeningReasonInput.model_validate(
                    dict(result="pending", source=source, reason="model_failure")
                ),
                "current",
            ),
        ),
    )
    result = evaluate_paper(facts)[Concept.EFFECTIVE_SCREENING_DECISION]
    assert result.eligible is False
    assert result.decision is None
    assert result.reasons == ("decision_absent", "projection_not_decision")


def test_all_missing_read_prerequisites_have_reasons_within_supported_scope() -> None:
    facts = replace(
        accepted_paper(),
        pdf=ArtifactFact(Presence.ABSENT),
        extraction=ExtractionFact(),
        quality=QualityFact(QualityBasis.ABSENT),
    )
    result = evaluate_paper(facts)[Concept.ELIGIBLE_FOR_AUTO_READ]
    assert result.reasons == (
        "pdf_absent",
        "extraction_unknown",
        "quality_absent",
        "root_unknown",
        "execution_source_unknown",
        "visibility_unknown",
    )


def test_later_human_denial_blocks_old_request_without_removing_history() -> None:
    original = replace(
        read_paper(), manual_request=ManualReadRequest("r", "paper-a", "human")
    )
    denied = DecisionFact(
        "denied",
        "paper-a",
        2,
        ScreeningReasonInput.model_validate(
            dict(result="denied", source="direct_manual_decision", reason="low_value")
        ),
        "current",
    )
    updated = replace(original, decisions=(*original.decisions, denied))
    assert evaluate_paper(original)[Concept.REQUESTED_MANUAL_READ].eligible is True
    assert evaluate_paper(updated)[Concept.REQUESTED_MANUAL_READ].reasons == (
        "decision_not_accepted",
        "manual_request_superseded",
    )
    assert updated.decisions[0] == original.decisions[0]


def test_invalid_reason_combination_and_ambiguous_decisions_fail_closed() -> None:
    facts = accepted_paper()
    human = facts.decisions[0]
    invalid = replace(
        human,
        record=human.record.model_copy(
            update={
                "reason": DecisionReason.LOW_VALUE,
            }
        ),
    )
    assert evaluate_paper(replace(facts, decisions=(invalid,)))[
        Concept.EFFECTIVE_SCREENING_DECISION
    ].reasons == (
        "decision_absent",
        "decision_contradictory",
    )
    assert evaluate_paper(
        replace(facts, decisions=(human, replace(human, reference="other")))
    )[Concept.EFFECTIVE_SCREENING_DECISION].reasons == ("decision_contradictory",)


def test_absence_conflicts_with_screening_or_quality_success_evidence() -> None:
    facts = read_paper()
    malformed = replace(
        facts,
        screening=replace(facts.pdf, presence=Presence.ABSENT),
        quality=replace(facts.quality, basis=QualityBasis.ABSENT),
    )
    result = evaluate_paper(malformed)
    assert result[Concept.CURRENT_SCREENING_ARTIFACT].reasons == (
        "screening_absent",
        "screening_contradictory",
    )
    assert result[Concept.ELIGIBLE_FOR_AUTO_READ].reasons == (
        "quality_absent",
        "quality_contradictory",
    )


def test_crossed_current_references_are_contradictions_not_historical_facts() -> None:
    facts = read_paper()
    malformed = replace(
        facts,
        pdf=replace(facts.pdf, version_id="other-version"),
        extraction=replace(facts.extraction, pdf_reference="other-pdf"),
    )
    assert evaluate_paper(malformed)[Concept.ELIGIBLE_FOR_AUTO_READ].reasons == (
        "pdf_contradictory",
        "extraction_contradictory",
    )


def test_duplicate_identity_rejects_itself_without_order_dependent_evidence() -> None:
    good = read_paper()
    other = replace(
        good,
        quality=QualityFact(
            QualityBasis.FAILED, "body-1", QualityFailure.LAYOUT_REVIEW
        ),
    )
    forward = evaluate_concept(Concept.ELIGIBLE_FOR_AUTO_READ, (good, other))
    reverse = evaluate_concept(Concept.ELIGIBLE_FOR_AUTO_READ, (other, good))
    assert forward == reverse
    assert forward["paper-a"].eligible is False
    assert forward["paper-a"].reasons == ("duplicate_paper",)


@pytest.mark.parametrize(
    ("source", "reason", "result"),
    [
        ("blind_calibration", "out_of_scope", "denied"),
        ("regular_review", "defer_judgment", "pending"),
        ("direct_manual_decision", "low_value", "denied"),
        ("metadata_abandonment", "insufficient_metadata", "denied"),
        ("manual_read_request", "manual_read_request", "accepted"),
    ],
)
def test_all_human_sources_keep_priority_over_later_system_acceptance(
    source: str,
    reason: str,
    result: str,
) -> None:
    human = DecisionFact(
        "human",
        "paper-a",
        1,
        ScreeningReasonInput.model_validate(
            dict(result=result, source=source, reason=reason)
        ),
        "historical",
    )
    system = DecisionFact(
        "system",
        "paper-a",
        2,
        ScreeningReasonInput.model_validate(
            dict(
                result="accepted",
                source="suggestion_rule",
                reason="high_research_value",
            )
        ),
        "current",
    )
    results = evaluate_paper(replace(read_paper(), decisions=(system, human)))
    effective = results[Concept.EFFECTIVE_SCREENING_DECISION]
    assert effective.eligible is True
    assert effective.decision == human
    assert results[Concept.DECISION_BASIS_STALE].eligible is True
    assert results[Concept.NEEDS_PDF].eligible is False
    assert results[Concept.ELIGIBLE_FOR_AUTO_READ].eligible is (result == "accepted")


@pytest.mark.parametrize(
    ("canonical", "current", "expected"),
    [
        (None, None, ("canonical_unknown", "version_unknown")),
        ("survivor", "v2", ("not_canonical", "not_current_version")),
    ],
)
def test_unknown_merge_state_and_noncurrent_versions_deny_downstream(
    canonical: str | None,
    current: str | None,
    expected: tuple[str, ...],
) -> None:
    result = evaluate_paper(
        replace(read_paper(), canonical_id=canonical, current_version_id=current)
    )
    assert result[Concept.ELIGIBLE_FOR_AUTO_READ].eligible is False
    assert result[Concept.ELIGIBLE_FOR_AUTO_READ].reasons == expected


@pytest.mark.parametrize(
    ("minimum", "nontruncated", "missing", "expected"),
    [
        (True, True, ("no_title",), ("metadata_contradictory", "metadata_no_title")),
        (False, False, (), ("metadata_incomplete", "metadata_contradictory")),
        (
            False,
            True,
            ("no_abstract",),
            ("metadata_incomplete", "metadata_contradictory", "metadata_no_abstract"),
        ),
    ],
)
def test_inconsistent_metadata_flags_do_not_create_readiness(
    minimum: bool,
    nontruncated: bool,
    missing: tuple[str, ...],
    expected: tuple[str, ...],
) -> None:
    result = MetadataResult.model_validate(
        dict(
            request_key="m",
            paper_id="paper-a",
            version_id="v1",
            revision_no=1,
            minimum_complete=minimum,
            nontruncated_complete=nontruncated,
            missing=missing,
        )
    )
    facts = replace(read_paper(), metadata=MetadataFacts.from_result(result))
    assert evaluate_paper(facts)[Concept.METADATA_READY].reasons == expected


def test_unknown_human_basis_retains_decision_but_does_not_assert_staleness() -> None:
    facts = read_paper()
    human = replace(facts.decisions[0], applicability="undeterminable")
    result = evaluate_paper(replace(facts, decisions=(human,)))
    assert result[Concept.EFFECTIVE_SCREENING_DECISION].decision == human
    assert result[Concept.DECISION_BASIS_STALE].reasons == ("decision_basis_unknown",)


def test_read_request_accepts_system_decision_but_not_other_paper() -> None:
    facts = read_paper()
    wrong_request = replace(
        facts, manual_request=ManualReadRequest("r", "other", "human")
    )
    assert evaluate_paper(wrong_request)[Concept.REQUESTED_MANUAL_READ].reasons == (
        "manual_request_contradictory",
    )
    system = DecisionFact(
        "system",
        "paper-a",
        1,
        ScreeningReasonInput.model_validate(
            dict(
                result="accepted",
                source="suggestion_rule",
                reason="high_research_value",
            )
        ),
        "current",
        screening_reference="s",
    )
    facts = replace(
        facts,
        decisions=(system,),
        gate=GateState.ENABLED,
        screening=ArtifactFact(Presence.PRESENT, "s", "v1", "current"),
        manual_request=ManualReadRequest("r", "paper-a", "system"),
    )
    assert evaluate_paper(facts)[Concept.REQUESTED_MANUAL_READ].reasons == ()


def test_read_quality_cannot_borrow_another_extraction_identity() -> None:
    facts = read_paper()
    wrong_quality = replace(
        facts, quality=replace(facts.quality, extraction_reference="other")
    )
    assert evaluate_paper(wrong_quality)[Concept.ELIGIBLE_FOR_AUTO_READ].reasons == (
        "quality_contradictory",
    )


def test_a7_success_projection_preserves_undeterminable_applicability() -> None:
    from datetime import UTC, datetime

    from paper_radar.screening_tasks.success_models import SuccessReceipt, SuccessView

    view = SuccessView(
        SuccessReceipt(
            "s",
            "task",
            1,
            "artifact",
            "fingerprint",
            "boundary",
            "test",
            datetime(2026, 1, 1, tzinfo=UTC),
        ),
        "undeterminable",
    )
    facts = replace(
        read_paper(), screening=ArtifactFact.from_success(view, version_id="v1")
    )
    assert evaluate_paper(facts)[Concept.CURRENT_SCREENING_ARTIFACT].reasons == (
        "screening_unknown",
    )


def test_reference_harvest_failure_cannot_block_accepted_fulltext_or_read() -> None:
    facts = replace(read_paper(), reference_harvest_failed=True)
    result = evaluate_paper(facts)
    assert result[Concept.ELIGIBLE_FOR_AUTO_READ].eligible is True
    assert result[Concept.NEEDS_REFERENCE_HARVEST].eligible is None
    pending_pdf = replace(facts, pdf=ArtifactFact(Presence.ABSENT))
    assert evaluate_paper(pending_pdf)[Concept.NEEDS_PDF].eligible is True
    pending_body = replace(facts, extraction=ExtractionFact(ExtractionState.ABSENT))
    assert evaluate_paper(pending_body)[Concept.NEEDS_EXTRACTION].eligible is True


def test_empty_identity_cannot_be_mistaken_for_matching_canonical_current_facts() -> (
    None
):
    facts = replace(
        read_paper(),
        paper_id="",
        canonical_id="",
        version_id="",
        current_version_id="",
        revision_no=0,
    )
    result = evaluate_paper(facts)
    assert result[Concept.CANONICAL_PAPER].reasons == ("identity_contradictory",)
    assert result[Concept.CURRENT_VERSION].reasons == ("identity_contradictory",)
    assert result[Concept.ELIGIBLE_FOR_AUTO_READ].eligible is False
