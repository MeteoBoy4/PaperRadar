"""最终审阅回归;临时受保护来源/OS模型,不运行真实sudo。"""

from pathlib import Path

import pytest


def test_readonly_sample_recheck_failure_replaces_the_shared_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.live_evidence.ledger import LedgerError
    from scripts import issue176_admission_snapshot as sampling
    from tests.live_evidence_ledger_support import NOW
    from tests.read_execution_support import setup
    from tests.screening_live_admission_support import protected_admission

    product, _, credentials = setup(tmp_path / "product", monkeypatch)
    protected_admission(
        tmp_path / "evidence",
        monkeypatch,
        uses=("boundary-low", "value-low", "read-low"),
    )
    monkeypatch.setattr(
        sampling, "datetime", type("Clock", (), {"now": staticmethod(lambda tz: NOW)})
    )

    def expired(*args: object, **kwargs: object) -> None:
        raise LedgerError("observation_stale")

    monkeypatch.setattr(sampling, "recheck_admission_request", expired)
    result = sampling.sample(product.database, credentials)
    assert len(result["reports"]) == 3
    for report in result["reports"]:
        assert report["recheck_reason"] == "observation_stale"
        assert report["executable"] is False
        assert report["qualified"] == []
        assert report["reason"] == ["observation_stale"]
        assert "executable=false" in report["doctor_fragment"]
        assert "observation_stale" in report["doctor_fragment"]


def test_screening_settled_model_mismatch_tightens_without_another_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.live_evidence import service as evidence
    from paper_radar.live_evidence.evidence import ExecutionBinding
    from paper_radar.live_evidence.lifecycle import use_for_id
    from paper_radar.live_evidence.types import BindingComponent, Capability
    from paper_radar.pi_execution.errors import ExecutionError
    from paper_radar.screening_tasks import FailureKind, FailureReceipt
    from tests.live_evidence_ledger_support import NOW
    from tests.pi_execution_service_support import service_inputs
    from tests.screening_live_admission_support import protected_admission

    product, receipt, _ = service_inputs(
        tmp_path / "product", monkeypatch, mode="model_mismatch"
    )
    ledger, original, components = protected_admission(
        tmp_path / "evidence", monkeypatch
    )
    product._now = lambda: NOW
    calls = []

    def helper(arguments: tuple[str, ...]) -> bool:
        import sqlite3

        # helper不在业务写事务内;即使helper失败仍保留收紧意图。
        with sqlite3.connect(product.database, timeout=0) as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.rollback()
        calls.append(arguments)
        return arguments == ("tick",)

    monkeypatch.setattr(evidence, "_run_helper", helper)
    settled = product.run_attempt(receipt.receipt_id)
    assert isinstance(settled, FailureReceipt)
    assert settled.kind is FailureKind.MODEL_MISMATCH
    projection = evidence.load_admission_evidence(
        evidence.AdmissionRequest(
            use_for_id("boundary-low"),
            ExecutionBinding(tuple(components.items())),
            frozenset(BindingComponent),
        ),
        now=NOW,
    )
    assert projection.decision.executable is False
    assert projection.pending_revocation is True
    assert projection.decision.for_capability(Capability.MODEL_IDENTITY).revoked is True
    assert (
        projection.decision.for_capability(Capability.CWD_ANCESTORS).qualified is True
    )
    assert any(args[0] == "revoke" for args in calls)
    with pytest.raises(ExecutionError, match="evidence_missing"):
        product.run_attempt(receipt.receipt_id)
    assert product.tasks.status(receipt.receipt_id).used_attempts == 1
    assert (
        product.tasks.status(receipt.receipt_id).last_failure
        is FailureKind.MODEL_MISMATCH
    )
    assert ledger.show(original.receipt_id).receipt == original


@pytest.mark.parametrize(
    "source_name", ["deploy.sh", "uninstall.sh", "owner-workflow.sh", "payload.tar"]
)
def test_g2_root_never_reads_a_source_swapped_after_password_boundary(
    tmp_path: Path, source_name: str
) -> None:
    from tests.site_deployment_checkpoint_support import run_bootstrap
    from tests.site_g2_entry_support import g2_entry_sandbox

    root, runner, _, events = g2_entry_sandbox(tmp_path)
    private = tmp_path / "synthetic-private"
    private.write_bytes(b"synthetic root-private marker must never become public")
    private.chmod(0o600)
    source = runner.with_name(source_name)
    sudo = tmp_path / "sudo-model"
    sudo.write_text(
        sudo.read_text().replace(
            'exec "$@"',
            f'/usr/bin/rm -- "{source}"\n'
            f'/usr/bin/ln -s "{private}" "{source}"\nexec "$@"',
        )
    )
    result = run_bootstrap([str(runner)])
    staged = root / "var/lib/paperradar/live-evidence-staging" / source_name
    assert not staged.exists() or private.read_bytes() not in staged.read_bytes()
    assert result.returncode == 0, result.stderr.decode()
    assert events.read_text().splitlines()[0] == "collect"


