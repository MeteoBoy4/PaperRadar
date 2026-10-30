"""审查回归:公共纯规则的请求、Read 前置和类型契约。"""

from dataclasses import replace

import pytest

from paper_radar.eligibility import (
    ArtifactFact,
    Concept,
    DecisionFact,
    ExecutionSource,
    ExtractionFact,
    ExtractionState,
    GateState,
    ManualReadRequest,
    PaperProjection,
    Presence,
    QualityBasis,
    QualityFact,
    QualityFailure,
    RootPurpose,
    evaluate_concept,
    evaluate_paper,
)
from paper_radar.screening.reasons import ScreeningReasonInput
from paper_radar.screening_tasks.success_models import Applicability
from tests.test_eligibility import read_paper


def system_accepted_paper() -> PaperProjection:
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
        screening_reference="screening-1",
    )
    return replace(
        read_paper(),
        decisions=(system,),
        gate=GateState.ENABLED,
        screening=ArtifactFact(Presence.PRESENT, "screening-1", "v1", "current"),
    )


def test_current_system_accepted_only_needs_a_request() -> None:
    facts = system_accepted_paper()
    requested = replace(
        facts,
        manual_request=ManualReadRequest("request-1", "paper-a", "system"),
    )
    result = evaluate_paper(requested)
    assert result[Concept.EFFECTIVE_SCREENING_DECISION].eligible is True
    assert result[Concept.ELIGIBLE_FOR_AUTO_READ].eligible is True
    assert result[Concept.REQUESTED_MANUAL_READ].reasons == ()
    assert result[Concept.REQUESTED_MANUAL_READ].eligible is True
    assert requested.decisions == facts.decisions


def test_experiment_single_read_prerequisites_do_not_require_a_request() -> None:
    facts = replace(
        read_paper(),
        root_purpose=RootPurpose.EXPERIMENT,
        quality=QualityFact(QualityBasis.EXPERIMENT_DOCUMENT_GATE, "body-1"),
    )
    result = evaluate_paper(facts)
    prerequisites = result[Concept.READ_PREREQUISITES]
    assert prerequisites.eligible is True
    assert prerequisites.reasons == ()
    assert prerequisites.support == "partial"
    assert (
        prerequisites.scope
        == "read_prerequisites_only_no_rank_capacity_claim_or_budget"
    )
    assert result[Concept.ELIGIBLE_FOR_AUTO_READ].reasons == (
        "experiment_no_auto_queue",
    )
    assert result[Concept.REQUESTED_MANUAL_READ].reasons == ("manual_request_absent",)
    assert facts.manual_request is None


def test_applicability_fields_share_a7_closed_vocabulary() -> None:
    from typing import get_args, get_type_hints

    from paper_radar.screening_tasks.success_models import SuccessView

    authority = get_type_hints(SuccessView)["applicability"]
    assert get_args(authority) == ("current", "historical", "undeterminable")
    for fact_type in (ArtifactFact, ExtractionFact, DecisionFact):
        assert (
            get_type_hints(fact_type, localns={"Applicability": authority})[
                "applicability"
            ]
            == authority
        )


def test_absent_and_unknown_artifact_references_are_consistently_rejected() -> None:
    for presence, missing in (
        (Presence.ABSENT, "absent"),
        (Presence.UNKNOWN, "unknown"),
    ):
        for fact in (
            ArtifactFact(presence, reference="synthetic-reference"),
            ArtifactFact(presence, version_id="v1"),
            ArtifactFact(presence, applicability="current"),
            ArtifactFact(presence, applicability="historical"),
        ):
            result = evaluate_paper(replace(read_paper(), screening=fact, pdf=fact))
            assert result[Concept.CURRENT_SCREENING_ARTIFACT].reasons == (
                f"screening_{missing}",
                "screening_contradictory",
            )
            assert result[Concept.READ_PREREQUISITES].reasons == (
                f"pdf_{missing}",
                "pdf_contradictory",
                "extraction_contradictory",
            )


@pytest.mark.parametrize(
    ("gate", "reason"),
    [
        (GateState.ENABLED, ()),
        (GateState.PAUSED, ("gate_paused",)),
        (GateState.DISABLED, ("gate_disabled",)),
        (GateState.UNKNOWN, ("gate_unknown",)),
    ],
)
def test_request_does_not_enable_a_system_decision(
    gate: GateState,
    reason: tuple[str, ...],
) -> None:
    facts = replace(
        system_accepted_paper(),
        gate=gate,
        manual_request=ManualReadRequest("request", "paper-a", "system"),
    )
    result = evaluate_paper(facts)
    for concept in (
        Concept.READ_PREREQUISITES,
        Concept.ELIGIBLE_FOR_AUTO_READ,
        Concept.REQUESTED_MANUAL_READ,
    ):
        assert result[concept].reasons == reason
        assert result[concept].eligible is (not reason)


