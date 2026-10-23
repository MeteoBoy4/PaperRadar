"""A7-03 真实进程竞争、精确到期与强杀窗口。"""

import json
import os
import sqlite3
import subprocess
import sys
from contextlib import AbstractContextManager, closing
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import pytest

from paper_radar.papers import PaperFacts
from paper_radar.screening_tasks import ScreeningTasks
from paper_radar.screening_tasks.attempt_models import Claim
from tests.a3_process_support import paused_subprocess
from tests.a7_registration_support import Archive, archive, request_for

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def save_claim(path: Path, claim: Claim) -> None:
    """测试私有能力交换文件;不进入普通stdout。"""
    payload = asdict(claim)
    payload["claimed_at"] = claim.claimed_at.isoformat()
    payload["expires_at"] = claim.expires_at.isoformat()
    path.write_text(json.dumps(payload), encoding="utf-8")
    path.chmod(0o600)


def worker_command(
    database: Path, receipt_id: str, operation: str, now: datetime, capability: Path
) -> list[str]:
    return [
        sys.executable,
        "-m",
        "tests.a7_attempts_worker",
        str(database),
        receipt_id,
        operation,
        now.isoformat(),
        str(capability),
    ]


def paused(
    data: Archive,
    receipt_id: str,
    operation: str,
    now: datetime,
    capability: Path,
    phase: str = "begin",
) -> AbstractContextManager[tuple[subprocess.Popen[str], int]]:
    return paused_subprocess(
        worker_command(data.database, receipt_id, operation, now, capability),
        Path(__file__).parent / "a7_attempts_process",
        {"A7_ATTEMPTS_PAUSE": phase},
        "尝试进程未到达屏障",
        "尝试进程提前退出",
    )


def result_of(process: subprocess.Popen[str]) -> dict[str, object]:
    stdout, stderr = process.communicate(timeout=20)
    assert process.returncode == 0, stderr
    return dict(json.loads(stdout))


