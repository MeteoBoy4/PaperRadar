from pathlib import Path

import pytest

from paper_radar.live_evidence.evidence import ExecutionBinding
from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerTrust
from paper_radar.live_evidence.receipt import canonical_bytes
from paper_radar.live_evidence.types import BindingComponent, Capability
from tests.live_evidence_ledger_support import (
    NOW,
    owner_uid,
    plan,
    protected_root,
    receipt,
)


def test_real_loader_projects_protected_activation_and_durable_failed_revocation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from paper_radar.live_evidence import service
    from paper_radar.live_evidence.lifecycle import EvidenceLifecycle, use_for_id

    root = protected_root(tmp_path)
    ledger = EvidenceLedger(root, trust=LedgerTrust(owner_uid(), owner_uid() + 1, root))
    ledger.initialize()
    ledger.approve_plan(plan(), now=NOW)
    source = root / "inbox" / "site.json"
    source.write_bytes(canonical_bytes(receipt()))
    source.chmod(0o644)
    ledger.receive(source, now=NOW)
    lifecycle = EvidenceLifecycle(ledger)
    binding = ExecutionBinding(tuple(receipt().binding.items()))
    review = lifecycle.review(
        receipt().receipt_id,
        "boundary-low",
        binding=binding,
        checked_components=frozenset(BindingComponent),
        now=NOW,
    )
    lifecycle.activate(review, confirmation=receipt().receipt_id, now=NOW)
    monkeypatch.setattr(service, "_ledger", lambda: ledger)
    monkeypatch.setattr(service, "_pending_path", lambda: tmp_path / "pending.jsonl")
    monkeypatch.setattr(service, "_run_helper", lambda arguments: False)
    request = service.AdmissionRequest(
        use_for_id("boundary-low"), binding, frozenset(BindingComponent)
    )
    before = service.load_admission_evidence(request, now=NOW)
    assert before.decision.for_capability(Capability.CWD_ANCESTORS).qualified
    assert not before.decision.executable  # 缺模型等必要能力仍拒绝。
    assert (
        service.request_revocation(
            receipt().receipt_id,
            "boundary-low",
            components=frozenset({BindingComponent.CWD_ANCESTORS}),
            now=NOW,
        )
        is False
    )
    after = service.load_admission_evidence(request, now=NOW)
    assert after.pending_revocation is True
    assert after.decision.for_capability(Capability.CWD_ANCESTORS).revoked is True
    assert not after.decision.for_capability(Capability.CWD_ANCESTORS).qualified


def test_public_loader_rejects_incomplete_legacy_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from paper_radar.live_evidence import service
    from paper_radar.live_evidence.lifecycle import use_for_id
    from paper_radar.pi_execution.admission import load_admission_evidence
    from tests.test_pi_execution_admission import binding as legacy_binding

    ledger = EvidenceLedger(tmp_path / "missing")
    monkeypatch.setattr(service, "_ledger", lambda: ledger)
    request = service.AdmissionRequest(
        use_for_id("read-low"), ExecutionBinding(tuple(receipt().binding.items()))
    )
    projected = load_admission_evidence(request, now=NOW)
    assert projected is not None
    assert [reason.token for reason in projected.decision.reasons] == [
        "ledger_untrusted"
    ]
    assert load_admission_evidence(legacy_binding()) is None


def test_all_required_receipted_active_qualifications_share_one_projection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from paper_radar.live_evidence import service
    from paper_radar.live_evidence.lifecycle import use_for_id
    from paper_radar.live_evidence.registry import INITIAL_REGISTRY
    from paper_radar.live_evidence.types import Requirement
    from tests.live_evidence_lifecycle_support import activated

    required = tuple(
        rule.capability
        for rule in INITIAL_REGISTRY.requirements_for(use_for_id("boundary-low"))
        if rule.requirement is Requirement.REQUIRED
    )
    ledger, _, binding = activated(tmp_path, capabilities=required, provider=True)
    monkeypatch.setattr(service, "_ledger", lambda: ledger)
    monkeypatch.setattr(service, "_pending_path", lambda: tmp_path / "pending.jsonl")
    projection = service.load_admission_evidence(
        service.AdmissionRequest(
            use_for_id("boundary-low"), binding, frozenset(BindingComponent)
        ),
        now=NOW,
    )
    assert projection.decision.executable is True
    assert projection.pending_revocation is False
    assert all(projection.decision.for_capability(cap).qualified for cap in required)
    assert projection.decision.for_capability(
        Capability.EXACT_REQUEST_COUNT
    ).disclosure_unknown


def test_corrupt_pending_intent_can_only_tighten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.live_evidence import service
    from paper_radar.live_evidence.lifecycle import use_for_id

    pending = tmp_path / "pending.jsonl"
    pending.write_bytes(b"corrupt")
    monkeypatch.setattr(service, "_pending_path", lambda: pending)
    projection = service.load_admission_evidence(
        service.AdmissionRequest(
            use_for_id("read-low"), ExecutionBinding(tuple(receipt().binding.items()))
        ),
        now=NOW,
    )
    assert not projection.decision.executable
    assert projection.pending_revocation
    assert [reason.token for reason in projection.decision.reasons] == [
        "ledger_untrusted"
    ]
