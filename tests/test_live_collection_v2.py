from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from paper_radar.contracts import ContractName, ContractVersion, build_frozen_contract
from paper_radar.live_evidence.cli import live_evidence_app
from paper_radar.live_evidence.collection import (
    CollectionRound,
    Operation,
    ProtectedCollection,
)
from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerError, LedgerTrust
from paper_radar.live_evidence.lifecycle import EvidenceLifecycle
from paper_radar.live_evidence.receipt import canonical_bytes, content_sha256
from paper_radar.live_evidence.receipt_v2 import (
    ApprovedPlanV2,
    EvidenceReceiptV2,
)
from paper_radar.live_evidence.types import BindingComponent
from tests.live_evidence_ledger_support import NOW, owner_uid, plan, protected_root


def approved(identifier: str = "live-plan") -> ApprovedPlanV2:
    data = plan().model_dump()
    data.update(
        format_version="v2",
        domain_id="live-177",
        plan_id=identifier,
        kind="model_six_cell",
        cases=("auth-model", "rpc-second"),
        starts_at=NOW - timedelta(hours=1),
        ends_at=NOW + timedelta(days=1),
        max_auth_calls=20,
        max_network_requests=20,
        max_model_calls=40,
        max_rounds=20,
    )
    return ApprovedPlanV2.model_validate(data)


def test_v2_fixed_domain_and_combined_network_budget() -> None:
    assert approved().domain_id == "live-177"
    with pytest.raises(ValidationError, match="live-177"):
        ApprovedPlanV2.model_validate({**approved().model_dump(), "domain_id": "new"})
    with pytest.raises(ValidationError, match="network_budget_exceeded"):
        ApprovedPlanV2.model_validate({**approved().model_dump(), "max_auth_calls": 21})


BINDING = {part: "b" * 64 for part in BindingComponent}


def collection(tmp_path: Path) -> ProtectedCollection:
    root = protected_root(tmp_path)
    ledger = EvidenceLedger(
        root, trust=LedgerTrust(owner_uid=owner_uid(), anchor=tmp_path)
    )
    ledger.initialize()
    result = ProtectedCollection(ledger)
    result.initialize(now=NOW)
    result.approve_plan(approved(), now=NOW)
    return result


def test_reserved_unknown_usage_survives_reopen_and_plan_change(tmp_path: Path) -> None:
    current = collection(tmp_path)
    run = current.start_round("live-plan", binding=BINDING, now=NOW)
    current.reserve(run.round_id, "auth-model", "auth", now=NOW)
    other = ProtectedCollection(current.ledger)
    other.approve_plan(approved("another-plan"), now=NOW)
    status = other.status("another-plan", now=NOW)
    assert (status.network_used, status.network_remaining, status.model_used) == (
        1,
        39,
        0,
    )
    assert status.next_action == "recover_interrupted"
    other.recover_interrupted(now=NOW)
    status = current.status("live-plan", now=NOW)
    assert status.stopped and status.failed_rounds == 1
    with pytest.raises(LedgerError, match="plan_stopped"):
        other.start_round("another-plan", binding=BINDING, now=NOW)


def finished(
    current: ProtectedCollection,
    run: CollectionRound,
    *,
    failed: str | None = None,
    reason: str = "protocol_failed",
) -> EvidenceReceiptV2:
    cases = []
    for identifier in run.case_ids:
        cases.append(
            dict(
                case_id=identifier,
                outcome="failed" if identifier == failed else "passed",
                auth_calls=0,
                model_calls=0,
                network_requests=0,
            )
        )
        if identifier == failed:
            break
    return EvidenceReceiptV2.model_validate(
        dict(
            format_version="v2",
            domain_id="live-177",
            registry_version="live-admission-v1",
            plan_id=run.plan_id,
            plan_sha256=content_sha256(current.ledger.show_plan(run.plan_id)),
            collector_sha256="a" * 64,
            round_id=run.round_id,
            round_number=run.round_number,
            history_sha256=run.history_sha256,
            prior_receipts=run.prior_receipts,
            reservation_ids=(),
            started_at=run.started_at,
            completed_at=NOW,
            binding=BINDING,
            cases=cases,
            failure_history=[dict(case_id=failed, reason=reason)] if failed else [],
            claims=[
                dict(
                    capability="rpc_completion",
                    use_id="boundary-low",
                    case_id=cases[0]["case_id"],
                    status="unknown",
                    basis="not_observed",
                    scope="not_observed",
                    verified_at=None,
                    evidence_at=NOW,
                )
            ],
        )
    )


