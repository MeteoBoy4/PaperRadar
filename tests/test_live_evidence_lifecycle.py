from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest

from paper_radar.live_evidence.evaluator import evaluate_admission
from paper_radar.live_evidence.evidence import ExecutionBinding
from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerError, LedgerTrust
from paper_radar.live_evidence.lifecycle import EvidenceLifecycle, use_for_id
from paper_radar.live_evidence.receipt import canonical_bytes
from paper_radar.live_evidence.registry import INITIAL_REGISTRY
from paper_radar.live_evidence.types import BindingComponent, Capability
from tests.live_evidence_ledger_support import (
    NOW,
    owner_uid,
    plan,
    protected_root,
    receipt,
)
from tests.live_evidence_lifecycle_support import activated, installed


def test_owner_activation_is_scoped_idempotent_and_preserves_original_claim(
    tmp_path: Path,
) -> None:
    root = protected_root(tmp_path)
    ledger = EvidenceLedger(root, trust=LedgerTrust(owner_uid(), owner_uid() + 1, root))
    ledger.initialize()
    ledger.approve_plan(plan(), now=NOW)
    source = root / "inbox" / "site.json"
    original = receipt()
    source.write_bytes(canonical_bytes(original))
    source.chmod(0o644)
    ledger.receive(source, now=NOW)
    lifecycle = EvidenceLifecycle(ledger)
    binding = ExecutionBinding(tuple(original.binding.items()))
    review = lifecycle.review(
        original.receipt_id,
        "boundary-low",
        binding=binding,
        checked_components=frozenset(BindingComponent),
        now=NOW,
    )
    assert review.eligible == (Capability.CWD_ANCESTORS,)
    result = lifecycle.activate(review, confirmation=original.receipt_id, now=NOW)
    assert result.duplicate is False
    assert (
        lifecycle.activate(review, confirmation=original.receipt_id, now=NOW).duplicate
        is True
    )
    state = lifecycle.snapshot(now=NOW)
    assert state.evidence[0].evidence_active is True
    assert state.evidence[0].claim.verified_at == original.claims[0].verified_at
    assert ledger.show(original.receipt_id).receipt == original


def test_restore_and_irreversible_revoke_never_resurrect_old_grants(
    tmp_path: Path,
) -> None:
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
    backup = root / "inbox" / "backup.sqlite3"
    lifecycle.backup(backup)
    lifecycle.tighten(receipt().receipt_id, "boundary-low", now=NOW)
    lifecycle.restore(backup, now=NOW)
    restarted = EvidenceLifecycle(EvidenceLedger(root, trust=ledger.trust))
    state = restarted.snapshot(now=NOW).evidence[0]
    assert state.evidence_active is False
    assert state.revoked is True
    import pytest

    from paper_radar.live_evidence.ledger import LedgerError

    with pytest.raises(LedgerError, match="activation_empty"):
        restarted.activate(review, confirmation=receipt().receipt_id, now=NOW)


@pytest.mark.parametrize("component", tuple(BindingComponent))
def test_each_component_drift_revokes_only_dependent_qualifications(
    tmp_path: Path,
    component: BindingComponent,
) -> None:
    ledger, original, binding = activated(
        tmp_path,
        capabilities=(
            Capability.CWD_ANCESTORS,
            Capability.ZERO_CORE,
            Capability.HOST_RUNTIME,
        ),
    )
    lifecycle = EvidenceLifecycle(ledger)
    before = lifecycle.snapshot(now=NOW)
    affected = lifecycle.tighten(
        original.receipt_id, "boundary-low", now=NOW, components=frozenset({component})
    )
    after = lifecycle.snapshot(now=NOW)
    rules = {
        rule.capability: rule
        for rule in INITIAL_REGISTRY.requirements_for(use_for_id("boundary-low"))
    }
    for old, current in zip(before.evidence, after.evidence, strict=True):
        assert current.claim == old.claim
        assert current.revoked == (component in rules[current.capability].dependencies)
        assert (current.capability in affected) == current.revoked
    changed = replace(
        binding,
        components=tuple(
            (name, "changed" if name is component else value)
            for name, value in binding.components
        ),
    )
    decision = evaluate_admission(
        INITIAL_REGISTRY,
        use_for_id("boundary-low"),
        after.evidence,
        binding=changed,
        now=NOW,
        checked_components=frozenset(BindingComponent),
    )
    for cap in affected:
        assert f"binding_drift:{component.value}" in {
            reason.token for reason in decision.for_capability(cap).reasons
        }


def test_day_29_activation_does_not_renew_and_exact_deadline_is_expired(
    tmp_path: Path,
) -> None:
    ledger, original, binding = activated(
        tmp_path,
        capabilities=(Capability.MODEL_IDENTITY,),
        verified_at=NOW - timedelta(days=29),
        provider=True,
    )
    lifecycle = EvidenceLifecycle(ledger)
    for now, expired in ((NOW, False), (NOW + timedelta(days=1), True)):
        snapshot = lifecycle.snapshot(now=now)
        decision = evaluate_admission(
            INITIAL_REGISTRY,
            use_for_id("boundary-low"),
            snapshot.evidence,
            binding=binding,
            now=now,
            checked_components=frozenset(BindingComponent),
        )
        item = decision.for_capability(Capability.MODEL_IDENTITY)
        assert item.expires_at == NOW + timedelta(days=1)
        assert item.expired is expired
        assert (
            item.claim is not None
            and item.claim.verified_at == original.claims[0].verified_at
        )


