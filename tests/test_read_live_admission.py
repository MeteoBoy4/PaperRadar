"""#174 Read 正式分项准入;独立未绑定消费者覆盖。"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from paper_radar.live_evidence.types import BindingComponent
from paper_radar.pi_execution.errors import ExecutionError
from paper_radar.pi_execution.launcher import PreparedLaunch, prepare_launch
from paper_radar.read_tasks import ReadAnalysis, ReadTask
from tests.read_execution_support import setup


def test_product_never_calls_legacy_synthetic_evidence_alias(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    product, task, credentials = setup(tmp_path, monkeypatch)
    calls: list[object] = []

    def synthetic(binding: object) -> None:
        calls.append(binding)
        raise AssertionError("产品触及工程授予接缝")

    monkeypatch.setattr(
        "paper_radar.read_execution.service._evidence_for", synthetic, raising=False
    )
    with pytest.raises(ExecutionError, match="evidence_missing"):
        product.run_attempt(task.task_id)
    assert calls == []
    assert product.tasks.task(task.task_id).attempts == ()
    assert not (credentials / "auth-observed.json").exists()


def test_expiry_after_prepare_is_refused_without_attempt_or_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from contextlib import contextmanager
    from datetime import timedelta

    from tests.live_evidence_ledger_support import NOW
    from tests.screening_live_admission_support import protected_admission

    product, task, credentials = setup(tmp_path / "product", monkeypatch)
    protected_admission(tmp_path / "evidence", monkeypatch, uses=("read-low",))
    current = NOW
    product._now = lambda: current

    @contextmanager
    def prepare(*args: Any, **kwargs: Any) -> Iterator[PreparedLaunch]:
        nonlocal current
        with prepare_launch(*args, **kwargs) as prepared:
            current = NOW + timedelta(days=30)
            yield prepared

    monkeypatch.setattr("paper_radar.read_execution.service.prepare_launch", prepare)
    with pytest.raises(ExecutionError, match="evidence_missing"):
        product.run_attempt(task.task_id)
    assert product.tasks.task(task.task_id).attempts == ()
    assert product.tasks.analyses(task.paper_id) == ()
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
    from paper_radar.read_execution import service as execution
    from tests.live_evidence_ledger_support import NOW
    from tests.screening_live_admission_support import protected_admission

    product, task, credentials = setup(tmp_path / "product", monkeypatch)
    _, _, components = protected_admission(
        tmp_path / "evidence", monkeypatch, uses=("read-low",)
    )
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
        product.run_attempt(task.task_id)
    assert product.tasks.task(task.task_id).attempts == ()
    assert product.tasks.analyses(task.paper_id) == ()
    assert (credentials / "auth-observed.json").exists()
    request = AdmissionRequest(
        use_for_id("read-low"),
        ExecutionBinding(tuple(components.items())),
        frozenset(BindingComponent),
    )
    after = evidence_service.load_admission_evidence(request, now=NOW)
    assert after.pending_revocation
    assert f"binding_drift:{component.value}" in {
        reason.token for reason in after.decision.reasons
    }
    components[component] = "b" * 64
    restarted = execution.ReadExecution(
        product.database,
        product.data_root,
        roots=product.roots,
        credentials_dir=credentials,
        auth_mode=product.auth_mode,
        clock=lambda: NOW,
    )
    with pytest.raises(ExecutionError, match="evidence_missing"):
        restarted.run_attempt(task.task_id)
    assert restarted.tasks.task(task.task_id).remaining_attempts == 2


@pytest.mark.parametrize(
    "change",
    [
        "expired",
        "clock_rollback",
        "source_lost",
        "ledger_lost",
        "watermark_rollback",
        "revoked",
        "ledger_restored",
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
    from tests.screening_live_admission_support import protected_admission

    product, task, _ = setup(tmp_path / "product", monkeypatch)
    ledger, evidence_receipt, _ = protected_admission(
        tmp_path / "evidence", monkeypatch, uses=("read-low",)
    )
    now = NOW
    product._now = lambda: now
    observes: list[int] = []
    observe = current_binding.local_binding_components

    def counted(*args: Any, **kwargs: Any) -> dict[BindingComponent, str]:
        observes.append(1)
        return observe(*args, **kwargs)

    monkeypatch.setattr(current_binding, "local_binding_components", counted)
    run = product.tasks.run_pi_once

    def before_transaction(*args: Any, **kwargs: Any) -> ReadAnalysis | ReadTask:
        nonlocal now
        if change == "expired":
            now += timedelta(days=30)
        elif change == "clock_rollback":
            now -= timedelta(seconds=1)
        elif change == "source_lost":
            (ledger.root / "inbox/site.json").unlink()
        elif change == "revoked":
            from paper_radar.live_evidence.lifecycle import EvidenceLifecycle

            EvidenceLifecycle(ledger).tighten(
                evidence_receipt.receipt_id, "read-low", now=NOW
            )
        elif change == "ledger_restored":
            from paper_radar.live_evidence.lifecycle import EvidenceLifecycle

            EvidenceLifecycle(ledger).record_restore(now=NOW)
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
        assert isinstance(result, (ReadAnalysis, ReadTask))
        return result

    monkeypatch.setattr(product.tasks, "run_pi_once", before_transaction)
    with pytest.raises(ExecutionError, match="evidence_missing"):
        product.run_attempt(task.task_id)
    assert product.tasks.task(task.task_id).attempts == ()
    assert product.tasks.analyses(task.paper_id) == ()
    assert len(observes) == 2


def test_dispatched_attempt_crossing_expiry_keeps_existing_settlement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from datetime import timedelta

    from tests.live_evidence_ledger_support import NOW
    from tests.screening_live_admission_support import protected_admission

    product, task, _ = setup(tmp_path / "product", monkeypatch)
    protected_admission(tmp_path / "evidence", monkeypatch, uses=("read-low",))
    now = NOW
    product._now = lambda: now

    def cross_expiry() -> bool:
        nonlocal now
        now += timedelta(days=30)
        return False

    result = product.run_attempt(task.task_id, cancelled=cross_expiry)
    assert isinstance(result, ReadAnalysis)
    assert product.tasks.task(task.task_id).remaining_attempts == 1


def test_tick_failure_denies_before_claim_and_keeps_durable_intent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.live_evidence_ledger_support import NOW
    from tests.screening_live_admission_support import protected_admission

    product, task, _ = setup(tmp_path / "product", monkeypatch)
    _, _, components = protected_admission(
        tmp_path / "evidence", monkeypatch, uses=("read-low",)
    )
    product._now = lambda: NOW
    monkeypatch.setattr(
        "paper_radar.live_evidence.service._run_helper", lambda args: False
    )
    with pytest.raises(ExecutionError, match="evidence_missing"):
        product.run_attempt(task.task_id)
    from tests.screening_live_admission_support import projected_admission

    projection = projected_admission(components, "read-low")
    assert projection.pending_revocation is True
    assert projection.decision.executable is False
    assert product.tasks.task(task.task_id).attempts == ()
    assert product.tasks.analyses(task.paper_id) == ()


def test_runtime_failure_tightens_and_retry_does_not_refill_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.live_evidence_ledger_support import NOW
    from tests.screening_live_admission_support import protected_admission

    product, task, _ = setup(tmp_path / "product", monkeypatch, mode="protocol")
    _, _, components = protected_admission(
        tmp_path / "evidence", monkeypatch, uses=("read-low",)
    )
    product._now = lambda: NOW
    monkeypatch.setattr(
        "paper_radar.live_evidence.service._run_helper", lambda args: args == ("tick",)
    )
    result = product.run_attempt(task.task_id)
    assert isinstance(result, ReadTask)
    assert result.attempts[-1].failure == "protocol_error"
    assert product.tasks.task(task.task_id).remaining_attempts == 1
    from tests.screening_live_admission_support import projected_admission

    projection = projected_admission(components, "read-low")
    assert projection.pending_revocation is True
    assert projection.decision.executable is False
    with pytest.raises(ExecutionError, match="evidence_missing"):
        product.run_attempt(task.task_id)
    assert product.tasks.task(task.task_id).remaining_attempts == 1


def test_product_service_has_no_legacy_alias_read() -> None:
    from tests.live_admission_source_support import legacy_alias_reads

    root = Path(__file__).resolve().parents[1] / "src/paper_radar"
    assert legacy_alias_reads(root) == ()


@pytest.mark.parametrize(
    "state", ["missing_required", "not_activated", "revoked", "receipt_source_missing"]
)
def test_required_gaps_never_refresh_or_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, state: str
) -> None:
    from paper_radar.live_evidence.lifecycle import EvidenceLifecycle
    from tests.live_evidence_ledger_support import NOW
    from tests.screening_live_admission_support import REQUIRED, protected_admission

    product, task, credentials = setup(tmp_path / "product", monkeypatch)
    ledger, receipt, _ = protected_admission(
        tmp_path / "evidence",
        monkeypatch,
        capabilities=("cwd_ancestors",) if state == "missing_required" else REQUIRED,
        uses=("read-low",),
        activate=state != "not_activated",
    )
    product._now = lambda: NOW
    if state == "revoked":
        EvidenceLifecycle(ledger).tighten(receipt.receipt_id, "read-low", now=NOW)
    elif state == "receipt_source_missing":
        (ledger.root / "inbox/site.json").unlink()
    with pytest.raises(ExecutionError, match="evidence_missing"):
        product.run_attempt(task.task_id)
    assert product.tasks.task(task.task_id).attempts == ()
    assert not (credentials / "auth-observed.json").exists()
    assert not tuple(product.data_root.rglob("*.jsonl"))


@pytest.mark.parametrize(
    ("qualification", "reason"),
    [
        ("quality", "prerequisites_failed"),
        ("running", "task_running"),
        ("budget", "budget_exhausted"),
        ("generation", "budget_exhausted"),
        ("input", "read_input_over_budget"),
    ],
)
def test_active_evidence_does_not_grant_read_qualifications(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, qualification: str, reason: str
) -> None:
    from paper_radar.body import BodyService
    from paper_radar.read_tasks import ReadTaskError
    from tests.body_support import CHECKS
    from tests.live_evidence_ledger_support import NOW
    from tests.screening_live_admission_support import protected_admission

    product, task, _ = setup(tmp_path / "product", monkeypatch)
    protected_admission(tmp_path / "evidence", monkeypatch, uses=("read-low",))
    product._now = lambda: NOW
    if qualification == "quality":
        body = BodyService(product.database, product.data_root)
        extraction = body.extraction(task.identity.extraction_fingerprint)
        assert extraction is not None and extraction.identity is not None
        body.review_layout(
            extraction.identity,
            passed=False,
            checks={**CHECKS, "reading_order": False},
            note="rejected",
            actor="human",
            request_id="reject",
        )
    elif qualification == "running":
        product.tasks.claim(task.task_id)
    elif qualification in {"budget", "generation"}:
        product.tasks.fail(product.tasks.claim(task.task_id), "timeout")
        product.tasks.fail(product.tasks.claim(task.task_id), "executor_error")
        if qualification == "generation":
            product.tasks.retry(
                task.task_id, request_id="retry", reason="explicit", actor="human"
            )
    else:
        monkeypatch.setattr("paper_radar.read_inputs.budget.SINGLE_FRAME_BYTES", 1)
    before = product.tasks.task(task.task_id)
    with pytest.raises(ReadTaskError, match=reason):
        product.run_attempt(task.task_id)
    assert product.tasks.task(task.task_id) == before
    assert product.tasks.analyses(task.paper_id) == ()


def test_admitted_experiment_analysis_cannot_be_consumed_as_production(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.read_tasks import ReadTaskError
    from tests.live_evidence_ledger_support import NOW
    from tests.screening_live_admission_support import protected_admission

    product, task, _ = setup(tmp_path / "product", monkeypatch)
    protected_admission(tmp_path / "evidence", monkeypatch, uses=("read-low",))
    product._now = lambda: NOW
    result = product.run_attempt(task.task_id)
    assert isinstance(result, ReadAnalysis)
    assert result.root_purpose == "experiment"
    with pytest.raises(ReadTaskError, match="ordinary_consumption_denied"):
        product.tasks.analysis(result.analysis_id, ordinary=True)


def test_business_restore_and_restart_do_not_refund_attempt_or_revive_grant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dataclasses import replace

    from paper_radar.backup import create_backup, restore_backup
    from paper_radar.read_execution import ReadExecution
    from tests.live_evidence_ledger_support import NOW
    from tests.screening_live_admission_support import protected_admission

    product, task, credentials = setup(
        tmp_path / "product", monkeypatch, mode="protocol"
    )
    protected_admission(tmp_path / "evidence", monkeypatch, uses=("read-low",))
    product._now = lambda: NOW
    monkeypatch.setattr(
        "paper_radar.live_evidence.service._run_helper", lambda args: args == ("tick",)
    )
    failed = product.run_attempt(task.task_id)
    assert isinstance(failed, ReadTask)
    assert failed.remaining_attempts == 1
    backup = create_backup(product.database, product.data_root, tmp_path / "backups")
    restored = tmp_path / "restored"
    restore_backup(backup.batch_dir, restored)
    restarted = ReadExecution(
        restored / "database.sqlite3",
        restored,
        roots=replace(product.roots, data_root=restored),
        credentials_dir=credentials,
        auth_mode=product.auth_mode,
        clock=lambda: NOW,
    )
    with pytest.raises(ExecutionError, match="evidence_missing"):
        restarted.run_attempt(task.task_id)
    after = restarted.tasks.task(task.task_id)
    assert after.remaining_attempts == 1
    assert after.attempts == failed.attempts


def test_observed_model_mismatch_settles_once_and_tightens_before_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.live_evidence_ledger_support import NOW
    from tests.screening_live_admission_support import protected_admission

    product, task, _ = setup(tmp_path / "product", monkeypatch, mode="model_mismatch")
    protected_admission(tmp_path / "evidence", monkeypatch, uses=("read-low",))
    product._now = lambda: NOW
    monkeypatch.setattr(
        "paper_radar.live_evidence.service._run_helper", lambda args: args == ("tick",)
    )
    result = product.run_attempt(task.task_id)
    assert isinstance(result, ReadTask)
    assert result.attempts[-1].failure == "model_mismatch"
    assert result.remaining_attempts == 1
    with pytest.raises(ExecutionError, match="evidence_missing"):
        product.run_attempt(task.task_id)
    assert product.tasks.task(task.task_id).attempts == result.attempts


def test_content_rejection_keeps_capability_and_two_attempt_correction_discipline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.read_tasks import ReadTaskError
    from tests.live_evidence_ledger_support import NOW
    from tests.screening_live_admission_support import protected_admission

    product, task, _ = setup(tmp_path / "product", monkeypatch, mode="degrade")
    _, _, components = protected_admission(
        tmp_path / "evidence", monkeypatch, uses=("read-low",)
    )
    product._now = lambda: NOW
    first = product.run_attempt(task.task_id)
    assert isinstance(first, ReadTask)
    assert first.attempts[-1].failure == "output_invalid"
    assert first.remaining_attempts == 1
    from tests.screening_live_admission_support import projected_admission

    projection = projected_admission(components, "read-low")
    assert projection.pending_revocation is False
    assert projection.decision.executable is True
    second = product.run_attempt(task.task_id)
    assert isinstance(second, ReadAnalysis) and second.attempt_ordinal == 2
    assert product.tasks.task(task.task_id).remaining_attempts == 0
    with pytest.raises(ReadTaskError, match="already_succeeded"):
        product.run_attempt(task.task_id)


def test_disclosure_only_pending_revocation_does_not_block_required_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.live_evidence.service import request_revocation
    from paper_radar.live_evidence.types import Capability
    from tests.live_evidence_ledger_support import NOW
    from tests.screening_live_admission_support import REQUIRED, protected_admission

    product, task, _ = setup(tmp_path / "product", monkeypatch)
    _, receipt, _ = protected_admission(
        tmp_path / "evidence",
        monkeypatch,
        capabilities=(*REQUIRED, "account_limits"),
        uses=("read-low",),
    )
    product._now = lambda: NOW
    monkeypatch.setattr(
        "paper_radar.live_evidence.service._run_helper", lambda args: args == ("tick",)
    )
    assert (
        request_revocation(
            receipt.receipt_id,
            "read-low",
            now=NOW,
            components=frozenset(),
            failed_capabilities=frozenset({Capability.ACCOUNT_LIMITS}),
        )
        is False
    )
    assert isinstance(product.run_attempt(task.task_id), ReadAnalysis)
    assert product.tasks.task(task.task_id).remaining_attempts == 1


def test_transaction_rejection_requests_tightening_only_after_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sqlite3

    from tests.live_evidence_ledger_support import NOW
    from tests.screening_live_admission_support import protected_admission

    product, task, _ = setup(tmp_path / "product", monkeypatch)
    ledger, _, _ = protected_admission(
        tmp_path / "evidence", monkeypatch, uses=("read-low",)
    )
    now = NOW
    product._now = lambda: now
    helper_calls: list[str] = []

    def helper(arguments: tuple[str, ...]) -> bool:
        # 临时业务库可立即取得写锁,证明特权请求不位于领取写事务内。
        with sqlite3.connect(product.database, timeout=0) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.rollback()
        helper_calls.append(arguments[0])
        return True

    monkeypatch.setattr("paper_radar.live_evidence.service._run_helper", helper)
    run = product.tasks.run_pi_once

    def before_transaction(*args: Any, **kwargs: Any) -> ReadAnalysis | ReadTask:
        # 物理来源丢失是真实收紧触发;自然到期只拒绝,不永久撤销。
        (ledger.root / "inbox/site.json").unlink()
        return run(*args, **kwargs)

    monkeypatch.setattr(product.tasks, "run_pi_once", before_transaction)
    with pytest.raises(ExecutionError, match="evidence_missing"):
        product.run_attempt(task.task_id)
    assert helper_calls == ["tick", "revoke"]
    assert product.tasks.task(task.task_id).attempts == ()