def test_ordinary_failure_resumes_from_unpassed_case_and_rejects_tampered_origin(
    tmp_path: Path,
) -> None:
    current = collection(tmp_path)
    run = current.start_round("live-plan", binding=BINDING, now=NOW)
    first = finished(current, run, failed="rpc-second")
    current.complete_round(first, now=NOW)
    again = current.start_round("live-plan", binding=BINDING, now=NOW)
    assert again.case_ids == ("rpc-second",)
    assert again.prior_receipts == (content_sha256(first),)
    second = finished(current, again)
    forged = EvidenceReceiptV2.model_validate(
        {**second.model_dump(), "prior_receipts": ()}
    )
    with pytest.raises(LedgerError, match="collection_history_mismatch"):
        current.complete_round(forged, now=NOW)
    current.complete_round(second, now=NOW)
    assert current.status("live-plan", now=NOW).next_action == "complete"
    assert current.status("live-plan", now=NOW).failed_rounds == 1
    assert current.status("live-plan", now=NOW).failure_chains == ()


def publish(current: ProtectedCollection, receipt: EvidenceReceiptV2) -> Path:
    source = current.ledger.root / "inbox" / (receipt.round_id + ".json")
    source.write_bytes(canonical_bytes(receipt))
    source.chmod(0o644)
    return source


def test_owner_receive_v2_after_empty_admission_cancel_and_resume(
    tmp_path: Path,
) -> None:
    current = collection(tmp_path)
    empty = current.start_round("live-plan", binding=BINDING, now=NOW)
    current.cancel_round(empty.round_id, now=NOW)
    run = current.start_round("live-plan", binding=BINDING, now=NOW)
    first = finished(current, run, failed="rpc-second")
    current.complete_round(first, now=NOW)
    source = publish(current, first)
    assert not current.ledger.receive(source, now=NOW).duplicate
    run = current.start_round("live-plan", binding=BINDING, now=NOW)
    second = finished(current, run)
    current.complete_round(second, now=NOW)
    source = publish(current, second)
    assert current.ledger.receive(source, now=NOW).receipt_id == second.receipt_id
    assert current.ledger.show(first.receipt_id).receipt == first
    assert current.ledger.show(second.receipt_id).receipt == second


def test_concurrent_reservations_enforce_combined_40_and_model_40(
    tmp_path: Path,
) -> None:
    current = collection(tmp_path)
    plan = ApprovedPlanV2.model_validate(
        {
            **approved("full-budget").model_dump(),
            "max_auth_calls": 40,
            "max_network_requests": 0,
        }
    )
    current.approve_plan(plan, now=NOW)
    run = current.start_round("full-budget", binding=BINDING, now=NOW)

    def dispatch(operation: Operation) -> str:
        try:
            return current.reserve(
                run.round_id, "auth-model", operation, now=NOW
            ).operation
        except LedgerError as error:
            return error.category

    with ThreadPoolExecutor(max_workers=6) as pool:
        outcomes = list(pool.map(dispatch, ["auth"] * 44 + ["model"] * 44))
    assert outcomes.count("auth") == outcomes.count("model") == 40
    assert outcomes.count("plan_budget_exceeded") == 8
    status = ProtectedCollection(current.ledger).status("live-plan", now=NOW)
    assert (
        status.network_used,
        status.model_used,
        status.network_remaining,
        status.model_remaining,
    ) == (40, 40, 0, 0)


