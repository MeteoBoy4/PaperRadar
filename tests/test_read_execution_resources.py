"""D1串行资源、安装保护、认证期间最新领取与中断回收。"""

import os
import subprocess
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from paper_radar.pi_execution import ExecutionError
from paper_radar.pi_supply import activation_history, probe_install
from paper_radar.read_tasks import ReadAnalysis, ReadTask
from paper_radar.read_tasks.execution import execution_resource
from tests.read_execution_support import allow_engineering_path, setup


def test_waiting_for_same_root_resource_does_not_authenticate_or_spend_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, task, credentials = setup(tmp_path, monkeypatch)
    started = threading.Event()
    done = threading.Event()
    errors: list[BaseException] = []

    def execute() -> None:
        started.set()
        try:
            service.run_attempt(task.task_id)
        except BaseException as error:
            errors.append(error)
        finally:
            done.set()

    with execution_resource(service.data_root):
        thread = threading.Thread(target=execute)
        thread.start()
        assert started.wait(2)
        assert not done.wait(0.1)
        assert service.tasks.task(task.task_id).attempts == ()
        assert not (credentials / "auth-observed.json").exists()
    thread.join(10)
    assert done.is_set() and len(errors) == 1
    assert (
        isinstance(errors[0], ExecutionError) and errors[0].reason == "evidence_missing"
    )
    assert service.tasks.task(task.task_id).attempts == ()


def test_auth_holds_install_protection_and_claim_uses_latest_correction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.read_tasks_support import valid_candidate

    service, task, _ = setup(tmp_path, monkeypatch, mode="require_correction")
    allow_engineering_path(monkeypatch)
    first = service.tasks.claim(task.task_id)
    popen = subprocess.Popen
    selected = activation_history(service.database)[-1]
    observed: list[str] = []

    def spawn(*args: Any, **kwargs: Any) -> subprocess.Popen[bytes]:
        observed.append(
            probe_install(
                service.database, selected.supply_id, selected.install_id
            ).state
        )
        if "auth" in args[0]:
            raw = valid_candidate(
                main_findings=[
                    {
                        "statement": "错误项。",
                        "evidence": [{"evidence_id": "BAD PRIVATE ID"}],
                    }
                ]
            )
            result = service.tasks.submit_test(first, raw)
            assert (
                isinstance(result, ReadTask)
                and result.attempts[0].failure == "output_invalid"
            )
        return popen(*args, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", spawn)
    result = service.run_attempt(task.task_id)
    assert isinstance(result, ReadAnalysis) and result.attempt_ordinal == 2
    assert observed == ["in_flight", "in_flight"]
    assert (
        probe_install(service.database, selected.supply_id, selected.install_id).state
        == "idle"
    )


@pytest.mark.parametrize("interruption", [KeyboardInterrupt, SystemExit])
def test_model_interruption_reaps_entire_group_and_recovers_unknown_without_refund(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, interruption: type[BaseException]
) -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    service, task, _ = setup(tmp_path, monkeypatch, mode="timeout", clock=lambda: now)
    allow_engineering_path(monkeypatch)
    popen = subprocess.Popen
    children: list[subprocess.Popen[bytes]] = []
    directories: list[Path] = []

    def spawn(*args: Any, **kwargs: Any) -> subprocess.Popen[bytes]:
        child = popen(*args, **kwargs)
        if "auth" not in args[0]:
            children.append(child)
            directories.append(Path(kwargs["env"]["PI_CODING_AGENT_DIR"]).parent)
        return child

    def cancelled() -> bool:
        if children:
            raise interruption
        return False

    monkeypatch.setattr(subprocess, "Popen", spawn)
    with pytest.raises(interruption):
        service.run_attempt(task.task_id, cancelled=cancelled)
    assert len(children) == 1 and children[0].poll() is not None
    with pytest.raises(ProcessLookupError):
        os.killpg(children[0].pid, 0)
    assert not directories[0].exists()
    assert all(
        stream is not None and stream.closed
        for stream in (children[0].stdin, children[0].stdout, children[0].stderr)
    )
    view = service.tasks.task(task.task_id)
    assert view.status == "running" and view.remaining_attempts == 1
    assert view.attempts[0].failure is None
    now += timedelta(seconds=601)
    reclaimed = service.tasks.reclaim(task.task_id)
    assert (
        reclaimed.attempts[0].failure == "outcome_unknown"
        and reclaimed.remaining_attempts == 1
    )
    selected = activation_history(service.database)[-1]
    assert (
        probe_install(service.database, selected.supply_id, selected.install_id).state
        == "idle"
    )
    service.tasks.validate_all()


def test_activation_change_after_prebinding_is_rejected_before_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.pi_execution.admission import AdmissionEvidence, EvidenceBinding
    from paper_radar.pi_supply import activate_supply, rebuild_supply
    from tests.pi_rpc_source_support import RpcSupplyRun
    from tests.pi_supply_support import Download

    service, task, _ = setup(tmp_path, monkeypatch)
    selected = activation_history(service.database)[-1]

    def evidence(binding: EvidenceBinding) -> AdmissionEvidence:
        rebuilt = rebuild_supply(
            service.database,
            selected.supply_id,
            service.roots.install_root,
            data_root=service.data_root,
            config_root=service.roots.config_root,
            material_root=service.roots.material_root,
            downloader=Download(),
            runner=RpcSupplyRun(),
        )
        assert rebuilt.install_id != selected.install_id
        activate_supply(service.database, selected.supply_id, task.snapshot_id)
        return AdmissionEvidence(binding, True, True, True)

    monkeypatch.setattr("paper_radar.read_execution.service._evidence_for", evidence)
    with pytest.raises(ExecutionError, match="evidence_mismatch"):
        service.run_attempt(task.task_id)
    assert service.tasks.task(task.task_id).attempts == ()
    current = activation_history(service.database)[-1]
    assert (
        probe_install(service.database, current.supply_id, current.install_id).state
        == "idle"
    )


@pytest.mark.parametrize("problem", ["cwd", "isolation"])
def test_postclaim_startup_failure_is_one_executor_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, problem: str
) -> None:
    service, task, _ = setup(tmp_path, monkeypatch)
    allow_engineering_path(monkeypatch)

    def changed_after_claim() -> bool:
        if problem == "cwd":
            (tmp_path / "cwd/private-context").write_text("PRIVATE CONTEXT SENTINEL")
        else:
            monkeypatch.setattr("paper_radar.pi_execution.isolation._RUNTIME_PATHS", ())
        return False

    result = service.run_attempt(task.task_id, cancelled=changed_after_claim)
    assert isinstance(result, ReadTask) and len(result.attempts) == 1
    assert result.attempts[0].failure == "executor_error"
    assert service.tasks.analyses(task.paper_id) == ()
    selected = activation_history(service.database)[-1]
    assert (
        probe_install(service.database, selected.supply_id, selected.install_id).state
        == "idle"
    )
