"""A7-04 成功与回收竞争及完整发布/业务提交/丢回包的进程中断。"""

import json
import os
import subprocess
import sys
from contextlib import AbstractContextManager
from datetime import datetime
from pathlib import Path

import pytest

from paper_radar.screening_tasks import ScreeningTasks, SuccessCandidate, SuccessReceipt
from paper_radar.storage.artifacts import ArtifactStore
from tests.a3_process_support import paused_subprocess
from tests.a7_registration_support import Archive, archive, request_for
from tests.a7_success_worker import RAW_ONE, RAW_TWO
from tests.test_a7_attempts_process import NOW, result_of, save_claim


def command(
    data: Archive,
    receipt_id: str,
    operation: str,
    instant: datetime,
    capability: Path,
    variant: str = "one",
) -> list[str]:
    return [
        sys.executable,
        "-m",
        "tests.a7_success_worker",
        str(data.database),
        str(data.data_root),
        receipt_id,
        operation,
        instant.isoformat(),
        str(capability),
        variant,
    ]


def paused(
    data: Archive,
    receipt_id: str,
    operation: str,
    instant: datetime,
    capability: Path,
    phase: str,
    variant: str = "one",
) -> AbstractContextManager[tuple[subprocess.Popen[str], int]]:
    return paused_subprocess(
        command(data, receipt_id, operation, instant, capability, variant),
        Path(__file__).parent / "a7_success_process",
        {"A7_SUCCESS_PAUSE": phase},
        "成功进程未到达屏障",
        "成功进程提前退出",
    )


def success_artifacts(data: Archive) -> tuple[str, ...]:
    return tuple(
        item.artifact_id
        for item in ArtifactStore(data.database, data.data_root).list_artifacts()
        if item.kind == "model_success_response"
    )


