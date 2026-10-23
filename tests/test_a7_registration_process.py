"""真实双进程、确定屏障、忙锁及提交中断。"""

import json
import os
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

import pytest

from paper_radar.papers import PaperFacts
from paper_radar.screening_tasks import ScreeningTasks
from tests.a3_process_support import paused_subprocess
from tests.a7_registration_support import Archive, archive, request_for


def paused(data: Archive, phase: str, raw: dict[str, object]):  # type: ignore[no-untyped-def]
    return paused_subprocess(
        [
            sys.executable,
            "-m",
            "tests.a7_registration_worker",
            str(data.database),
            json.dumps(raw),
        ],
        Path(__file__).parent / "a7_registration_process",
        {"A7_REGISTRATION_PAUSE": phase},
        "任务登记进程未到达屏障",
        "任务登记进程提前退出",
    )


@pytest.mark.parametrize("different_requests", [False, True])
def test_two_processes_register_one_budget_and_task(
    tmp_path: Path, different_requests: bool
) -> None:
    data = archive(tmp_path)
    request = request_for(data)
    other = (
        request_for(data, scheduled_day="2026-01-02") if different_requests else request
    )
    with (
        paused(data, "begin", request) as (one, release_one),
        paused(data, "begin", other) as (two, release_two),
    ):
        os.write(release_one, b"G")
        os.write(release_two, b"G")
        outputs = [process.communicate(timeout=20) for process in (one, two)]
        assert one.returncode == two.returncode == 0, outputs
    receipts = [json.loads(output[0]) for output in outputs]
    assert receipts[0]["task_id"] == receipts[1]["task_id"]
    assert (receipts[0] == receipts[1]) is not different_requests
    service = ScreeningTasks(data.database)
    service.validate_all()
    assert len(service.receipts(data.paper_id)) == (2 if different_requests else 1)


@pytest.mark.parametrize("phase", ["begin", "middle", "committed"])
def test_kill_registration_transaction_or_reply_preserves_exact_replay(
    tmp_path: Path, phase: str
) -> None:
    data = archive(tmp_path)
    request = request_for(
        data,
        source="manual",
        scheduled_day=None,
        request_id="crashed-request",
        actor="researcher",
        reason="进程登记",
    )
    with paused(data, phase, request) as (process, _):
        process.kill()
        process.wait(timeout=15)
    tasks = ScreeningTasks(data.database)
    tasks.validate_all()
    before = tasks.receipts(data.paper_id)
    assert len(before) == (1 if phase == "committed" else 0)
    receipt = tasks.register(request)
    if before:
        assert receipt == before[0]
    assert tasks.register(request) == receipt
    assert tasks.receipts(data.paper_id) == (receipt,)
    tasks.validate_all()


def test_pre_read_cas_rejects_concurrent_paper_revision_without_half_registration(
    tmp_path: Path,
) -> None:
    data = archive(tmp_path)
    with paused(data, "begin", request_for(data)) as (process, release):
        corrected = PaperFacts(data.database, data.data_root).correct(
            {
                "version_id": data.version_id,
                "request_id": "concurrent-correction",
                "actor": "researcher",
                "reason": "并发补全",
                "fields": {"volume": {"value": "42", "locator": "volume"}},
            }
        )
        assert corrected.status == "retained"
        os.write(release, b"G")
        stdout, stderr = process.communicate(timeout=15)
        assert process.returncode == 0, stderr
        assert json.loads(stdout) == {"reason": "facts_changed"}
    tasks = ScreeningTasks(data.database)
    assert tasks.receipts(data.paper_id) == ()
    tasks.validate_all()
    assert tasks.register(request_for(data)).revision_no == 2


def test_busy_is_bounded_and_retry_does_not_create_half_registration(
    tmp_path: Path,
) -> None:
    data = archive(tmp_path)
    with (
        paused(data, "begin", request_for(data)) as (process, release),
        closing(sqlite3.connect(data.database)) as owner,
    ):
        owner.execute("BEGIN IMMEDIATE")
        os.write(release, b"G")
        stdout, stderr = process.communicate(timeout=15)
        assert process.returncode == 0, stderr
        assert json.loads(stdout) == {"reason": "database_busy"}
        owner.rollback()
    tasks = ScreeningTasks(data.database)
    assert tasks.receipts(data.paper_id) == ()
    receipt = tasks.register(request_for(data))
    assert tasks.receipts(data.paper_id) == (receipt,)
    tasks.validate_all()
