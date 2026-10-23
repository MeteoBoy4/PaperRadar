"""真实双进程唯一后继、精确重放、提交丢回包及终局竞争。"""

import json
import os
import sys
from datetime import timedelta
from pathlib import Path

import pytest

from paper_radar.screening_tasks import FailureKind, FailureReport, ScreeningTasks
from tests.a3_process_support import paused_subprocess
from tests.a7_registration_support import archive, request_for
from tests.a7_retry_support import exhaust, retry_for
from tests.test_a7_attempts_process import NOW, result_of, save_claim
from tests.test_a7_success_process import paused as paused_success


def save_request(path, request):
    path.write_text(json.dumps(request), encoding="utf-8")
    path.chmod(0o600)
    return path


def paused(data, receipt, instant, request_path, phase="begin", operation="retry"):
    return paused_subprocess(
        [
            sys.executable,
            "-m",
            "tests.a7_retry_worker",
            str(data.database),
            str(data.data_root),
            receipt.receipt_id,
            operation,
            instant.isoformat(),
            str(request_path),
        ],
        Path(__file__).parent / "a7_retry_process",
        {"A7_RETRY_PAUSE": phase},
        "retry进程未到达屏障",
        "retry进程提前退出",
    )


@pytest.mark.parametrize("identity", ["same", "different", "conflict"])
def test_two_processes_create_exactly_one_successor(
    tmp_path: Path, identity: str
) -> None:
    data = archive(tmp_path)
    service = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    initial = service.register(request_for(data))
    exhaust(service, initial)
    request = retry_for(data, initial)
    other = (
        request
        if identity == "same"
        else {
            **request,
            **(
                {"request_id": "other"}
                if identity == "different"
                else {"reason": "冲突理由"}
            ),
        }
    )
    one_path = save_request(tmp_path / "one.json", request)
    two_path = save_request(tmp_path / "two.json", other)
    with (
        paused(data, initial, NOW, one_path) as (one, release_one),
        paused(data, initial, NOW, two_path) as (two, release_two),
    ):
        os.write(release_one, b"G")
        os.write(release_two, b"G")
        results = [result_of(one), result_of(two)]
    result = service.query(
        paper_id=data.paper_id, stage="boundary", snapshot_id=data.snapshot_id
    )
    assert len(result.budgets[0].tasks) == 2
    successor = result.budgets[0].tasks[-1]
    if identity == "same":
        assert results[0] == results[1]
    else:
        assert sum(item.get("task_id") == successor.task_id for item in results) == 1
        rejected = next(item for item in results if "reason" in item)
        assert rejected["reason"] == (
            "already_retried" if identity == "different" else "request_conflict"
        )
        if identity == "different":
            assert rejected["successor_task_id"] == successor.task_id
    service.validate_all()


@pytest.mark.parametrize("phase", ["begin", "middle", "committed"])
def test_killed_retry_rolls_back_or_replays_exact_committed_receipt(
    tmp_path: Path, phase: str
) -> None:
    data = archive(tmp_path)
    now = NOW
    service = ScreeningTasks(data.database, data.data_root, clock=lambda: now)
    initial = service.register(request_for(data))
    service.fail(service.claim(initial.receipt_id), FailureReport(FailureKind.TIMEOUT))
    service.claim(initial.receipt_id)
    now += timedelta(seconds=600)
    request = retry_for(data, initial)
    path = save_request(tmp_path / "request.json", request)
    with paused(data, initial, now, path, phase) as (process, _):
        process.kill()
        process.wait(timeout=15)
    before = service.query(
        paper_id=data.paper_id, stage="boundary", snapshot_id=data.snapshot_id
    )
    assert len(before.budgets[0].tasks) == (2 if phase == "committed" else 1)
    assert before.budgets[0].tasks[0].state == (
        "failed" if phase == "committed" else "lease_expired"
    )
    receipt = service.retry(request)
    assert receipt.generation == 1
    assert service.retry(request) == receipt
    assert len(service.receipts(data.paper_id)) == 2
    service.validate_all()


@pytest.mark.parametrize("operation", ["reclaim", "success"])
@pytest.mark.parametrize("order", ["retry_first", "other_first", "simultaneous"])
def test_retry_and_reclaim_or_success_have_one_consistent_terminal_outcome(
    tmp_path: Path, operation: str, order: str
) -> None:
    data = archive(tmp_path)
    now = NOW
    service = ScreeningTasks(data.database, data.data_root, clock=lambda: now)
    initial = service.register(request_for(data))
    service.fail(service.claim(initial.receipt_id), FailureReport(FailureKind.TIMEOUT))
    claim = service.claim(initial.receipt_id)
    capability = tmp_path / "claim.json"
    save_claim(capability, claim)
    now = claim.expires_at
    path = save_request(tmp_path / "request.json", retry_for(data, initial))
    other_context = (
        paused_success(
            data, initial.receipt_id, "submit", now, capability, "business_begin"
        )
        if operation == "success"
        else paused(data, initial, now, path, operation="reclaim")
    )
    with (
        paused(data, initial, now, path) as (retry, release_retry),
        other_context as (other, release_other),
    ):
        if order == "simultaneous":
            os.write(release_retry, b"G")
            os.write(release_other, b"G")
            retry_result, other_result = result_of(retry), result_of(other)
        elif order == "retry_first":
            os.write(release_retry, b"G")
            retry_result = result_of(retry)
            os.write(release_other, b"G")
            other_result = result_of(other)
        else:
            os.write(release_other, b"G")
            other_result = result_of(other)
            os.write(release_retry, b"G")
            retry_result = result_of(retry)
    view = service.query(
        paper_id=data.paper_id, stage="boundary", snapshot_id=data.snapshot_id
    )
    if "success_id" in other_result:
        assert retry_result["reason"] == "already_succeeded"
        assert len(view.budgets[0].tasks) == 1
        assert view.budgets[0].tasks[0].state == "succeeded"
    else:
        assert retry_result["generation"] == 1
        assert len(view.budgets[0].tasks) == 2
        assert view.budgets[0].tasks[0].state == "failed"
        assert view.budgets[0].tasks[0].attempts[-1].failure.kind == "outcome_unknown"
        if operation == "success":
            assert other_result["reason"] == "invalid_credential"
        else:
            assert other_result["state"] == "failed"
    service.validate_all()