@pytest.mark.parametrize("basis", ["historical", "undeterminable"])
def test_request_cannot_revive_old_or_unknown_system_basis(
    basis: Applicability,
) -> None:
    facts = system_accepted_paper()
    facts = replace(
        facts,
        decisions=(replace(facts.decisions[0], applicability=basis),),
        manual_request=ManualReadRequest("request", "paper-a", "system"),
    )
    result = evaluate_paper(facts)
    assert result[Concept.READ_PREREQUISITES].reasons == ("decision_not_current",)
    assert result[Concept.REQUESTED_MANUAL_READ].reasons == ("decision_not_current",)


@pytest.mark.parametrize("basis", ["current", "historical", "undeterminable"])
@pytest.mark.parametrize("gate", list(GateState))
@pytest.mark.parametrize("purpose", [RootPurpose.PRODUCTION, RootPurpose.EXPERIMENT])
def test_human_accepted_read_does_not_depend_on_system_gate(
    basis: Applicability,
    gate: GateState,
    purpose: RootPurpose,
) -> None:
    facts = read_paper()
    facts = replace(
        facts,
        decisions=(replace(facts.decisions[0], applicability=basis),),
        gate=gate,
        root_purpose=purpose,
        quality=QualityFact(
            QualityBasis.FORMAL_GATE
            if purpose is RootPurpose.PRODUCTION
            else QualityBasis.EXPERIMENT_DOCUMENT_GATE,
            "body-1",
        ),
    )
    before = evaluate_paper(facts)
    assert before[Concept.READ_PREREQUISITES].eligible is True
    assert before[Concept.REQUESTED_MANUAL_READ].reasons == ("manual_request_absent",)
    requested = replace(
        facts, manual_request=ManualReadRequest("r", "paper-a", "human")
    )
    after = evaluate_paper(requested)
    assert after[Concept.REQUESTED_MANUAL_READ].eligible is True
    assert before[Concept.READ_PREREQUISITES] == after[Concept.READ_PREREQUISITES]
    assert before[Concept.ELIGIBLE_FOR_AUTO_READ].reasons == (
        ("experiment_no_auto_queue",) if purpose is RootPurpose.EXPERIMENT else ()
    )
    assert evaluate_concept(Concept.READ_PREREQUISITES, (facts,)) == {
        "paper-a": before[Concept.READ_PREREQUISITES],
    }


@pytest.mark.parametrize(
    ("result", "reason"), [("pending", "defer_judgment"), ("denied", "low_value")]
)
@pytest.mark.parametrize("source", ["direct_manual_decision", "suggestion_rule"])
def test_pending_and_denied_request_require_callers_accepted_event(
    result: str,
    reason: str,
    source: str,
) -> None:
    facts = system_accepted_paper() if source == "suggestion_rule" else read_paper()
    previous = replace(
        facts.decisions[0],
        record=ScreeningReasonInput.model_validate(
            dict(
                result=result,
                source=source,
                reason=(
                    "boundary_uncertain"
                    if source == "suggestion_rule" and result == "pending"
                    else reason
                ),
            ),
        ),
    )
    facts = replace(
        facts,
        decisions=(previous,),
        manual_request=ManualReadRequest(
            "r",
            "paper-a",
            previous.reference,
        ),
    )
    assert evaluate_paper(facts)[Concept.REQUESTED_MANUAL_READ].reasons == (
        "decision_not_accepted",
    )
    accepted = DecisionFact(
        "manual-accepted",
        "paper-a",
        2,
        ScreeningReasonInput.model_validate(
            dict(
                result="accepted",
                source="manual_read_request",
                reason="manual_read_request",
            )
        ),
        "current",
    )
    updated = replace(
        facts,
        decisions=(previous, accepted),
        manual_request=ManualReadRequest("r", "paper-a", "manual-accepted"),
    )
    assert evaluate_paper(updated)[Concept.REQUESTED_MANUAL_READ].eligible is True
    assert facts.decisions == (previous,)


@pytest.mark.parametrize(
    ("read_request", "reason"),
    [
        (None, "manual_request_absent"),
        (ManualReadRequest("", "paper-a", "system"), "manual_request_contradictory"),
        (ManualReadRequest("r", "other", "system"), "manual_request_contradictory"),
        (ManualReadRequest("r", "paper-a", "old"), "manual_request_superseded"),
    ],
)
def test_request_identity_is_separate_from_read_prerequisites(
    read_request: ManualReadRequest | None,
    reason: str,
) -> None:
    facts = replace(system_accepted_paper(), manual_request=read_request)
    result = evaluate_paper(facts)
    assert result[Concept.READ_PREREQUISITES].eligible is True
    assert result[Concept.ELIGIBLE_FOR_AUTO_READ].eligible is True
    assert result[Concept.REQUESTED_MANUAL_READ].reasons == (reason,)