@pytest.mark.parametrize("operation", ["read", "activate", "revoke", "tick", "receive"])
def test_clock_watermark_protects_all_read_and_write_paths(
    tmp_path: Path, operation: str
) -> None:
    ledger, original, binding = activated(tmp_path)
    lifecycle = EvidenceLifecycle(ledger)
    review = lifecycle.review(
        original.receipt_id,
        "boundary-low",
        binding=binding,
        checked_components=frozenset(BindingComponent),
        now=NOW,
    )
    lifecycle.tick(now=NOW + timedelta(seconds=1))
    before = ledger.database.read_bytes()
    with pytest.raises(LedgerError, match="clock_rollback"):
        if operation == "read":
            lifecycle.snapshot(now=NOW)
        elif operation == "activate":
            lifecycle.activate(review, confirmation=original.receipt_id, now=NOW)
        elif operation == "revoke":
            lifecycle.tighten(original.receipt_id, "boundary-low", now=NOW)
        elif operation == "tick":
            lifecycle.tick(now=NOW)
        else:
            ledger.receive(ledger.root / "inbox" / "site.json", now=NOW)
    assert ledger.database.read_bytes() == before


@pytest.mark.parametrize(
    "confirmation,use_id,reason",
    [
        ("bad", "boundary-low", "activation_confirmation_mismatch"),
        ("correct", "read-low", "activation_empty"),
    ],
)
def test_activation_cannot_grant_another_use_or_bypass_confirmation(
    tmp_path: Path,
    confirmation: str,
    use_id: str,
    reason: str,
) -> None:
    ledger, original, binding = installed(tmp_path)
    from paper_radar.live_evidence.lifecycle import use_id_for

    lifecycle = EvidenceLifecycle(ledger)
    review = lifecycle.review(
        original.receipt_id,
        use_id_for(use_for_id(use_id)),
        binding=binding,
        checked_components=frozenset(BindingComponent),
        now=NOW,
    )
    with pytest.raises(LedgerError, match=reason):
        lifecycle.activate(
            review,
            confirmation=original.receipt_id
            if confirmation == "correct"
            else confirmation,
            now=NOW,
        )
    assert not any(
        item.evidence_active for item in lifecycle.snapshot(now=NOW).evidence
    )


def test_restored_history_requires_manual_reactivation_and_preserves_watermark(
    tmp_path: Path,
) -> None:
    ledger, original, binding = activated(tmp_path)
    lifecycle = EvidenceLifecycle(ledger)
    backup = ledger.root / "snapshot.sqlite3"
    lifecycle.backup(backup)
    lifecycle.tick(now=NOW + timedelta(seconds=1))
    lifecycle.restore(backup, now=NOW + timedelta(seconds=1))
    assert (
        lifecycle.snapshot(now=NOW + timedelta(seconds=1)).evidence[0].evidence_active
        is False
    )
    review = lifecycle.review(
        original.receipt_id,
        "boundary-low",
        binding=binding,
        checked_components=frozenset(BindingComponent),
        now=NOW + timedelta(seconds=1),
    )
    assert (
        lifecycle.activate(
            review, confirmation=original.receipt_id, now=NOW + timedelta(seconds=1)
        ).duplicate
        is False
    )
    with pytest.raises(LedgerError, match="clock_rollback"):
        lifecycle.snapshot(now=NOW)


def test_corrupt_restore_does_not_change_current_history(tmp_path: Path) -> None:
    ledger, _, _ = activated(tmp_path)
    broken = ledger.root / "broken.sqlite3"
    broken.write_bytes(b"corrupt")
    broken.chmod(0o644)
    before = ledger.database.read_bytes()
    with pytest.raises(LedgerError, match="ledger_untrusted"):
        EvidenceLifecycle(ledger).restore(broken, now=NOW)
    assert ledger.database.read_bytes() == before


def test_failed_revalidation_and_restore_cannot_select_old_verified_claim(
    tmp_path: Path,
) -> None:
    from paper_radar.live_evidence.receipt import (
        ApprovedPlan,
        EvidenceReceipt,
        content_sha256,
    )
    from tests.live_evidence_ledger_support import plan as original_plan

    ledger, old, _ = activated(tmp_path)
    lifecycle = EvidenceLifecycle(ledger)
    backup = ledger.root / "snapshot.sqlite3"
    lifecycle.backup(backup)
    approved = ApprovedPlan.model_validate(
        original_plan().model_dump() | {"plan_id": "beta-2"}
    )
    ledger.approve_plan(approved, now=NOW)
    data = old.model_dump(mode="json")
    data.update(plan_id="beta-2", plan_sha256=content_sha256(approved))
    data["cases"][0]["outcome"] = "failed"
    data["failure_history"] = [{"case_id": "cwd", "reason": "isolation_failed"}]
    data["claims"][0].update(status="unknown", verified_at=None)
    failed = EvidenceReceipt.model_validate(data)
    source = ledger.root / "inbox" / "failed.json"
    source.write_bytes(canonical_bytes(failed))
    source.chmod(0o644)
    ledger.receive(source, now=NOW)
    lifecycle.restore(backup, now=NOW)
    state = lifecycle.snapshot(now=NOW).evidence[0]
    assert state.claim.status.value == "unknown"
    assert state.claim.verified_at is None
    assert state.evidence_active is False


@pytest.mark.parametrize(
    "recorded", ["2026-11-09T12:00:00", "2020-01-01T00:00:00+00:00"]
)
def test_corrupt_received_time_cannot_reorder_or_grant_history(
    tmp_path: Path, recorded: str
) -> None:
    ledger, _, _ = activated(tmp_path)
    with ledger.connection(writable=True) as connection:
        connection.execute("UPDATE receipts SET received_at=?", (recorded,))
    with pytest.raises(LedgerError, match="ledger_untrusted"):
        EvidenceLifecycle(ledger).snapshot(now=NOW)
