from __future__ import annotations

import pytest
from pydantic import ValidationError

from paper_radar.live_evidence.receipt import ApprovedPlan, EvidenceReceipt


def test_beta_plan_cannot_authorize_network() -> None:
    with pytest.raises(ValidationError) as error:
        ApprovedPlan.model_validate(
            {
                "format_version": "v1",
                "plan_id": "beta-1",
                "kind": "site_beta",
                "collector_sha256": "a" * 64,
                "cases": ["cwd"],
                "starts_at": "2026-11-09T00:00:00Z",
                "ends_at": "2026-11-10T00:00:00Z",
                "max_auth_calls": 0,
                "max_model_calls": 0,
                "max_network_requests": 1,
                "max_rounds": 1,
                "stop_on_first_failure": True,
            }
        )
    assert "beta_budget_nonzero" in str(error.value)


def test_receipt_requires_version_and_rejects_arbitrary_content() -> None:
    with pytest.raises(ValidationError) as error:
        EvidenceReceipt.model_validate({"passed": True, "token": "secret"})
    assert {tuple(item["loc"]) for item in error.value.errors()} >= {
        ("format_version",),
        ("passed",),
        ("token",),
    }


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("binding", {}, "binding_incomplete"),
        (
            "failure_history",
            [{"case_id": "cwd", "reason": "collector_failed"}],
            "failure_history_inconsistent",
        ),
        ("completed_at", "2026-11-08T00:00:00Z", "evidence_time_invalid"),
    ],
)
def test_receipt_rejects_incomplete_or_conflicting_facts(
    field: str, value: object, reason: str
) -> None:
    from tests.live_evidence_ledger_support import receipt

    payload = receipt().model_dump(mode="json")
    payload[field] = value
    with pytest.raises(ValidationError) as error:
        EvidenceReceipt.model_validate(payload)
    assert reason in str(error.value)


def test_beta_cannot_claim_provider_observation() -> None:
    from paper_radar.live_evidence.receipt import validate_against_plan
    from tests.live_evidence_ledger_support import NOW, plan, receipt

    payload = receipt().model_dump(mode="json")
    payload["claims"][0]["capability"] = "model_identity"
    with pytest.raises(ValueError, match="beta_claim_forbidden"):
        validate_against_plan(EvidenceReceipt.model_validate(payload), plan(), now=NOW)


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"plan_sha256": "c" * 64}, "plan_mismatch"),
        ({"round_number": 2}, "plan_budget_exceeded"),
        ({"completed_at": "2026-11-11T00:00:00Z"}, "evidence_time_future"),
    ],
)
def test_plan_is_separate_authority(change: dict[str, object], reason: str) -> None:
    from paper_radar.live_evidence.receipt import validate_against_plan
    from tests.live_evidence_ledger_support import NOW, plan, receipt

    payload = receipt().model_dump(mode="json")
    payload.update(change)
    with pytest.raises(ValueError, match=reason):
        validate_against_plan(EvidenceReceipt.model_validate(payload), plan(), now=NOW)


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"verified_at": None}, "evidence_time_invalid"),
        ({"evidence_at": "2026-11-09T01:01:00"}, "evidence_time_invalid"),
        ({"status": "unknown"}, "evidence_time_invalid"),
    ],
)
def test_claim_time_is_original_and_explicit(
    change: dict[str, object], reason: str
) -> None:
    from tests.live_evidence_ledger_support import receipt

    payload = receipt().model_dump(mode="json")
    payload["claims"][0].update(change)
    with pytest.raises(ValidationError) as error:
        EvidenceReceipt.model_validate(payload)
    assert reason in str(error.value)


def test_beta_rejects_even_one_observed_request() -> None:
    from paper_radar.live_evidence.receipt import validate_against_plan
    from tests.live_evidence_ledger_support import NOW, plan, receipt

    payload = receipt().model_dump(mode="json")
    payload["cases"][0]["network_requests"] = 1
    with pytest.raises(ValueError, match="plan_budget_exceeded"):
        validate_against_plan(EvidenceReceipt.model_validate(payload), plan(), now=NOW)


def test_verified_claim_cannot_cite_unobserved_basis() -> None:
    from tests.live_evidence_ledger_support import receipt

    payload = receipt().model_dump(mode="json")
    payload["claims"][0]["basis"] = "not_observed"
    with pytest.raises(ValidationError) as error:
        EvidenceReceipt.model_validate(payload)
    assert "claim_basis_conflict" in str(error.value)
