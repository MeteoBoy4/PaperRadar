"""一次执行公开 seam:领取前拒绝和真实本机标准库对端。"""

from pathlib import Path

import pytest

from paper_radar.pi_execution import ExecutionError


def test_product_missing_evidence_never_claims_or_refreshes_auth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.pi_execution.service import PiExecution
    from tests.pi_execution_service_support import service_inputs

    service, receipt, credentials = service_inputs(tmp_path, monkeypatch)
    assert isinstance(service, PiExecution)
    with pytest.raises(ExecutionError, match="evidence_missing"):
        service.run_attempt(receipt.receipt_id)
    assert service.tasks.status(receipt.receipt_id).used_attempts == 0
    assert (
        service.tasks.query_successes(
            paper_id=receipt.paper_id, stage="boundary", snapshot_id=receipt.snapshot_id
        )
        == ()
    )
    assert not (credentials / "auth-observed.json").exists()


def test_controlled_local_peer_reaches_authoritative_pi_rpc_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.pi_execution.service import prepare_call
    from paper_radar.screening_tasks import SuccessReceipt
    from tests.pi_execution_service_support import allow_synthetic, service_inputs

    service, receipt, credentials = service_inputs(tmp_path, monkeypatch)
    description = prepare_call(service.tasks, receipt.receipt_id)
    assert description.sampling == "provider_default"
    assert description.temperature is None and description.top_p is None
    allow_synthetic(monkeypatch)
    monkeypatch.setenv("NODE_OPTIONS", "private-sentinel")
    monkeypatch.setenv("XDG_CONFIG_HOME", "private-sentinel")
    result = service.run_attempt(receipt.receipt_id)
    assert isinstance(result, SuccessReceipt)
    assert result.executor_kind == "pi_rpc"
    saved = service.tasks.load_success(result.success_id)
    from paper_radar.screening.schema import BoundaryOutput

    assert isinstance(saved.output, BoundaryOutput)
    assert saved.output.boundary == "in_scope"
    assert (saved.audit["input_tokens"], saved.audit["output_tokens"]) == (5, 2)
    assert saved.audit["provider_request_id"] is None
    assert "private-sentinel" not in repr(saved)
    assert "oauth-test-only-sensitive-sentinel" not in repr(saved)
    assert (credentials / "auth-observed.json").exists()
    service.tasks.validate_all()


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("timeout", "timeout"),
        ("environment", "executor_error"),
        ("protocol", "protocol_error"),
        ("cwd_mismatch", "protocol_error"),
        ("orphan", "timeout"),
        ("model_mismatch", "model_mismatch"),
        ("output_invalid", "output_invalid"),
    ],
)
def test_runtime_categories_and_opt_in_cwd_consume_one_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, expected: str
) -> None:
    from paper_radar.llm.rpc_types import RpcLimits
    from paper_radar.screening_tasks import FailureReceipt
    from tests.pi_execution_service_support import allow_synthetic, service_inputs

    service, receipt, _ = service_inputs(tmp_path, monkeypatch, mode=mode)
    allow_synthetic(monkeypatch)
    result = service.run_attempt(
        receipt.receipt_id,
        limits=RpcLimits(total=0.5, initialization=0.4, close=0.2, terminate=1),
    )
    assert isinstance(result, FailureReceipt)
    assert result.kind.value == expected
    from paper_radar.pi_supply import activation_history, probe_install

    selected = activation_history(service.database)[-1]
    assert (
        probe_install(service.database, selected.supply_id, selected.install_id).state
        == "idle"
    )
    assert service.tasks.status(receipt.receipt_id).used_attempts == 1
    assert (
        service.tasks.query_successes(
            paper_id=receipt.paper_id, stage="boundary", snapshot_id=receipt.snapshot_id
        )
        == ()
    )


def test_cancelled_attempt_and_explicit_retry_keep_budget_and_new_sessions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.screening_tasks import FailureReceipt, SuccessReceipt
    from tests.pi_execution_service_support import allow_synthetic, service_inputs

    service, receipt, _ = service_inputs(tmp_path, monkeypatch)
    allow_synthetic(monkeypatch)
    first = service.run_attempt(receipt.receipt_id, cancelled=lambda: True)
    assert isinstance(first, FailureReceipt) and first.kind.value == "cancelled"
    second = service.run_attempt(receipt.receipt_id, cancelled=lambda: True)
    assert isinstance(second, FailureReceipt) and second.attempt_no == 2
    assert service.tasks.status(receipt.receipt_id).used_attempts == 2
    retried = service.tasks.retry(
        dict(
            parent_task_id=receipt.task_id,
            paper_id=receipt.paper_id,
            stage="boundary",
            snapshot_id=receipt.snapshot_id,
            request_id="explicit-retry",
            reason="重新尝试",
            actor="owner",
        )
    )
    final = service.run_attempt(retried.receipt_id)
    assert isinstance(final, SuccessReceipt) and final.attempt_no == 1