@pytest.mark.parametrize(
    "reason",
    [
        "isolation_failed",
        "identity_mismatch",
        "interrupted",
        "sensitive_output",
        "permission_failed",
        "ledger_untrusted",
        "source_untrusted",
    ],
)
def test_safety_failure_stops_first_round_across_plans(
    tmp_path: Path, reason: str
) -> None:
    current = collection(tmp_path)
    run = current.start_round("live-plan", binding=BINDING, now=NOW)
    current.complete_round(
        finished(current, run, failed="auth-model", reason=reason), now=NOW
    )
    current.approve_plan(approved("renamed-plan"), now=NOW)
    status = current.status("renamed-plan", now=NOW)
    assert status.stopped and status.stop_reason == reason
    with pytest.raises(LedgerError, match="plan_stopped"):
        current.start_round("renamed-plan", binding=BINDING, now=NOW)


def test_third_same_failure_class_stops_even_with_new_plans(tmp_path: Path) -> None:
    current = collection(tmp_path)
    for index in range(3):
        identifier = f"round-plan-{index}"
        current.approve_plan(approved(identifier), now=NOW)
        run = current.start_round(identifier, binding=BINDING, now=NOW)
        current.complete_round(finished(current, run, failed="auth-model"), now=NOW)
        status = current.status("live-plan", now=NOW)
        assert status.stopped == (index == 2)
        assert status.failure_chains == (("auth-model", "protocol_failed", index + 1),)
    assert status.stop_reason == "failure_class_stopped"


def test_sixth_failed_round_opens_global_circuit_despite_reason_changes(
    tmp_path: Path,
) -> None:
    current = collection(tmp_path)
    for index in range(6):
        run = current.start_round("live-plan", binding=BINDING, now=NOW)
        reason = "protocol_failed" if index % 2 else "resource_unavailable"
        current.complete_round(
            finished(current, run, failed="auth-model", reason=reason), now=NOW
        )
        status = current.status("live-plan", now=NOW)
        assert status.stopped == (index == 5)
        assert status.failure_chains == (("auth-model", reason, 1),)
    assert status.failed_rounds == 6 and status.stop_reason == "global_circuit_open"


def test_other_template_success_does_not_clear_failure_chain(tmp_path: Path) -> None:
    current = collection(tmp_path)
    run = current.start_round("live-plan", binding=BINDING, now=NOW)
    current.complete_round(finished(current, run, failed="auth-model"), now=NOW)
    other = ApprovedPlanV2.model_validate(
        {**approved("other-template").model_dump(), "cases": ("rpc-second",)}
    )
    current.approve_plan(other, now=NOW)
    run = current.start_round("other-template", binding=BINDING, now=NOW)
    current.complete_round(finished(current, run), now=NOW)
    assert current.status("live-plan", now=NOW).failure_chains == (
        ("auth-model", "protocol_failed", 1),
    )


def test_schema_cutover_reopen_and_missing_fact_history_refuse(tmp_path: Path) -> None:
    current = collection(tmp_path)
    current.initialize(now=NOW)
    with current.ledger.connection() as connection:
        assert connection.execute("PRAGMA user_version").fetchone() == (2,)
        assert {
            row[1] for row in connection.execute("PRAGMA table_info(collection_facts)")
        } == {"sequence", "previous_digest", "digest", "payload"}
    run = current.start_round("live-plan", binding=BINDING, now=NOW)
    current.reserve(run.round_id, "auth-model", "auth", now=NOW)
    with current.ledger.connection(writable=True) as connection:
        connection.execute(
            "DELETE FROM collection_facts WHERE sequence="
            "(SELECT MAX(sequence) FROM collection_facts)"
        )
    with pytest.raises(LedgerError, match="ledger_untrusted"):
        ProtectedCollection(current.ledger).status("live-plan", now=NOW)


def test_restore_old_snapshot_cannot_refund_reservations_or_stop(
    tmp_path: Path,
) -> None:
    current = collection(tmp_path)
    backup = current.ledger.root / "historical.sqlite3"
    EvidenceLifecycle(current.ledger).backup(backup)
    run = current.start_round("live-plan", binding=BINDING, now=NOW)
    current.reserve(run.round_id, "auth-model", "auth", now=NOW)
    current.recover_interrupted(now=NOW)
    EvidenceLifecycle(current.ledger).restore(backup, now=NOW)
    status = current.status("live-plan", now=NOW)
    assert status.network_used == 1 and status.stopped
    assert status.stop_reason == "interrupted"


