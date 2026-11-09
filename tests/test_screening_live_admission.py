"""#173 正式 Screening 准入;独立未绑定产品入口覆盖。"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from paper_radar.live_evidence.types import BindingComponent
from paper_radar.pi_execution.admission import AdmissionEvidence
from paper_radar.pi_execution.errors import ExecutionError
from paper_radar.pi_execution.launcher import PreparedLaunch, prepare_launch
from paper_radar.screening_tasks import FailureReceipt, SuccessReceipt
from tests.pi_execution_service_support import service_inputs


def test_product_never_calls_legacy_synthetic_evidence_alias(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, receipt, credentials = service_inputs(tmp_path, monkeypatch)
    calls: list[object] = []

    def synthetic(binding: object) -> AdmissionEvidence:
        calls.append(binding)
        raise AssertionError("产品触及工程授予接缝")

    monkeypatch.setattr("paper_radar.pi_execution.service._evidence_for", synthetic)
    with pytest.raises(ExecutionError, match="evidence_missing"):
        service.run_attempt(receipt.receipt_id)
    assert calls == []
    assert service.tasks.status(receipt.receipt_id).used_attempts == 0
    assert not (credentials / "auth-observed.json").exists()


def test_expiry_after_prepare_is_refused_without_attempt_or_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from contextlib import contextmanager
    from datetime import timedelta

    from paper_radar.pi_execution import service as execution
    from tests.live_evidence_ledger_support import NOW
    from tests.screening_live_admission_support import (
        product_inputs,
        protected_admission,
    )

    service, receipt, credentials = product_inputs(tmp_path / "product", monkeypatch)
    protected_admission(tmp_path / "evidence", monkeypatch)
    current = NOW
    service._now = lambda: current
    original = prepare_launch

    @contextmanager
    def prepare(*args: Any, **kwargs: Any) -> Iterator[PreparedLaunch]:
        nonlocal current
        with original(*args, **kwargs) as prepared:
            current = NOW + timedelta(days=30)
            yield prepared

    monkeypatch.setattr(execution, "prepare_launch", prepare)
    with pytest.raises(ExecutionError, match="evidence_missing"):
        service.run_attempt(receipt.receipt_id)
    status = service.tasks.status(receipt.receipt_id)
    assert (status.used_attempts, status.last_failure) == (0, None)
    assert (credentials / "auth-observed.json").exists()


@pytest.mark.parametrize("component", list(BindingComponent))
def test_every_component_drift_after_refresh_is_durable_even_when_helper_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, component: BindingComponent
) -> None:
    from contextlib import contextmanager

    from paper_radar.live_evidence import service as evidence_service
    from paper_radar.live_evidence.evidence import ExecutionBinding
    from paper_radar.live_evidence.lifecycle import use_for_id
    from paper_radar.live_evidence.service import AdmissionRequest
    from paper_radar.live_evidence.types import BindingComponent
    from paper_radar.pi_execution import service as execution
    from tests.live_evidence_ledger_support import NOW
    from tests.screening_live_admission_support import (
        product_inputs,
        protected_admission,
    )

    product, receipt, credentials = product_inputs(tmp_path / "product", monkeypatch)
    _, _, components = protected_admission(tmp_path / "evidence", monkeypatch)
    product._now = lambda: NOW
    monkeypatch.setattr(evidence_service, "_run_helper", lambda args: False)
    original = prepare_launch

    @contextmanager
    def prepare(*args: Any, **kwargs: Any) -> Iterator[PreparedLaunch]:
        with original(*args, **kwargs) as prepared:
            components[component] = "c" * 64
            yield prepared

    monkeypatch.setattr(execution, "prepare_launch", prepare)
    with pytest.raises(ExecutionError, match="evidence_missing"):
        product.run_attempt(receipt.receipt_id)
    status = product.tasks.status(receipt.receipt_id)
    assert (status.used_attempts, status.last_failure) == (0, None)
    assert (credentials / "auth-observed.json").exists()
    request = AdmissionRequest(
        use_for_id("boundary-low"),
        ExecutionBinding(tuple(components.items())),
        frozenset(BindingComponent),
    )
    after = evidence_service.load_admission_evidence(request, now=NOW)
    assert after.pending_revocation
    assert f"binding_drift:{component.value}" in {
        reason.token for reason in after.decision.reasons
    }
    components[component] = "b" * 64
    restarted = execution.PiExecution(
        product.database,
        product.data_root,
        roots=product.roots,
        credentials_dir=credentials,
        auth_mode=product.auth_mode,
        clock=lambda: NOW,
    )
    with pytest.raises(ExecutionError, match="evidence_missing"):
        restarted.run_attempt(receipt.receipt_id)
    assert restarted.tasks.status(receipt.receipt_id).used_attempts == 0


@pytest.mark.parametrize(
    "change",
    [
        "expired",
        "clock_rollback",
        "source_lost",
        "ledger_lost",
        "watermark_rollback",
        "observation_lost",
        "observation_expired",
        "observation_changed",
        "observation_coverage_lost",
    ],
)
def test_transaction_checkpoint_rechecks_time_sources_and_watermark_without_tree_scan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    import sqlite3
    from datetime import timedelta

    from paper_radar.pi_execution import current_binding
    from tests.live_evidence_ledger_support import NOW
    from tests.screening_live_admission_support import (
        product_inputs,
        protected_admission,
    )

    product, receipt, _ = product_inputs(tmp_path / "product", monkeypatch)
    ledger, _, _ = protected_admission(tmp_path / "evidence", monkeypatch)
    now = NOW
    product._now = lambda: now
    observes: list[int] = []
    observe = current_binding.local_binding_components

    def counted(*args: Any, **kwargs: Any) -> dict[BindingComponent, str]:
        observes.append(1)
        return observe(*args, **kwargs)

    monkeypatch.setattr(current_binding, "local_binding_components", counted)
    run = product.tasks.run_once

    def before_transaction(
        *args: Any, **kwargs: Any
    ) -> SuccessReceipt | FailureReceipt:
        nonlocal now
        if change == "expired":
            now += timedelta(days=30)
        elif change == "clock_rollback":
            now -= timedelta(seconds=1)
        elif change == "source_lost":
            (ledger.root / "inbox/site.json").unlink()
        elif change == "ledger_lost":
            ledger.database.unlink()
        elif change == "observation_lost":
            (ledger.root / "inbox/current-observation.json").unlink()
        elif change == "observation_expired":
            now += timedelta(seconds=61)
        elif change in {"observation_changed", "observation_coverage_lost"}:
            from paper_radar.live_evidence.observation import CurrentObservation
            from paper_radar.live_evidence.receipt import canonical_bytes

            path = ledger.root / "inbox/current-observation.json"
            observation = CurrentObservation.model_validate_json(path.read_bytes())
            data = observation.model_dump()
            if change == "observation_changed":
                data["binding"][BindingComponent.IPV4_EGRESS] = "d" * 64
            else:
                data["checked_components"] = []
            path.write_bytes(canonical_bytes(CurrentObservation.model_validate(data)))
        else:
            with sqlite3.connect(ledger.database) as connection:
                connection.execute(
                    "UPDATE events SET recorded_at=?",
                    ((NOW - timedelta(seconds=1)).isoformat(),),
                )
        result = run(*args, **kwargs)
        assert isinstance(result, (SuccessReceipt, FailureReceipt))
        return result

    monkeypatch.setattr(product.tasks, "run_once", before_transaction)
    with pytest.raises(ExecutionError, match="evidence_missing"):
        product.run_attempt(receipt.receipt_id)
    status = product.tasks.status(receipt.receipt_id)
    assert (status.used_attempts, status.last_failure) == (0, None)
    assert len(observes) == 2


def test_dispatched_attempt_crossing_expiry_keeps_existing_settlement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from datetime import timedelta

    from paper_radar.screening_tasks import SuccessReceipt
    from tests.live_evidence_ledger_support import NOW
    from tests.screening_live_admission_support import (
        product_inputs,
        protected_admission,
    )

    product, receipt, _ = product_inputs(tmp_path / "product", monkeypatch)
    protected_admission(tmp_path / "evidence", monkeypatch)
    now = NOW
    product._now = lambda: now

    def cross_expiry() -> bool:
        nonlocal now
        now += timedelta(days=30)
        return False

    result = product.run_attempt(receipt.receipt_id, cancelled=cross_expiry)
    assert isinstance(result, SuccessReceipt)
    assert product.tasks.status(receipt.receipt_id).used_attempts == 1


def test_tick_failure_denies_before_claim_and_keeps_durable_intent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.live_evidence_ledger_support import NOW
    from tests.screening_live_admission_support import (
        product_inputs,
        protected_admission,
    )

    product, receipt, _ = product_inputs(tmp_path / "product", monkeypatch)
    protected_admission(tmp_path / "evidence", monkeypatch)
    product._now = lambda: NOW
    monkeypatch.setattr(
        "paper_radar.live_evidence.service._run_helper", lambda args: False
    )
    with pytest.raises(ExecutionError, match="evidence_missing"):
        product.run_attempt(receipt.receipt_id)
    assert (tmp_path / "evidence/pending.jsonl").is_file()
    status = product.tasks.status(receipt.receipt_id)
    assert (status.used_attempts, status.last_failure) == (0, None)


def test_runtime_failure_tightens_and_retry_does_not_refill_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.screening_tasks import FailureReceipt
    from tests.live_evidence_ledger_support import NOW
    from tests.screening_live_admission_support import protected_admission

    product, receipt, _ = service_inputs(
        tmp_path / "product", monkeypatch, mode="protocol"
    )
    protected_admission(tmp_path / "evidence", monkeypatch)
    product._now = lambda: NOW
    monkeypatch.setattr(
        "paper_radar.live_evidence.service._run_helper", lambda args: args == ("tick",)
    )
    result = product.run_attempt(receipt.receipt_id)
    assert isinstance(result, FailureReceipt)
    assert result.kind.value == "protocol_error"
    assert product.tasks.status(receipt.receipt_id).used_attempts == 1
    assert (tmp_path / "evidence/pending.jsonl").is_file()
    with pytest.raises(ExecutionError, match="evidence_missing"):
        product.run_attempt(receipt.receipt_id)
    assert product.tasks.status(receipt.receipt_id).used_attempts == 1


def test_product_service_has_no_legacy_alias_read() -> None:
    import ast
    import inspect

    from paper_radar.pi_execution import service

    tree = ast.parse(inspect.getsource(service))
    assert not any(
        isinstance(node, ast.Name)
        and node.id == "_evidence_for"
        and isinstance(node.ctx, ast.Load)
        for node in ast.walk(tree)
    )


@pytest.mark.parametrize(
    "state", ["missing_required", "not_activated", "revoked", "receipt_source_missing"]
)
def test_required_qualification_gaps_never_refresh_or_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, state: str
) -> None:
    from paper_radar.live_evidence.lifecycle import EvidenceLifecycle
    from tests.live_evidence_ledger_support import NOW
    from tests.screening_live_admission_support import (
        REQUIRED,
        product_inputs,
        protected_admission,
    )

    product, receipt, credentials = product_inputs(tmp_path / "product", monkeypatch)
    ledger, evidence_receipt, _ = protected_admission(
        tmp_path / "evidence",
        monkeypatch,
        capabilities=("cwd_ancestors",) if state == "missing_required" else REQUIRED,
        activate=state != "not_activated",
    )
    product._now = lambda: NOW
    if state == "revoked":
        EvidenceLifecycle(ledger).tighten(
            evidence_receipt.receipt_id, "boundary-low", now=NOW
        )
    elif state == "receipt_source_missing":
        (ledger.root / "inbox/site.json").unlink()
    with pytest.raises(ExecutionError, match="evidence_missing"):
        product.run_attempt(receipt.receipt_id)
    status = product.tasks.status(receipt.receipt_id)
    assert (status.used_attempts, status.last_failure) == (0, None)
    assert not (credentials / "auth-observed.json").exists()


def test_disclosure_only_pending_revocation_keeps_shared_required_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.live_evidence.service import request_revocation
    from paper_radar.live_evidence.types import Capability
    from tests.live_evidence_ledger_support import NOW
    from tests.screening_live_admission_support import (
        REQUIRED,
        product_inputs,
        protected_admission,
    )

    product, receipt, _ = product_inputs(tmp_path / "product", monkeypatch)
    _, evidence_receipt, _ = protected_admission(
        tmp_path / "evidence", monkeypatch, capabilities=(*REQUIRED, "account_limits")
    )
    product._now = lambda: NOW
    monkeypatch.setattr(
        "paper_radar.live_evidence.service._run_helper", lambda args: args == ("tick",)
    )
    assert (
        request_revocation(
            evidence_receipt.receipt_id,
            "boundary-low",
            now=NOW,
            components=frozenset(),
            failed_capabilities=frozenset({Capability.ACCOUNT_LIMITS}),
        )
        is False
    )
    result = product.run_attempt(receipt.receipt_id)
    assert isinstance(result, SuccessReceipt)
    assert product.tasks.status(receipt.receipt_id).used_attempts == 1
