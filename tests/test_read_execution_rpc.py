"""D1独立进程/协议对端进入唯一Read v2权威;不证明真实准入。"""

from pathlib import Path

import pytest

from paper_radar.read_tasks import ReadAnalysis
from tests.read_execution_support import allow_engineering_path, setup


def test_engineering_peer_saves_pi_audit_and_replays(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, task, credentials = setup(tmp_path, monkeypatch)
    allow_engineering_path(monkeypatch)
    result = service.run_attempt(task.task_id)
    assert isinstance(result, ReadAnalysis), getattr(result, "attempts", ())
    assert result.executor_kind == "pi_rpc" and result.attempt_ordinal == 1
    assert result.audit["audit_snapshot_id"] == task.snapshot_id
    assert (result.audit["input_tokens"], result.audit["output_tokens"]) == (5, 2)
    assert (credentials / "auth-observed.json").exists()
    assert service.tasks.analysis(result.analysis_id).audit == result.audit
    service.tasks.validate_all()
    assert not (service.data_root / "logs").exists()


def test_first_reject_then_last_correction_uses_two_distinct_processes_and_one_analysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess
    from typing import Any

    from paper_radar.read_tasks import ReadTask, ReadTaskError

    service, task, _ = setup(tmp_path, monkeypatch, mode="degrade")
    allow_engineering_path(monkeypatch)
    popen = subprocess.Popen
    sessions: list[tuple[int, str]] = []

    def spawn(*args: Any, **kwargs: Any) -> subprocess.Popen[bytes]:
        child = popen(*args, **kwargs)
        if "auth" not in args[0]:
            assert kwargs["start_new_session"] is True
            sessions.append((child.pid, kwargs["env"]["PI_CODING_AGENT_DIR"]))
        return child

    monkeypatch.setattr(subprocess, "Popen", spawn)
    first = service.run_attempt(task.task_id)
    assert (
        isinstance(first, ReadTask) and first.attempts[-1].failure == "output_invalid"
    )
    correction = service.tasks.prepare_correction(task.task_id)
    assert correction and "BAD PRIVATE ID" not in correction
    second = service.run_attempt(task.task_id)
    assert isinstance(second, ReadAnalysis) and second.attempt_ordinal == 2
    assert second.discards and len(second.output.main_findings) == 1
    assert len(service.tasks.analyses(task.paper_id)) == 1
    assert (
        len(sessions) == 2
        and sessions[0][0] != sessions[1][0]
        and sessions[0][1] != sessions[1][1]
    )
    assert all(not Path(directory).parent.exists() for _, directory in sessions)
    assert service.tasks.task(task.task_id).remaining_attempts == 0
    with pytest.raises(ReadTaskError, match="already_succeeded"):
        service.run_attempt(task.task_id)
    assert len(sessions) == 2
    service.tasks.validate_all()


@pytest.mark.parametrize(
    ("mode", "failure"),
    [
        ("timeout", "timeout"),
        ("orphan", "timeout"),
        ("environment", "executor_error"),
        ("protocol", "protocol_error"),
        ("cwd_mismatch", "protocol_error"),
        ("model_mismatch", "model_mismatch"),
        ("retry", "protocol_error"),
        ("compaction", "protocol_error"),
        ("extra_turn", "protocol_error"),
        ("duplicate_end", "protocol_error"),
        ("output_invalid", "output_invalid"),
    ],
)
def test_each_runtime_failure_spends_one_attempt_and_never_creates_analysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, failure: str
) -> None:
    from paper_radar.llm.rpc_types import RpcLimits
    from paper_radar.pi_supply import activation_history, probe_install
    from paper_radar.read_tasks import ReadTask

    service, task, _ = setup(tmp_path, monkeypatch, mode=mode)
    allow_engineering_path(monkeypatch)
    result = service.run_attempt(
        task.task_id,
        limits=RpcLimits(total=0.7, initialization=0.5, close=0.2, terminate=1),
    )
    assert isinstance(result, ReadTask)
    assert len(result.attempts) == 1 and result.attempts[-1].failure == failure
    assert service.tasks.analyses(task.paper_id) == ()
    install = activation_history(service.database)[-1]
    assert (
        probe_install(service.database, install.supply_id, install.install_id).state
        == "idle"
    )
    service.tasks.validate_all()


def test_cancel_has_one_completion_and_no_implicit_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.read_tasks import ReadTask

    service, task, _ = setup(tmp_path, monkeypatch)
    allow_engineering_path(monkeypatch)
    result = service.run_attempt(task.task_id, cancelled=lambda: True)
    assert isinstance(result, ReadTask) and len(result.attempts) == 1
    assert result.attempts[-1].failure == "cancelled"
    assert result.remaining_attempts == 1
    assert service.tasks.analyses(task.paper_id) == ()
