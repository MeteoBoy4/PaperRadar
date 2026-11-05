"""D1 Read租约、显式回收、唯一retry及并发所有权。"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from paper_radar.read_tasks import (
    ReadAnalysis,
    ReadHandle,
    ReadTask,
    ReadTaskError,
    ReadTasks,
)
from tests.a8_call_support import Archive
from tests.pi_rpc_source_support import NOW
from tests.read_tasks_support import ready, valid_candidate


def registered(root: Path) -> tuple[Archive, ReadTasks, ReadTask, list[datetime]]:
    data, _body, extraction = ready(root)
    time = [NOW]
    service = ReadTasks(data.database, data.data_root, clock=lambda: time[0])
    task = service.register(
        data.paper_id,
        snapshot_id=data.snapshot_id,
        extraction_fingerprint=extraction.fingerprint,
        request_id="read",
    )
    return data, service, task, time


def test_expiry_never_refunds_and_explicit_reclaim_spends_last_attempt(
    tmp_path: Path,
) -> None:
    data, service, task, time = registered(tmp_path)
    old = service.claim(task.task_id)
    time[0] += timedelta(seconds=600)
    assert service.task(task.task_id).status == "running"
    assert service.task(task.task_id).remaining_attempts == 1
    with pytest.raises(ReadTaskError, match="task_running"):
        service.claim(task.task_id)
    recovered = service.reclaim(task.task_id)
    assert recovered.attempts[0].failure == "outcome_unknown"
    with pytest.raises(ReadTaskError, match="settlement_conflict"):
        service.submit_test(old, valid_candidate())
    service.claim(task.task_id)
    time[0] += timedelta(seconds=600)
    assert service.reclaim(task.task_id).status == "failed"
    assert service.reclaim(task.task_id).remaining_attempts == 0
    restarted = ReadTasks(data.database, data.data_root, clock=lambda: time[0])
    with pytest.raises(ReadTaskError, match="budget_exhausted"):
        restarted.claim(task.task_id)


def test_renewal_preserves_ownership_and_forged_wrapper_ordinal_is_rejected(
    tmp_path: Path,
) -> None:
    _, service, task, time = registered(tmp_path)
    handle = service.claim(task.task_id)
    time[0] += timedelta(seconds=500)
    assert service.renew(handle) == NOW + timedelta(seconds=1100)
    time[0] += timedelta(seconds=200)
    assert service.reclaim(task.task_id).status == "running"
    with pytest.raises(ReadTaskError, match="invalid_credential"):
        service.submit_test(replace(handle, ordinal=2), valid_candidate())
    accepted = service.submit_test(handle, valid_candidate())
    assert isinstance(accepted, ReadAnalysis)
    assert accepted.attempt_ordinal == 1


def test_retry_only_failed_terminal_and_unique_successor_is_durable(
    tmp_path: Path,
) -> None:
    data, service, task, time = registered(tmp_path)
    with pytest.raises(ReadTaskError, match="not_failed"):
        service.retry(task.task_id, request_id="early", reason="request", actor="human")
    first = service.claim(task.task_id)
    with pytest.raises(ReadTaskError, match="not_failed"):
        service.retry(
            task.task_id, request_id="running", reason="request", actor="human"
        )
    service.fail(first, "timeout")
    service.fail(service.claim(task.task_id), "executor_error")
    child = service.retry(
        task.task_id, request_id="retry", reason="explicit reason", actor="human"
    )
    restarted = ReadTasks(data.database, data.data_root, clock=lambda: time[0])
    assert (
        restarted.retry(
            task.task_id, request_id="retry", reason="explicit reason", actor="human"
        ).task_id
        == child.task_id
    )
    assert (
        restarted.retry(
            task.task_id,
            request_id="another-retry",
            reason="same parent",
            actor="human",
        ).task_id
        == child.task_id
    )
    assert child.generation == 2 and child.remaining_attempts == 2
    assert service.claim(child.task_id).ordinal == 1
    assert len(service.history(data.paper_id)) == 2


def test_concurrent_claim_has_exactly_one_owner(tmp_path: Path) -> None:
    data, service, task, _ = registered(tmp_path)

    def claim() -> ReadHandle | str:
        try:
            return ReadTasks(data.database, data.data_root, clock=lambda: NOW).claim(
                task.task_id
            )
        except ReadTaskError as error:
            return error.reason

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: claim(), range(2)))
    assert results.count("task_running") == 1
    assert len(service.task(task.task_id).attempts) == 1


def test_success_cannot_retry_and_competing_candidate_cannot_overwrite(
    tmp_path: Path,
) -> None:
    _, service, task, _ = registered(tmp_path)
    handle = service.claim(task.task_id)
    result = service.submit_test(handle, valid_candidate())
    assert isinstance(result, ReadAnalysis)
    with pytest.raises(ReadTaskError, match="not_failed"):
        service.retry(
            task.task_id, request_id="retry-success", reason="another", actor="human"
        )
    with pytest.raises(ReadTaskError, match="settlement_conflict"):
        service.submit_test(handle, valid_candidate(next_action="不同的下一步。"))
    assert service.analysis(result.analysis_id).raw_candidate == valid_candidate()


def test_concurrent_exact_submission_returns_same_single_analysis(
    tmp_path: Path,
) -> None:
    data, service, task, _ = registered(tmp_path)
    handle = service.claim(task.task_id)

    def submit(_: int) -> str:
        result = ReadTasks(
            data.database, data.data_root, clock=lambda: NOW
        ).submit_test(handle, valid_candidate())
        assert isinstance(result, ReadAnalysis)
        return result.analysis_id

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(submit, range(2)))
    assert ids[0] == ids[1]
    assert len(service.analyses(data.paper_id)) == 1
