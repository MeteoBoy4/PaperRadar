"""双轴审阅回归:资源交接中断与领取前实际请求。"""

import os
import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from paper_radar.llm import render_request
from paper_radar.llm.rpc import validate_request
from paper_radar.llm.rpc_pipes import PipeSession
from paper_radar.papers import PaperFacts
from paper_radar.pi_execution.service import PiExecution, prepare_call
from paper_radar.screening_tasks import FailureKind, FailureReport, TaskError
from paper_radar.stage_inputs import StageInput
from tests.pi_execution_service_support import allow_synthetic, service_inputs
from tests.test_paper_mapping import screening_fields
from tests.test_paper_service import observation


@pytest.mark.parametrize("interruption", [KeyboardInterrupt, SystemExit])
@pytest.mark.parametrize("cleanup_denied", [False, True])
def test_adoption_interruption_reaps_process_and_resources_but_keeps_lease(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    interruption: type[BaseException],
    cleanup_denied: bool,
    request: pytest.FixtureRequest,
) -> None:
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
    roots: list[Path] = []
    children: list[subprocess.Popen[bytes]] = []
    mkdtemp = tempfile.mkdtemp
    rmtree = shutil.rmtree

    def owned_directory(
        suffix: str | None = None,
        prefix: str | None = None,
        dir: str | Path | None = None,
    ) -> str:
        directory = mkdtemp(suffix=suffix, prefix=prefix, dir=dir)
        if prefix == "paper-radar-pi-":
            roots.append(Path(directory))
            request.addfinalizer(lambda: rmtree(directory, ignore_errors=True))
        return directory

    def controlled_cleanup(path: Any, *args: Any, **kwargs: Any) -> None:
        if cleanup_denied and Path(path) in roots:
            raise PermissionError("private-cleanup-sentinel")
        rmtree(path, *args, **kwargs)

    def interrupted_adoption(child: subprocess.Popen[bytes]) -> PipeSession:
        assert isinstance(child.args, tuple)
        if "auth" in child.args:
            return PipeSession(child)
        children.append(child)
        raise interruption

    monkeypatch.setattr(tempfile, "mkdtemp", owned_directory)
    monkeypatch.setattr(shutil, "rmtree", controlled_cleanup)
    monkeypatch.setattr(
        "paper_radar.pi_execution.process.PipeSession", interrupted_adoption
    )
    with pytest.raises(interruption):
        service.run_attempt(receipt.receipt_id)
    assert len(children) == 1
    child = children[0]
    assert child.poll() is not None
    with pytest.raises(ProcessLookupError):
        os.killpg(child.pid, 0)
    assert all(
        stream is not None and stream.closed
        for stream in (child.stdin, child.stdout, child.stderr)
    )
    assert len(roots) == 1
    assert roots[0].exists() == cleanup_denied
    assert (credentials / "auth.json").exists()
    assert service.tasks.status(receipt.receipt_id).state == "running"
    assert service.tasks.status(receipt.receipt_id).used_attempts == 1
    now += timedelta(seconds=601)
    recovered = service.tasks.reclaim(receipt.receipt_id)
    assert recovered.last_failure is not None
    assert recovered.last_failure.value == "outcome_unknown"
    assert recovered.used_attempts == 1