@pytest.mark.parametrize(
    ("purpose", "quality", "expected"),
    [
        (RootPurpose.PRODUCTION, QualityBasis.FORMAL_GATE, ()),
        (RootPurpose.EXPERIMENT, QualityBasis.FORMAL_GATE, ()),
        (
            RootPurpose.PRODUCTION,
            QualityBasis.EXPERIMENT_DOCUMENT_GATE,
            ("quality_not_formal",),
        ),
        (RootPurpose.EXPERIMENT, QualityBasis.EXPERIMENT_DOCUMENT_GATE, ()),
        (RootPurpose.PRODUCTION, QualityBasis.ABSENT, ("quality_absent",)),
        (RootPurpose.EXPERIMENT, QualityBasis.UNKNOWN, ("quality_unknown",)),
    ],
)
def test_single_read_preserves_quality_and_root_admission(
    purpose: RootPurpose,
    quality: QualityBasis,
    expected: tuple[str, ...],
) -> None:
    facts = replace(
        read_paper(),
        root_purpose=purpose,
        quality=QualityFact(
            quality,
            "body-1"
            if quality
            in {
                QualityBasis.FORMAL_GATE,
                QualityBasis.EXPERIMENT_DOCUMENT_GATE,
            }
            else None,
        ),
    )
    assert evaluate_paper(facts)[Concept.READ_PREREQUISITES].reasons == expected


@pytest.mark.parametrize(
    ("source", "reason"),
    [
        (ExecutionSource.TEST, "test_execution_source"),
        (ExecutionSource.UNKNOWN, "execution_source_unknown"),
    ],
)
def test_single_experiment_read_cannot_bypass_execution_source(
    source: ExecutionSource,
    reason: str,
) -> None:
    facts = replace(
        read_paper(),
        execution_source=source,
        root_purpose=RootPurpose.EXPERIMENT,
        quality=QualityFact(QualityBasis.EXPERIMENT_DOCUMENT_GATE, "body-1"),
    )
    assert evaluate_paper(facts)[Concept.READ_PREREQUISITES].reasons == (reason,)


def test_single_experiment_read_keeps_body_quality_and_metadata_preconditions() -> None:
    facts = replace(
        read_paper(),
        root_purpose=RootPurpose.EXPERIMENT,
        metadata=None,
        pdf=ArtifactFact(Presence.ABSENT),
        extraction=ExtractionFact(ExtractionState.ABSENT),
        quality=QualityFact(
            QualityBasis.FAILED,
            "body-1",
            QualityFailure.EVIDENCE_REPLAY,
        ),
    )
    result = evaluate_paper(facts)[Concept.READ_PREREQUISITES]
    assert result.eligible is False
    assert result.reasons == (
        "metadata_unknown",
        "pdf_absent",
        "extraction_absent",
        "quality_failed",
    )
    assert result.quality_failure == QualityFailure.EVIDENCE_REPLAY


@pytest.mark.parametrize(
    ("screening", "expected"),
    [
        (
            ArtifactFact(Presence.PRESENT, "screening-1", "v1", "historical"),
            ("screening_historical",),
        ),
        (
            ArtifactFact(Presence.PRESENT, "other-screening", "v1", "current"),
            ("decision_contradictory",),
        ),
        (
            ArtifactFact(Presence.PRESENT, "screening-1", "other-version", "current"),
            ("screening_contradictory",),
        ),
    ],
)
def test_system_request_cannot_borrow_old_or_crossed_screening(
    screening: ArtifactFact,
    expected: tuple[str, ...],
) -> None:
    facts = replace(
        system_accepted_paper(),
        screening=screening,
        manual_request=ManualReadRequest("r", "paper-a", "system"),
    )
    result = evaluate_paper(facts)
    assert result[Concept.READ_PREREQUISITES].reasons == expected
    assert result[Concept.REQUESTED_MANUAL_READ].reasons == expected


def test_later_human_denial_wins_over_a_requested_system_acceptance() -> None:
    original = replace(
        system_accepted_paper(),
        manual_request=ManualReadRequest("r", "paper-a", "system"),
    )
    denied = DecisionFact(
        "human-denied",
        "paper-a",
        2,
        ScreeningReasonInput.model_validate(
            dict(
                result="denied",
                source="direct_manual_decision",
                reason="low_value",
            )
        ),
        "current",
    )
    updated = replace(original, decisions=(*original.decisions, denied))
    result = evaluate_paper(updated)
    assert result[Concept.READ_PREREQUISITES].reasons == ("decision_not_accepted",)
    assert result[Concept.REQUESTED_MANUAL_READ].reasons == (
        "decision_not_accepted",
        "manual_request_superseded",
    )
    assert original.manual_request == updated.manual_request