def test_v2_frozen_contract_and_v1_reader_rejection() -> None:
    contract = build_frozen_contract(ContractName.LIVE_EVIDENCE, ContractVersion("v2"))
    snapshot = Path(__file__).parents[1] / "contracts/live-evidence/live-evidence/v2"
    assert (snapshot / "schema.json").read_bytes() == contract.schema_bytes
    assert (snapshot / "manifest.json").read_bytes() == contract.manifest_bytes
    assert (
        json.loads(contract.schema_bytes)["properties"]["domain_id"]["const"]
        == "live-177"
    )
    from paper_radar.live_evidence.receipt import ApprovedPlan

    with pytest.raises(ValidationError, match="v1"):
        ApprovedPlan.model_validate(approved().model_dump())


def test_show_plan_reads_authoritative_quota_without_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    current = collection(tmp_path)
    run = current.start_round("live-plan", binding=BINDING, now=NOW)
    current.reserve(run.round_id, "auth-model", "auth", now=NOW)
    import paper_radar.live_evidence.ledger as module

    monkeypatch.setattr(module, "EvidenceLedger", lambda: current.ledger)
    before = current.ledger.database.read_bytes()
    result = CliRunner().invoke(live_evidence_app, ["show", "--plan-id", "live-plan"])
    assert result.exit_code == 0, result.output
    assert '"network_used": 1' in result.output
    assert '"network_remaining": 39' in result.output
    assert '"next_action": "recover_interrupted"' in result.output
    assert current.ledger.database.read_bytes() == before


def test_collection_schema_constraints_are_preserved_after_upgrade(
    tmp_path: Path,
) -> None:
    current = collection(tmp_path)
    with current.ledger.connection(writable=True) as connection:
        assert [
            row[1:6]
            for row in connection.execute("PRAGMA table_info(collection_facts)")
        ] == [
            ("sequence", "INTEGER", 0, None, 1),
            ("previous_digest", "TEXT", 1, None, 0),
            ("digest", "TEXT", 1, None, 0),
            ("payload", "BLOB", 1, None, 0),
        ]
        indexes = connection.execute("PRAGMA index_list(collection_facts)").fetchall()
        assert len(indexes) == 1 and indexes[0][2:4] == (1, "u")
        assert [
            row[2] for row in connection.execute(f"PRAGMA index_info({indexes[0][1]})")
        ] == ["digest"]
    assert current.ledger.show_plan("live-plan") == approved()


def test_unknown_wire_versions_are_rejected_without_fallback() -> None:
    from paper_radar.live_evidence.receipt_v2 import read_plan, read_receipt

    with pytest.raises(ValidationError, match="union_tag_invalid"):
        read_plan(b'{"format_version":"v99"}')
    with pytest.raises(ValidationError, match="union_tag_invalid"):
        read_receipt(b'{"format_version":"v99"}')


def test_exhausted_domain_refuses_new_round_before_it_can_become_interrupted(
    tmp_path: Path,
) -> None:
    current = collection(tmp_path)
    first_plan = ApprovedPlanV2.model_validate(
        {
            **approved("forty-auth").model_dump(),
            "max_auth_calls": 40,
            "max_network_requests": 0,
        }
    )
    current.approve_plan(first_plan, now=NOW)
    run = current.start_round("forty-auth", binding=BINDING, now=NOW)
    permits = tuple(
        current.reserve(run.round_id, "auth-model", "auth", now=NOW).reservation_id
        for _ in range(40)
    )
    data = finished(current, run, failed="auth-model").model_dump()
    data["reservation_ids"] = permits
    data["cases"][0]["auth_calls"] = 40
    current.complete_round(EvidenceReceiptV2.model_validate(data), now=NOW)
    with pytest.raises(LedgerError, match="plan_budget_exceeded"):
        current.start_round("live-plan", binding=BINDING, now=NOW)
    assert current.status("live-plan", now=NOW).failed_rounds == 1
    assert not current.status("live-plan", now=NOW).stopped