@pytest.mark.parametrize(
    "state", ["timeout", "expired", "timeout_during_auth", "expiry_during_auth"]
)
def test_correction_overflow_is_rejected_before_claim_without_task_effects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, state: str
) -> None:
    original, initial, credentials = service_inputs(tmp_path, monkeypatch)
    events: list[Mapping[str, object]] = []

    class Capture:
        def emit(self, event: Mapping[str, object]) -> None:
            events.append(event)

    now = datetime(2026, 1, 1, tzinfo=UTC)
    service = PiExecution(
        original.database,
        original.data_root,
        roots=original.roots,
        credentials_dir=credentials,
        auth_mode="chatgpt_subscription",
        sink=Capture(),
        clock=lambda: now,
    )
    paper = PaperFacts(service.database, service.data_root).submit(
        observation(
            doi="10.1234/correct",
            fields=screening_fields(abstract="a" * 260948),
        )
    )
    assert paper.paper_id is not None
    paper_id = paper.paper_id
    receipt = service.tasks.register(
        dict(
            paper_id=paper_id,
            snapshot_id=initial.snapshot_id,
            stage="boundary",
            source="scheduled",
            scheduled_day="2026-01-01",
        )
    )
    description = prepare_call(service.tasks, receipt.receipt_id)
    assert validate_request(render_request(description)) is None
    claim = service.tasks.claim(receipt.receipt_id)
    if state == "timeout":
        service.tasks.fail(claim, FailureReport(FailureKind.TIMEOUT))
    elif state == "expired":
        now += timedelta(seconds=601)
    before = service.tasks.query(
        paper_id=paper_id, stage="boundary", snapshot_id=receipt.snapshot_id
    )
    events.clear()
    allow_synthetic(monkeypatch)

    popen = subprocess.Popen
    auth_calls = 0

    def controlled_auth(*args: Any, **kwargs: Any) -> subprocess.Popen[bytes]:
        nonlocal now, before, auth_calls
        assert state.endswith("_during_auth"), "已知帧超限不应刷新认证"
        assert "auth" in args[0], "不得创建模型会话"
        auth_calls += 1
        child = popen(*args, **kwargs)
        if state == "timeout_during_auth":
            service.tasks.fail(claim, FailureReport(FailureKind.TIMEOUT))
        else:
            now += timedelta(seconds=601)
        before = service.tasks.query(
            paper_id=paper_id, stage="boundary", snapshot_id=receipt.snapshot_id
        )
        events.clear()
        return child

    monkeypatch.setattr(subprocess, "Popen", controlled_auth)
    with pytest.raises(TaskError, match="invalid_context"):
        service.run_attempt(receipt.receipt_id)
    assert (
        service.tasks.query(
            paper_id=paper_id, stage="boundary", snapshot_id=receipt.snapshot_id
        )
        == before
    )
    assert service.tasks.status(receipt.receipt_id).used_attempts == 1
    assert (
        service.tasks.query_successes(
            paper_id=paper_id, stage="boundary", snapshot_id=receipt.snapshot_id
        )
        == ()
    )
    assert events == []
    assert auth_calls == (1 if state.endswith("_during_auth") else 0)
    assert (credentials / "auth-observed.json").exists() == state.endswith(
        "_during_auth"
    )


@pytest.mark.parametrize("previous", ["timeout", "expired"])
def test_valid_preclaim_uses_same_authoritative_correction_as_executor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, previous: str
) -> None:
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
    first = service.tasks.claim(receipt.receipt_id)
    if previous == "timeout":
        service.tasks.fail(first, FailureReport(FailureKind.TIMEOUT))
        expected = "上次执行超时,请在受支持的执行时限内完成。"
    else:
        now += timedelta(seconds=601)
        expected = "上次执行结果未知,请重新完成本次冻结输入。"
    before = service.tasks.query(
        paper_id=receipt.paper_id, stage="boundary", snapshot_id=receipt.snapshot_id
    )
    assert service.tasks.prepare_correction(receipt.receipt_id) == expected
    assert (
        service.tasks.query(
            paper_id=receipt.paper_id, stage="boundary", snapshot_id=receipt.snapshot_id
        )
        == before
    )
    checked: list[str | None] = []

    def preclaim(correction: str | None) -> None:
        assert correction == expected
        checked.append(correction)

    def executor(
        stage_input: StageInput, correction: str | None, renewal: str
    ) -> FailureReport:
        assert checked == [expected]
        assert correction == expected
        return FailureReport(FailureKind.CANCELLED)

    result = service.tasks.run_once(receipt.receipt_id, executor, preclaim=preclaim)
    assert result.attempt_no == 2 and result.kind is FailureKind.CANCELLED
    assert service.tasks.status(receipt.receipt_id).used_attempts == 2
    service.tasks.validate_all()