@pytest.mark.parametrize(
    ("evidence_kind", "expected"),
    [
        ("mismatch", "evidence_mismatch"),
        ("cwd", "cwd_evidence_missing"),
        ("rpc", "rpc_evidence_missing"),
        ("model", "model_evidence_missing"),
    ],
)
def test_bound_evidence_failures_never_refresh_or_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, evidence_kind: str, expected: str
) -> None:
    from dataclasses import replace

    from paper_radar.pi_execution.admission import AdmissionEvidence, EvidenceBinding
    from tests.pi_execution_service_support import service_inputs

    service, receipt, credentials = service_inputs(tmp_path, monkeypatch)

    def evidence(binding: EvidenceBinding) -> AdmissionEvidence:
        return AdmissionEvidence(
            replace(binding, install_id="0" * 32)
            if evidence_kind == "mismatch"
            else binding,
            evidence_kind != "cwd",
            evidence_kind != "rpc",
            evidence_kind != "model",
        )

    monkeypatch.setattr("paper_radar.pi_execution.service._evidence_for", evidence)
    with pytest.raises(ExecutionError, match=expected):
        service.run_attempt(receipt.receipt_id)
    assert service.tasks.status(receipt.receipt_id).used_attempts == 0
    assert not (credentials / "auth-observed.json").exists()


@pytest.mark.parametrize("legacy", [False, True])
def test_explicit_sampling_is_valid_but_has_no_execution_mapping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, legacy: bool
) -> None:
    import yaml

    from paper_radar.config import compile_config
    from tests.pi_execution_service_support import service_inputs

    service, receipt, credentials = service_inputs(tmp_path, monkeypatch, legacy=legacy)
    if not legacy:
        settings = tmp_path / "config/settings.yaml"
        models = tmp_path / "config/models/models-v3.yaml"
        content = yaml.safe_load((models.parent / "models-v2.yaml").read_text())
        content["version"] = "models-v3"
        content["screening"].update(sampling="explicit", temperature=0.2, top_p=0.9)
        models.write_text(yaml.safe_dump(content))
        settings.write_text(settings.read_text().replace("models-v2", "models-v3"))
        snapshot = compile_config(settings, service.tasks.database)
        receipt = service.tasks.register(
            dict(
                paper_id=receipt.paper_id,
                snapshot_id=snapshot.snapshot_id,
                stage="boundary",
                source="scheduled",
                scheduled_day="2026-01-01",
            )
        )
    with pytest.raises(ExecutionError, match="sampling_mapping_unavailable"):
        service.run_attempt(receipt.receipt_id)
    assert service.tasks.status(receipt.receipt_id).used_attempts == 0
    assert not (credentials / "auth-observed.json").exists()


@pytest.mark.parametrize(
    ("problem", "expected"),
    [
        ("cwd", "cwd_not_empty"),
        ("isolation", "isolation_unavailable"),
        ("auth", "auth_failed"),
        ("install", "install_unavailable"),
        ("credentials", "credentials_invalid"),
        ("cwd_missing", "cwd_invalid"),
    ],
)
def test_preclaim_resource_and_auth_failures_keep_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, problem: str, expected: str
) -> None:
    import json

    from tests.pi_execution_service_support import allow_synthetic, service_inputs

    service, receipt, credentials = service_inputs(tmp_path, monkeypatch)
    allow_synthetic(monkeypatch)
    if problem == "cwd":
        (tmp_path / "cwd/project-context").write_text("private-sentinel")
    elif problem == "install":
        service.roots.install_root.rename(tmp_path / "unavailable-install")
    elif problem == "credentials":
        credentials.chmod(0o755)
    elif problem == "cwd_missing":
        (tmp_path / "cwd").rmdir()
    elif problem == "auth":
        path = credentials / "auth.json"
        content = json.loads(path.read_text())
        content["mode"] = "failure"
        path.write_text(json.dumps(content))
    else:

        def unavailable() -> int:
            raise ExecutionError("isolation_unavailable")

        monkeypatch.setattr(
            "paper_radar.pi_execution.launcher.isolation_capability", unavailable
        )
    with pytest.raises(ExecutionError, match=expected) as error:
        service.run_attempt(receipt.receipt_id)
    assert "private-sentinel" not in repr(error.value)
    assert "oauth-test-only-sensitive-sentinel" not in repr(error.value)
    assert service.tasks.status(receipt.receipt_id).used_attempts == 0


