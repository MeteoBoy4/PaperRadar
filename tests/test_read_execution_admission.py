"""D1真实产品准入只验证领取前拒绝;工程替身不授予EXP-2。"""

from pathlib import Path

import pytest

from paper_radar.pi_execution import ExecutionError
from tests.read_execution_support import allow_engineering_path, setup


def test_missing_evidence_does_not_authenticate_claim_or_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, task, credentials = setup(tmp_path, monkeypatch)
    with pytest.raises(ExecutionError, match="evidence_missing"):
        service.run_attempt(task.task_id)
    assert service.tasks.task(task.task_id).remaining_attempts == 2
    assert service.tasks.analyses(task.paper_id) == ()
    assert not (credentials / "auth-observed.json").exists()
    assert not tuple(service.data_root.rglob("*.jsonl"))


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        ("mismatch", "evidence_mismatch"),
        ("cwd", "cwd_evidence_missing"),
        ("rpc", "rpc_evidence_missing"),
        ("model", "model_evidence_missing"),
    ],
)
def test_inapplicable_or_unmeasured_evidence_does_not_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str, expected: str
) -> None:
    from dataclasses import replace

    from paper_radar.pi_execution.admission import AdmissionEvidence, EvidenceBinding

    service, task, credentials = setup(tmp_path, monkeypatch)

    def evidence(binding: EvidenceBinding) -> AdmissionEvidence:
        return AdmissionEvidence(
            replace(binding, install_id="0" * 32) if kind == "mismatch" else binding,
            kind != "cwd",
            kind != "rpc",
            kind != "model",
        )

    allow_engineering_path(monkeypatch, evidence)
    with pytest.raises(ExecutionError, match=expected):
        service.run_attempt(task.task_id)
    assert service.tasks.task(task.task_id).attempts == ()
    assert not (credentials / "auth-observed.json").exists()


@pytest.mark.parametrize("admitted", [False, True])
def test_admission_precedes_full_frame_budget_and_neither_spends_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, admitted: bool
) -> None:
    from paper_radar.read_tasks import ReadTaskError
    from tests.read_execution_support import allow_engineering_path

    service, task, credentials = setup(tmp_path, monkeypatch)
    # 模拟收紧后的本地帧边界;无公开产品开关,不构成现场准入。
    monkeypatch.setattr("paper_radar.read_inputs.budget.SINGLE_FRAME_BYTES", 1)
    if admitted:
        allow_engineering_path(monkeypatch)
    error = ReadTaskError if admitted else ExecutionError
    with pytest.raises(
        error, match="read_input_over_budget" if admitted else "evidence_missing"
    ):
        service.run_attempt(task.task_id)
    assert service.tasks.task(task.task_id).attempts == ()
    assert not (credentials / "auth-observed.json").exists()


@pytest.mark.parametrize(
    ("problem", "reason"),
    [
        ("cwd", "cwd_not_empty"),
        ("credentials", "credentials_invalid"),
        ("auth", "auth_failed"),
        ("install", "install_unavailable"),
        ("isolation", "isolation_unavailable"),
    ],
)
def test_resource_and_auth_failure_stay_before_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, problem: str, reason: str
) -> None:
    import json

    from tests.read_execution_support import allow_engineering_path

    service, task, credentials = setup(tmp_path, monkeypatch)
    allow_engineering_path(monkeypatch)
    if problem == "cwd":
        (tmp_path / "cwd/private-sentinel").write_text("PRIVATE BODY")
    elif problem == "credentials":
        credentials.chmod(0o755)
    elif problem == "auth":
        (credentials / "auth.json").write_text(
            json.dumps({"token": "AUTH PRIVATE SENTINEL", "mode": "failure"})
        )
    elif problem == "install":
        service.roots.install_root.rename(tmp_path / "unavailable")
    else:

        def unavailable() -> int:
            raise ExecutionError("isolation_unavailable")

        monkeypatch.setattr(
            "paper_radar.pi_execution.launcher.isolation_capability", unavailable
        )
    with pytest.raises(ExecutionError, match=reason) as error:
        service.run_attempt(task.task_id)
    assert "PRIVATE" not in repr(error.value)
    assert service.tasks.task(task.task_id).attempts == ()


def test_explicit_sampling_is_not_a_model_parameter_measurement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import yaml

    from paper_radar.config import compile_config

    service, task, credentials = setup(tmp_path, monkeypatch)
    config = service.roots.config_root
    source = config / "models/models-read-default-v1.yaml"
    models = yaml.safe_load(source.read_text())
    models["version"] = "models-read-explicit-v1"
    models["reading"].update(sampling="explicit", temperature=0.2, top_p=0.9)
    source.with_name("models-read-explicit-v1.yaml").write_text(yaml.safe_dump(models))
    settings = config / "settings.yaml"
    settings.write_text(
        settings.read_text().replace(
            "models-read-default-v1", "models-read-explicit-v1"
        )
    )
    snapshot = compile_config(settings, service.database)
    explicit = service.tasks.register(
        task.paper_id,
        snapshot_id=snapshot.snapshot_id,
        extraction_fingerprint=task.identity.extraction_fingerprint,
        request_id="explicit",
    )
    with pytest.raises(ExecutionError, match="sampling_mapping_unavailable"):
        service.run_attempt(explicit.task_id)
    assert service.tasks.task(explicit.task_id).attempts == ()
    assert not (credentials / "auth-observed.json").exists()


@pytest.mark.parametrize("timeout", [True, 0.0, float("nan"), 301.0])
def test_invalid_timeout_is_controlled_before_auth_or_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, timeout: float
) -> None:
    from paper_radar.llm.rpc_types import RpcLimits

    service, task, credentials = setup(tmp_path, monkeypatch)
    with pytest.raises(ExecutionError, match="timeout_invalid"):
        service.run_attempt(task.task_id, limits=RpcLimits(total=timeout))
    assert service.tasks.task(task.task_id).attempts == ()
    assert not (credentials / "auth-observed.json").exists()


def test_different_data_root_cannot_bypass_shared_serial_resource(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dataclasses import replace

    service, task, credentials = setup(tmp_path, monkeypatch)
    service.roots = replace(service.roots, data_root=tmp_path / "different")
    with pytest.raises(ExecutionError, match="resources_invalid"):
        service.run_attempt(task.task_id)
    assert service.tasks.task(task.task_id).attempts == ()
    assert not (credentials / "auth-observed.json").exists()