@pytest.mark.parametrize("consumer", ["screening", "read"])
@pytest.mark.parametrize("loss", ["receipt", "binding"])
def test_first_source_loss_cannot_revive_old_evidence_after_restoration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, consumer: str, loss: str
) -> None:
    from paper_radar.live_evidence import service as evidence
    from paper_radar.live_evidence.evidence import ExecutionBinding
    from paper_radar.live_evidence.lifecycle import use_for_id
    from paper_radar.live_evidence.receipt import UseId
    from paper_radar.live_evidence.types import BindingComponent
    from paper_radar.pi_execution.errors import ExecutionError
    from paper_radar.pi_execution.service import PiExecution
    from paper_radar.read_execution.service import ReadExecution
    from tests.live_evidence_ledger_support import NOW
    from tests.read_execution_support import setup
    from tests.screening_live_admission_support import (
        product_inputs,
        protected_admission,
    )

    product: PiExecution | ReadExecution
    use_id: UseId
    if consumer == "screening":
        product, request_receipt, credentials = product_inputs(
            tmp_path / "product", monkeypatch
        )
        task_id = request_receipt.receipt_id
        use_id = "boundary-low"
    else:
        product, task, credentials = setup(tmp_path / "product", monkeypatch)
        task_id = task.task_id
        use_id = "read-low"
    ledger, original, components = protected_admission(
        tmp_path / "evidence", monkeypatch, uses=(use_id,)
    )
    product._now = lambda: NOW
    monkeypatch.setattr(evidence, "_run_helper", lambda args: False)
    source = (
        ledger.root
        / "inbox"
        / ("site.json" if loss == "receipt" else "current-observation.json")
    )
    saved = source.read_bytes()
    source.unlink()
    with pytest.raises(ExecutionError, match="evidence_missing"):
        product.run_attempt(task_id)
    source.write_bytes(saved)
    source.chmod(0o644)
    projection = evidence.load_admission_evidence(
        evidence.AdmissionRequest(
            use_for_id(use_id),
            ExecutionBinding(tuple(components.items())),
            frozenset(BindingComponent),
        ),
        now=NOW,
    )
    assert projection.pending_revocation is True
    assert projection.decision.executable is False
    with pytest.raises(ExecutionError, match="evidence_missing"):
        product.run_attempt(task_id)
    assert not (credentials / "auth-observed.json").exists()
    assert ledger.show(original.receipt_id).receipt == original