@pytest.mark.parametrize("problem", ["cwd", "exec"])
def test_postclaim_startup_failures_are_budgeted_executor_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, problem: str
) -> None:
    from paper_radar.screening_tasks import FailureReceipt
    from tests.pi_execution_service_support import allow_synthetic, service_inputs

    service, receipt, _ = service_inputs(tmp_path, monkeypatch)
    allow_synthetic(monkeypatch)

    def after_claim() -> bool:
        if problem == "cwd":
            (tmp_path / "cwd/project-context").write_text("private-sentinel")
        else:
            monkeypatch.setattr("paper_radar.pi_execution.isolation._RUNTIME_PATHS", ())
        return False

    result = service.run_attempt(receipt.receipt_id, cancelled=after_claim)
    assert isinstance(result, FailureReceipt)
    assert result.kind.value == "executor_error"
    assert service.tasks.status(receipt.receipt_id).used_attempts == 1
    assert "private-sentinel" not in repr(result)


@pytest.mark.parametrize(
    ("prompt", "reason"),
    [(b"/private-sentinel", "system_prompt_path"), (b"x" * 131072, "argv_limit")],
)
def test_system_prompt_and_argv_limits_are_preclaim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, prompt: bytes, reason: str
) -> None:
    import hashlib

    import yaml

    from paper_radar.config import compile_config
    from tests.pi_execution_service_support import service_inputs

    service, receipt, credentials = service_inputs(tmp_path, monkeypatch)
    config = tmp_path / "config"
    (config / "prompts/pi-system-v2.md").write_bytes(prompt)
    adapter = yaml.safe_load((config / "adapters/pi-v1.yaml").read_text())
    adapter["version"] = "pi-v2"
    adapter["resources"][0].update(
        version="v2", sha256=hashlib.sha256(prompt).hexdigest()
    )
    (config / "adapters/pi-v2.yaml").write_text(yaml.safe_dump(adapter))
    settings = config / "settings.yaml"
    settings.write_text(
        settings.read_text().replace("screening: pi-v1", "screening: pi-v2")
    )
    snapshot = compile_config(settings, service.tasks.database)
    updated = service.tasks.register(
        dict(
            paper_id=receipt.paper_id,
            stage="boundary",
            snapshot_id=snapshot.snapshot_id,
            source="scheduled",
            scheduled_day="2026-01-01",
        )
    )
    with pytest.raises(ExecutionError, match=reason):
        service.run_attempt(updated.receipt_id)
    assert service.tasks.status(updated.receipt_id).used_attempts == 0
    assert not (credentials / "auth-observed.json").exists()


def test_audit_snapshot_can_change_while_budget_first_semantics_stay_fixed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.config import compile_config
    from paper_radar.pi_execution.service import prepare_call
    from paper_radar.screening_tasks import SuccessReceipt
    from tests.pi_execution_service_support import allow_synthetic, service_inputs

    service, initial, _ = service_inputs(tmp_path, monkeypatch)
    config = tmp_path / "config"
    adapter = config / "adapters/pi-v1.yaml"
    (config / "adapters/pi-v2.yaml").write_text(
        adapter.read_text()
        .replace("version: pi-v1", "version: pi-v2")
        .replace("transport-v1", "transport-v2")
    )
    settings = config / "settings.yaml"
    settings.write_text(
        settings.read_text().replace("screening: pi-v1", "screening: pi-v2")
    )
    snapshot = compile_config(settings, service.tasks.database)
    updated = service.tasks.register(
        dict(
            paper_id=initial.paper_id,
            stage="boundary",
            snapshot_id=snapshot.snapshot_id,
            source="scheduled",
            scheduled_day="2026-01-01",
        )
    )
    assert updated.budget_id == initial.budget_id
    description = prepare_call(service.tasks, updated.receipt_id)
    assert description.semantic_snapshot_id == initial.snapshot_id
    assert description.audit_snapshot_id == updated.snapshot_id
    allow_synthetic(monkeypatch)
    result = service.run_attempt(updated.receipt_id)
    assert isinstance(result, SuccessReceipt)
    assert (
        service.tasks.load_success(result.success_id).audit["adapter_version"]
        == "transport-v2"
    )