def test_expired_unsettled_holder_can_renew_in_another_process(tmp_path: Path) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(data.database, clock=lambda: NOW)
    receipt = tasks.register(request_for(data))
    claim = tasks.claim(receipt.receipt_id)
    capability = tmp_path / "private-claim.json"
    save_claim(capability, claim)
    result = subprocess.run(
        worker_command(
            data.database, receipt.receipt_id, "renew", claim.expires_at, capability
        ),
        env={
            "PATH": os.environ["PATH"],
            "PYTHONPATH": str(Path(__file__).parent / "deny_network"),
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"expires_at": "2026-01-01T00:20:00+00:00"}
    assert claim.credential not in result.stdout + result.stderr
    assert claim.renewal_handle not in result.stdout + result.stderr


def test_two_processes_compete_for_one_persisted_attempt(tmp_path: Path) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(data.database, clock=lambda: NOW)
    receipt = tasks.register(request_for(data))
    with (
        paused(data, receipt.receipt_id, "claim", NOW, tmp_path / "one.json") as (
            one,
            release_one,
        ),
        paused(data, receipt.receipt_id, "claim", NOW, tmp_path / "two.json") as (
            two,
            release_two,
        ),
    ):
        os.write(release_one, b"G")
        os.write(release_two, b"G")
        results = [result_of(process) for process in (one, two)]
    assert sum(item.get("attempt_no") == 1 for item in results) == 1
    assert sum(item.get("reason") == "task_running" for item in results) == 1
    status = tasks.status(receipt.receipt_id)
    assert (status.state, status.used_attempts, status.remaining_attempts) == (
        "running",
        1,
        1,
    )
    tasks.validate_all()


@pytest.mark.parametrize("phase", ["begin", "middle", "committed"])
def test_killed_claim_before_or_after_commit_preserves_consumed_budget(
    tmp_path: Path,
    phase: str,
) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(data.database, clock=lambda: NOW)
    receipt = tasks.register(request_for(data))
    with paused(
        data, receipt.receipt_id, "claim", NOW, tmp_path / "private.json", phase
    ) as (process, _):
        process.kill()
        process.wait(timeout=15)
    status = tasks.status(receipt.receipt_id)
    expected = ("running", 1, 1) if phase == "committed" else ("ready", 0, 2)
    assert (status.state, status.used_attempts, status.remaining_attempts) == expected
    tasks.validate_all()


@pytest.mark.parametrize("renew_first", [True, False])
def test_exact_expiry_renew_and_reclaim_are_serialized_and_fence_late_holder(
    tmp_path: Path,
    renew_first: bool,
) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(data.database, clock=lambda: NOW)
    receipt = tasks.register(request_for(data))
    claim = tasks.claim(receipt.receipt_id)
    capability = tmp_path / "private-claim.json"
    save_claim(capability, claim)
    expired = ScreeningTasks(data.database, clock=lambda: claim.expires_at)
    assert expired.status(receipt.receipt_id).state == "lease_expired"
    with (
        paused(data, receipt.receipt_id, "renew", claim.expires_at, capability) as (
            renew,
            release_renew,
        ),
        paused(data, receipt.receipt_id, "reclaim", claim.expires_at, capability) as (
            reclaim,
            release_reclaim,
        ),
    ):
        first, release_first, second, release_second = (
            (renew, release_renew, reclaim, release_reclaim)
            if renew_first
            else (reclaim, release_reclaim, renew, release_renew)
        )
        os.write(release_first, b"G")
        first_result = result_of(first)
        os.write(release_second, b"G")
        second_result = result_of(second)
    if renew_first:
        assert first_result == {"expires_at": "2026-01-01T00:20:00+00:00"}
        assert second_result["state"] == "running"
        assert expired.status(receipt.receipt_id).state == "running"
    else:
        assert first_result["state"] == "retryable"
        assert first_result["last_failure"] == "outcome_unknown"
        assert second_result == {"reason": "invalid_credential"}
        successor = expired.claim(receipt.receipt_id)
        assert successor.attempt_no == 2
        late = subprocess.run(
            worker_command(
                data.database, receipt.receipt_id, "fail", claim.expires_at, capability
            ),
            env={
                "PATH": os.environ["PATH"],
                "PYTHONPATH": str(Path(__file__).parent / "deny_network"),
            },
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        assert late.returncode == 0, late.stderr
        assert json.loads(late.stdout) == {"reason": "invalid_credential"}
        assert expired.status(receipt.receipt_id).used_attempts == 2
    tasks.validate_all()


def test_killed_executor_is_recovered_as_unknown_without_refunding_attempt(
    tmp_path: Path,
) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(data.database, clock=lambda: NOW)
    receipt = tasks.register(request_for(data))
    marker = tmp_path / "executor-invocations.txt"
    with paused(data, receipt.receipt_id, "run_once", NOW, marker, "executor") as (
        process,
        _,
    ):
        assert marker.read_text(encoding="utf-8") == "called\n"
        assert tasks.status(receipt.receipt_id).used_attempts == 1
        process.kill()
        process.wait(timeout=15)
    expired = ScreeningTasks(
        data.database, clock=lambda: datetime(2026, 1, 1, 0, 10, tzinfo=UTC)
    )
    before = expired.status(receipt.receipt_id)
    assert (before.state, before.remaining_attempts) == ("lease_expired", 1)
    after = expired.reclaim(receipt.receipt_id)
    assert (after.state, after.last_failure) == ("retryable", "outcome_unknown")
    assert expired.claim(receipt.receipt_id).attempt_no == 2
    assert marker.read_text(encoding="utf-8") == "called\n"
    expired.validate_all()


def test_simultaneous_renew_and_reclaim_commit_one_consistent_outcome(
    tmp_path: Path,
) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(data.database, clock=lambda: NOW)
    receipt = tasks.register(request_for(data))
    claim = tasks.claim(receipt.receipt_id)
    capability = tmp_path / "private-claim.json"
    save_claim(capability, claim)
    with (
        paused(data, receipt.receipt_id, "renew", claim.expires_at, capability) as (
            renew,
            release_renew,
        ),
        paused(data, receipt.receipt_id, "reclaim", claim.expires_at, capability) as (
            reclaim,
            release_reclaim,
        ),
    ):
        os.write(release_renew, b"G")
        os.write(release_reclaim, b"G")
        renewed = result_of(renew)
        reclaimed = result_of(reclaim)
    current = ScreeningTasks(data.database, clock=lambda: claim.expires_at)
    if "expires_at" in renewed:
        assert renewed == {"expires_at": "2026-01-01T00:20:00+00:00"}
        assert reclaimed["state"] == "running"
        assert current.status(receipt.receipt_id).state == "running"
    else:
        assert renewed == {"reason": "invalid_credential"}
        assert reclaimed["state"] == "retryable"
        assert reclaimed["last_failure"] == "outcome_unknown"
        assert current.status(receipt.receipt_id).state == "retryable"
    current.validate_all()


def test_claim_cas_rejects_facts_changed_between_mapping_and_transaction(
    tmp_path: Path,
) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(data.database, clock=lambda: NOW)
    receipt = tasks.register(request_for(data))
    with paused(data, receipt.receipt_id, "claim", NOW, tmp_path / "private.json") as (
        process,
        release,
    ):
        corrected = PaperFacts(data.database, data.data_root).correct(
            {
                "version_id": data.version_id,
                "request_id": "claim-cas-correction",
                "actor": "researcher",
                "reason": "并发补全",
                "fields": {"volume": {"value": "42", "locator": "volume"}},
            }
        )
        assert corrected.status == "retained"
        os.write(release, b"G")
        assert result_of(process) == {"reason": "facts_changed"}
    assert tasks.status(receipt.receipt_id).used_attempts == 0
    fresh = tasks.claim(receipt.receipt_id)
    assert fresh.revision_no == 2
    tasks.validate_all()


def test_claim_busy_is_bounded_without_consuming_attempt(tmp_path: Path) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(data.database, clock=lambda: NOW)
    receipt = tasks.register(request_for(data))
    with (
        paused(data, receipt.receipt_id, "claim", NOW, tmp_path / "private.json") as (
            process,
            release,
        ),
        closing(sqlite3.connect(data.database)) as owner,
    ):
        owner.execute("BEGIN IMMEDIATE")
        os.write(release, b"G")
        assert result_of(process) == {"reason": "database_busy"}
        owner.rollback()
    assert tasks.status(receipt.receipt_id).used_attempts == 0
    assert tasks.claim(receipt.receipt_id).attempt_no == 1
    tasks.validate_all()