def test_use_revocation_helper_survives_missing_source_and_preserves_other_cells(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.live_evidence import service as evidence
    from paper_radar.live_evidence import tightening
    from paper_radar.live_evidence.evidence import ExecutionBinding
    from paper_radar.live_evidence.lifecycle import EvidenceLifecycle, use_for_id
    from paper_radar.live_evidence.types import BindingComponent
    from tests.live_evidence_ledger_support import NOW
    from tests.screening_live_admission_support import protected_admission

    ledger, original, components = protected_admission(
        tmp_path / "evidence", monkeypatch, uses=("boundary-low", "read-low")
    )
    monkeypatch.setattr(tightening, "EvidenceLedger", lambda: ledger)
    monkeypatch.setattr(
        tightening, "datetime", type("Clock", (), {"now": staticmethod(lambda tz: NOW)})
    )
    monkeypatch.setattr(
        evidence,
        "_run_helper",
        lambda args: tightening.tightening_main(list(args)) == 0,
    )
    path = ledger.root / "inbox/site.json"
    saved = path.read_bytes()
    path.unlink()
    assert evidence.request_use_revocation("boundary-low", now=NOW) is True
    path.write_bytes(saved)
    path.chmod(0o644)
    snapshot = EvidenceLifecycle(ledger).snapshot(now=NOW)
    selected = [
        item for item in snapshot.evidence if item.use == use_for_id("boundary-low")
    ]
    assert selected and all(item.revoked for item in selected)
    reading = evidence.load_admission_evidence(
        evidence.AdmissionRequest(
            use_for_id("read-low"),
            ExecutionBinding(tuple(components.items())),
            frozenset(BindingComponent),
        ),
        now=NOW,
    )
    assert reading.decision.executable is True
    assert ledger.show(original.receipt_id).receipt == original


def test_large_frozen_payload_uses_stdin_without_exec_argument_limit(
    tmp_path: Path,
) -> None:
    import hashlib

    from paper_radar.live_evidence.deployment import G2_ROOT_FILES, render_g2_runner
    from tests.site_deployment_checkpoint_support import model_bootstrap, run_bootstrap
    from tests.site_g2_entry_support import g2_entry_sandbox

    root, runner, _, _ = g2_entry_sandbox(tmp_path)
    runner.with_name("payload.tar").write_bytes(b"large-reviewed-data" * 20000)
    runner.with_name("deploy.sh").write_text("exit 0\n")
    files = {name: runner.with_name(name).read_bytes() for name in G2_ROOT_FILES}
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    source = model_bootstrap(render_g2_runner(hashes, sealed_files=files), root)
    runner.write_text(source.replace("/usr/bin/sudo", str(tmp_path / "sudo-model")))
    result = run_bootstrap([str(runner)])
    assert result.returncode == 0, result.stderr.decode()
    assert (
        root / "var/lib/paperradar/live-evidence-staging/payload.tar"
    ).read_bytes() == files["payload.tar"]


@pytest.mark.parametrize("consumer", ["screening", "read"])
@pytest.mark.parametrize(
    "gap",
    [
        "stale_observation",
        "missing_capabilities",
        "not_activated",
        "capability_expired",
    ],
)
def test_ordinary_qualification_gaps_do_not_revoke_independent_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, consumer: str, gap: str
) -> None:
    from datetime import timedelta

    from paper_radar.live_evidence import service as evidence
    from paper_radar.live_evidence.evidence import ExecutionBinding
    from paper_radar.live_evidence.lifecycle import use_for_id
    from paper_radar.live_evidence.observation import CurrentObservation
    from paper_radar.live_evidence.receipt import UseId, canonical_bytes
    from paper_radar.live_evidence.types import BindingComponent, Capability
    from paper_radar.pi_execution.errors import ExecutionError
    from paper_radar.pi_execution.service import PiExecution
    from paper_radar.read_execution.service import ReadExecution
    from tests.live_evidence_ledger_support import NOW
    from tests.read_execution_support import setup
    from tests.screening_live_admission_support import (
        REQUIRED,
        product_inputs,
        protected_admission,
    )

    product: PiExecution | ReadExecution
    use_id: UseId
    if consumer == "screening":
        product, request, credentials = product_inputs(
            tmp_path / "product", monkeypatch
        )
        identifier, use_id = request.receipt_id, "boundary-low"
    else:
        product, task, credentials = setup(tmp_path / "product", monkeypatch)
        identifier, use_id = task.task_id, "read-low"
    site = (
        "auth_cache_current",
        "auth_cache_baseline",
        "cwd_ancestors",
        "file_isolation",
        "zero_core",
        "apport_identity",
        "supply_tree",
        "instance_tree",
        "pi_version",
        "launch_policy",
        "isolation_policy",
        "host_runtime",
    )
    ledger, original, components = protected_admission(
        tmp_path / "evidence",
        monkeypatch,
        uses=(use_id,),
        capabilities=site if gap == "missing_capabilities" else REQUIRED,
        activate=gap != "not_activated",
    )
    now = NOW + (
        timedelta(seconds=61)
        if gap == "stale_observation"
        else timedelta(days=30)
        if gap == "capability_expired"
        else timedelta()
    )
    product._now = lambda: now
    monkeypatch.setattr(evidence, "_run_helper", lambda args: False)
    observation = ledger.root / "inbox/current-observation.json"
    if gap == "capability_expired":
        observed = CurrentObservation.model_validate_json(observation.read_bytes())
        observation.write_bytes(
            canonical_bytes(observed.model_copy(update={"observed_at": now}))
        )
    with pytest.raises(ExecutionError, match="evidence_missing"):
        product.run_attempt(identifier)
    projection = evidence.load_admission_evidence(
        evidence.AdmissionRequest(
            use_for_id(use_id),
            ExecutionBinding(tuple(components.items())),
            frozenset(BindingComponent),
        ),
        now=now,
    )
    assert projection.pending_revocation is False
    assert all(not item.revoked for item in projection.decision.capabilities)
    if gap != "not_activated":
        assert (
            projection.decision.for_capability(Capability.CWD_ANCESTORS).qualified
            is True
        )
    if gap == "stale_observation":
        # 同事实的新鲜观察恢复适用性,未续verified_at或解除真正撤销。
        observed = CurrentObservation.model_validate_json(observation.read_bytes())
        observation.write_bytes(
            canonical_bytes(observed.model_copy(update={"observed_at": now}))
        )
        from paper_radar.pi_execution.admission_guard import AdmissionGuard
        from paper_radar.pi_execution.current_binding import build_admission_request
        from tests.test_pi_execution_admission import binding as execution_binding

        refreshed = build_admission_request(
            product.database,
            execution_binding(),
            use=use_for_id(use_id),
            credentials_dir=credentials,
            now=now,
        )
        assert (
            AdmissionGuard(use_for_id(use_id))
            .check(refreshed, now=now)
            .decision.executable
            is True
        )
    assert not (credentials / "auth-observed.json").exists()
    assert ledger.show(original.receipt_id).receipt == original