def test_interruption_preserves_lease_until_explicit_expired_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from datetime import UTC, datetime, timedelta

    from paper_radar.pi_execution.service import PiExecution
    from tests.pi_execution_service_support import allow_synthetic, service_inputs

    original, receipt, credentials = service_inputs(tmp_path, monkeypatch)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    service = PiExecution(
        original.database,
        original.data_root,
        roots=original.roots,
        credentials_dir=credentials,
        auth_mode="chatgpt_subscription",
        clock=lambda: now,
    )
    allow_synthetic(monkeypatch)

    def interrupt() -> bool:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        service.run_attempt(receipt.receipt_id, cancelled=interrupt)
    assert service.tasks.status(receipt.receipt_id).state == "running"
    now += timedelta(seconds=601)
    result = service.tasks.reclaim(receipt.receipt_id)
    assert (
        result.last_failure is not None
        and result.last_failure.value == "outcome_unknown"
    )
    assert service.tasks.status(receipt.receipt_id).used_attempts == 1


def test_outer_wire_expansion_refuses_before_auth_or_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.papers import PaperFacts
    from paper_radar.screening_tasks import TaskError
    from tests.pi_execution_service_support import service_inputs
    from tests.test_paper_mapping import screening_fields
    from tests.test_paper_service import observation

    service, original, credentials = service_inputs(tmp_path, monkeypatch)
    paper = PaperFacts(service.tasks.database, service.data_root).submit(
        observation(doi="10.1234/wire", fields=screening_fields(abstract='"' * 120000))
    )
    receipt = service.tasks.register(
        dict(
            paper_id=paper.paper_id,
            snapshot_id=original.snapshot_id,
            stage="boundary",
            source="scheduled",
            scheduled_day="2026-01-01",
        )
    )
    with pytest.raises(TaskError, match="invalid_context"):
        service.run_attempt(receipt.receipt_id)
    assert service.tasks.status(receipt.receipt_id).used_attempts == 0
    assert not (credentials / "auth-observed.json").exists()


@pytest.mark.parametrize("failure", ["snapshot", "protocol"])
def test_corrupt_snapshot_or_unregistered_protocol_is_preclaim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    import sqlite3

    from paper_radar.config import compile_config
    from paper_radar.screening_tasks import TaskError
    from tests.pi_execution_service_support import service_inputs

    service, receipt, credentials = service_inputs(tmp_path, monkeypatch)
    if failure == "protocol":
        config = tmp_path / "config"
        old = config / "adapters/pi-v1.yaml"
        (config / "adapters/pi-v2.yaml").write_text(
            old.read_text()
            .replace("version: pi-v1", "version: pi-v2")
            .replace("1.4.0", "1.4.99")
        )
        settings = config / "settings.yaml"
        settings.write_text(
            settings.read_text().replace("screening: pi-v1", "screening: pi-v2")
        )
        snapshot = compile_config(settings, service.tasks.database)
        receipt = service.tasks.register(
            dict(
                paper_id=receipt.paper_id,
                snapshot_id=snapshot.snapshot_id,
                stage="boundary",
                source="scheduled",
                scheduled_day="2026-01-01",
            )
        )
    else:
        with sqlite3.connect(service.tasks.database) as connection:
            connection.execute(
                "UPDATE runtime_config_snapshots SET payload_json=? "
                "WHERE snapshot_id=?",
                ("private-sentinel", receipt.snapshot_id),
            )
    with pytest.raises(
        TaskError,
        match="invalid_context" if failure == "protocol" else "corrupt_reference",
    ) as error:
        service.run_attempt(receipt.receipt_id)
    assert "private-sentinel" not in repr(error.value)
    if failure == "protocol":
        assert service.tasks.status(receipt.receipt_id).used_attempts == 0
    assert not (credentials / "auth-observed.json").exists()


def test_sink_receives_only_existing_safe_task_events(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from collections.abc import Mapping

    from paper_radar.pi_execution.service import PiExecution
    from paper_radar.screening_tasks import SuccessReceipt
    from tests.pi_execution_service_support import allow_synthetic, service_inputs

    events: list[Mapping[str, object]] = []

    class Capture:
        def emit(self, event: Mapping[str, object]) -> None:
            events.append(event)

    original, receipt, credentials = service_inputs(tmp_path, monkeypatch)
    service = PiExecution(
        original.database,
        original.data_root,
        roots=original.roots,
        credentials_dir=credentials,
        auth_mode="chatgpt_subscription",
        sink=Capture(),
    )
    with pytest.raises(ExecutionError, match="evidence_missing"):
        service.run_attempt(receipt.receipt_id)
    assert events == []
    allow_synthetic(monkeypatch)
    result = service.run_attempt(receipt.receipt_id)
    assert isinstance(result, SuccessReceipt)
    assert {event["event"] for event in events} >= {"claimed", "succeeded"}
    observed = repr(events) + repr(capsys.readouterr())
    for secret in (
        "oauth-test-only-sensitive-sentinel",
        "Frozen effective Pi system prompt",
        "论文研究天气过程",
        "real-model",
    ):
        assert secret not in observed