@pytest.mark.parametrize("phase", ["published", "middle", "committed"])
def test_killed_success_preserves_atomic_outcome_and_exact_commit_replay(
    tmp_path: Path, phase: str
) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    registered = tasks.register(request_for(data))
    claim = tasks.claim(registered.receipt_id)
    capability = tmp_path / "private-claim.json"
    save_claim(capability, claim)
    with paused(data, registered.receipt_id, "submit", NOW, capability, phase) as (
        process,
        _,
    ):
        assert len(success_artifacts(data)) == 1
        process.kill()
        process.wait(timeout=15)
    status = tasks.status(registered.receipt_id)
    assert (status.used_attempts, status.remaining_attempts) == (1, 1)
    expired = ScreeningTasks(
        data.database, data.data_root, clock=lambda: claim.expires_at
    )
    if phase == "committed":
        assert status.state == "succeeded"
        accepted = tasks.query_successes(
            paper_id=data.paper_id, stage="boundary", snapshot_id=data.snapshot_id
        )
        assert len(accepted) == 1
        replayed = tasks.submit(claim, SuccessCandidate(RAW_ONE))
        assert isinstance(replayed, SuccessReceipt)
        assert replayed == accepted[0].receipt
        assert expired.reclaim(registered.receipt_id).state == "succeeded"
        assert tasks.load_success(replayed.success_id).raw_response == RAW_ONE
    else:
        assert status.state == "running"
        assert (
            tasks.query_successes(
                paper_id=data.paper_id, stage="boundary", snapshot_id=data.snapshot_id
            )
            == ()
        )
        assert expired.reclaim(registered.receipt_id).last_failure == "outcome_unknown"
        before = success_artifacts(data)
        late = subprocess.run(
            command(
                data, registered.receipt_id, "submit", claim.expires_at, capability
            ),
            env={
                "PATH": os.environ["PATH"],
                "PYTHONPATH": str(Path(__file__).parent / "deny_network"),
            },
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        assert late.returncode == 0, late.stderr
        assert json.loads(late.stdout) == {"reason": "invalid_credential"}
        assert success_artifacts(data) == before
    assert len(success_artifacts(data)) == 1
    tasks.validate_all()


@pytest.mark.parametrize("success_first", [True, False])
def test_success_and_reclaim_compete_for_one_terminal_outcome(
    tmp_path: Path, success_first: bool
) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    registered = tasks.register(request_for(data))
    claim = tasks.claim(registered.receipt_id)
    capability = tmp_path / "private-claim.json"
    save_claim(capability, claim)
    with (
        paused(
            data,
            registered.receipt_id,
            "submit",
            claim.expires_at,
            capability,
            "business_begin",
        ) as (success, release_success),
        paused(
            data,
            registered.receipt_id,
            "reclaim",
            claim.expires_at,
            capability,
            "begin",
        ) as (reclaim, release_reclaim),
    ):
        first, release_first, second, release_second = (
            (success, release_success, reclaim, release_reclaim)
            if success_first
            else (reclaim, release_reclaim, success, release_success)
        )
        os.write(release_first, b"G")
        first_result = result_of(first)
        os.write(release_second, b"G")
        second_result = result_of(second)
    current = ScreeningTasks(
        data.database, data.data_root, clock=lambda: claim.expires_at
    )
    if success_first:
        assert "success_id" in first_result
        assert second_result["state"] == "succeeded"
        assert current.status(registered.receipt_id).state == "succeeded"
        assert (
            len(
                tasks.query_successes(
                    paper_id=data.paper_id,
                    stage="boundary",
                    snapshot_id=data.snapshot_id,
                )
            )
            == 1
        )
    else:
        assert first_result["last_failure"] == "outcome_unknown"
        assert second_result == {"reason": "invalid_credential"}
        assert current.status(registered.receipt_id).state == "retryable"
        assert (
            tasks.query_successes(
                paper_id=data.paper_id, stage="boundary", snapshot_id=data.snapshot_id
            )
            == ()
        )
    assert len(success_artifacts(data)) == 1
    assert current.status(registered.receipt_id).used_attempts == 1
    tasks.validate_all()


@pytest.mark.parametrize("distinct", [True, False])
def test_simultaneous_candidates_accept_one_or_replay_identical_submission(
    tmp_path: Path,
    distinct: bool,
) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    registered = tasks.register(request_for(data))
    claim = tasks.claim(registered.receipt_id)
    capability = tmp_path / "private-claim.json"
    save_claim(capability, claim)
    with (
        paused(
            data,
            registered.receipt_id,
            "submit",
            NOW,
            capability,
            "business_begin",
            "one",
        ) as (one, release_one),
        paused(
            data,
            registered.receipt_id,
            "submit",
            NOW,
            capability,
            "business_begin",
            "two" if distinct else "one",
        ) as (two, release_two),
    ):
        os.write(release_one, b"G")
        os.write(release_two, b"G")
        results = [result_of(process) for process in (one, two)]
    if distinct:
        assert sum("success_id" in result for result in results) == 1
        assert (
            sum(result.get("reason") == "settlement_conflict" for result in results)
            == 1
        )
    else:
        assert "success_id" in results[0]
        assert results[0] == results[1]
    accepted = tasks.query_successes(
        paper_id=data.paper_id, stage="boundary", snapshot_id=data.snapshot_id
    )
    assert len(accepted) == 1
    winner = next(
        index for index, result in enumerate(results) if "success_id" in result
    )
    assert (
        tasks.load_success(accepted[0].receipt.success_id).raw_response
        == (RAW_ONE, RAW_TWO)[winner]
    )
    assert len(success_artifacts(data)) == (2 if distinct else 1)
    assert tasks.status(registered.receipt_id).used_attempts == 1
    tasks.validate_all()


def test_reclaimed_credential_is_rejected_before_any_file_publication(
    tmp_path: Path,
) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    registered = tasks.register(request_for(data))
    claim = tasks.claim(registered.receipt_id)
    capability = tmp_path / "private-claim.json"
    save_claim(capability, claim)
    expired = ScreeningTasks(
        data.database, data.data_root, clock=lambda: claim.expires_at
    )
    assert expired.reclaim(registered.receipt_id).last_failure == "outcome_unknown"
    assert success_artifacts(data) == ()
    before_files = tuple(data.data_root.rglob("*"))
    late = subprocess.run(
        command(
            data, registered.receipt_id, "submit", claim.expires_at, capability, "two"
        ),
        env={
            "PATH": os.environ["PATH"],
            "PYTHONPATH": str(Path(__file__).parent / "deny_network"),
        },
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert late.returncode == 0, late.stderr
    assert json.loads(late.stdout) == {"reason": "invalid_credential"}
    assert claim.credential not in late.stdout + late.stderr
    assert claim.renewal_handle not in late.stdout + late.stderr
    assert success_artifacts(data) == ()
    assert tuple(data.data_root.rglob("*")) == before_files
    assert (
        tasks.query_successes(
            paper_id=data.paper_id, stage="boundary", snapshot_id=data.snapshot_id
        )
        == ()
    )
    tasks.validate_all()


def test_simultaneous_success_and_reclaim_have_exactly_one_terminal_fact(
    tmp_path: Path,
) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    registered = tasks.register(request_for(data))
    claim = tasks.claim(registered.receipt_id)
    capability = tmp_path / "private-claim.json"
    save_claim(capability, claim)
    with (
        paused(
            data,
            registered.receipt_id,
            "submit",
            claim.expires_at,
            capability,
            "business_begin",
        ) as (success, release_success),
        paused(
            data,
            registered.receipt_id,
            "reclaim",
            claim.expires_at,
            capability,
            "begin",
        ) as (reclaim, release_reclaim),
    ):
        os.write(release_success, b"G")
        os.write(release_reclaim, b"G")
        succeeded = result_of(success)
        reclaimed = result_of(reclaim)
    current = ScreeningTasks(
        data.database, data.data_root, clock=lambda: claim.expires_at
    )
    if "success_id" in succeeded:
        assert reclaimed["state"] == "succeeded"
        assert current.status(registered.receipt_id).state == "succeeded"
        assert (
            len(
                tasks.query_successes(
                    paper_id=data.paper_id,
                    stage="boundary",
                    snapshot_id=data.snapshot_id,
                )
            )
            == 1
        )
    else:
        assert succeeded == {"reason": "invalid_credential"}
        assert reclaimed["last_failure"] == "outcome_unknown"
        assert current.status(registered.receipt_id).state == "retryable"
        assert (
            tasks.query_successes(
                paper_id=data.paper_id, stage="boundary", snapshot_id=data.snapshot_id
            )
            == ()
        )
    assert len(success_artifacts(data)) == 1
    assert current.status(registered.receipt_id).used_attempts == 1
    tasks.validate_all()
