"""Screening 公共服务保持预算/回执语义并产生安全诊断。"""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from paper_radar.runtime_logging import FileSink
from paper_radar.screening_tasks import FailureKind, FailureReport, ScreeningTasks
from paper_radar.stage_inputs import StageInput
from tests.a7_registration_support import archive, request_for


def read_events(root: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in (root / "logs/runtime.jsonl").read_text().splitlines()
    ]


def test_executor_exception_remains_controlled_failure_and_is_not_logged(
    tmp_path: Path,
) -> None:
    data = archive(tmp_path)
    service = ScreeningTasks(
        data.database,
        data.data_root,
        clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        sink=FileSink(data.data_root),
        monotonic=lambda: 5.0,
    )
    receipt = service.register(request_for(data))

    def executor(
        stage_input: StageInput, correction: str | None, handle: str
    ) -> FailureReport:
        raise RuntimeError("PRIVATE_MODEL_OUTPUT_AND_TOKEN")

    result = service.run_once(receipt.receipt_id, executor)
    assert (result.kind, result.origin) == (FailureKind.EXECUTOR_ERROR, "exception")
    events = read_events(data.data_root)
    assert [event["event"] for event in events] == [
        "claimed",
        "unexpected_error",
        "failed",
    ]
    assert {event["task_id"] for event in events} == {receipt.task_id}
    assert {event["paper_id"] for event in events} == {data.paper_id}
    assert {event["stage"] for event in events} == {"boundary"}
    assert {event["fingerprint"] for event in events} == {receipt.fingerprint[:16]}
    assert all(event["timestamp"] == "2026-01-01T00:00:00+00:00" for event in events)
    assert all(event["elapsed_ms"] == 0 for event in events)
    assert (
        "PRIVATE_MODEL_OUTPUT_AND_TOKEN"
        not in (data.data_root / "logs/runtime.jsonl").read_text()
    )
    assert service.status(receipt.receipt_id).used_attempts == 1


@pytest.mark.parametrize(
    "interruption", [KeyboardInterrupt("PRIVATE_INTERRUPT"), SystemExit(17)]
)
def test_interrupt_is_rethrown_unchanged_and_does_not_refund_or_settle(
    tmp_path: Path,
    interruption: BaseException,
) -> None:
    data = archive(tmp_path)
    service = ScreeningTasks(
        data.database,
        data.data_root,
        clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        sink=FileSink(data.data_root),
    )
    receipt = service.register(request_for(data))

    def executor(
        stage_input: StageInput, correction: str | None, handle: str
    ) -> FailureReport:
        raise interruption

    with pytest.raises(type(interruption)) as raised:
        service.run_once(receipt.receipt_id, executor)
    assert raised.value is interruption
    status = service.status(receipt.receipt_id)
    assert (
        status.state,
        status.used_attempts,
        status.remaining_attempts,
        status.last_failure,
    ) == ("running", 1, 1, None)
    events = read_events(data.data_root)
    assert [event["event"] for event in events] == ["claimed", "interrupted"]
    assert events[-1]["category"] == "outcome_unknown"
    assert events[-1]["attempt"] == 1


def test_succeeded_is_observable_from_a_new_connection_before_event(
    tmp_path: Path,
) -> None:
    from collections.abc import Mapping

    from paper_radar.screening_tasks import SuccessCandidate, SuccessReceipt

    data = archive(tmp_path)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    observed = []

    class Observer:
        def emit(self, event: Mapping[str, object]) -> None:
            if event["event"] == "succeeded":
                reader = ScreeningTasks(
                    data.database, data.data_root, clock=lambda: now
                )
                observed.append(reader.status(receipt.receipt_id).state)
            FileSink(data.data_root).emit(event)

    service = ScreeningTasks(
        data.database, data.data_root, clock=lambda: now, sink=Observer()
    )
    receipt = service.register(request_for(data))
    raw = b' {"boundary":"in_scope","reason_zh":"Synthetic atmospheric research."}\n'
    result = service.run_once(receipt.receipt_id, lambda *_: SuccessCandidate(raw))
    assert isinstance(result, SuccessReceipt)
    assert observed == ["succeeded"]
    assert service.load_success(result.success_id).raw_response == raw
    assert [event["event"] for event in read_events(data.data_root)] == [
        "claimed",
        "succeeded",
    ]


def test_commit_failure_cannot_emit_succeeded(tmp_path: Path) -> None:
    import sqlite3

    from paper_radar.screening_tasks import SuccessCandidate, TaskError, TaskReason

    data = archive(tmp_path)
    service = ScreeningTasks(
        data.database,
        data.data_root,
        clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        sink=FileSink(data.data_root),
    )
    receipt = service.register(request_for(data))
    claim = service.claim(receipt.receipt_id)
    # SQLite 故障通过独立连接安装,不替换服务/事务内部方法。
    with sqlite3.connect(data.database) as connection:
        connection.execute(
            "CREATE TRIGGER reject_success BEFORE INSERT ON screening_successes "
            "BEGIN SELECT RAISE(ABORT, 'private_commit_failure'); END"
        )
    with pytest.raises(TaskError) as rejected:
        service.submit(
            claim,
            SuccessCandidate(
                b'{"boundary":"in_scope","reason_zh":"Atmosphere research."}'
            ),
        )
    assert rejected.value.reason == TaskReason.CORRUPT_REFERENCE
    assert service.status(receipt.receipt_id).state == "running"
    events = read_events(data.data_root)
    assert [value["event"] for value in events] == ["claimed", "submit_rejected"]
    assert events[-1]["reason"] == "corrupt_reference"


@pytest.mark.parametrize("implicit", [False, True])
def test_reclaim_is_logged_after_settlement_even_when_next_budget_is_exhausted(
    tmp_path: Path, implicit: bool
) -> None:
    from paper_radar.screening_tasks import TaskError, TaskReason

    data = archive(tmp_path)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    service = ScreeningTasks(
        data.database, data.data_root, clock=lambda: now, sink=FileSink(data.data_root)
    )
    receipt = service.register(request_for(data))
    first = service.claim(receipt.receipt_id)
    now = first.expires_at
    if not implicit:
        assert (
            service.reclaim(receipt.receipt_id).last_failure
            == FailureKind.OUTCOME_UNKNOWN
        )
    second = service.claim(receipt.receipt_id)
    now = second.expires_at
    with pytest.raises(TaskError) as exhausted:
        service.claim(receipt.receipt_id)
    assert exhausted.value.reason == TaskReason.BUDGET_EXHAUSTED
    events = read_events(data.data_root)
    assert [value["event"] for value in events] == [
        "claimed",
        "reclaimed",
        "claimed",
        "reclaimed",
    ]
    assert [value["attempt"] for value in events if value["event"] == "reclaimed"] == [
        1,
        2,
    ]
    assert service.status(receipt.receipt_id).remaining_attempts == 0


def test_direct_submit_interrupt_preserves_running_attempt_and_never_succeeds(
    tmp_path: Path,
) -> None:
    from typing import Any

    from sqlalchemy import Engine, event

    from paper_radar.screening_tasks import SuccessCandidate

    data = archive(tmp_path)
    service = ScreeningTasks(
        data.database,
        data.data_root,
        clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        sink=FileSink(data.data_root),
    )
    receipt = service.register(request_for(data))
    claim = service.claim(receipt.receipt_id)
    interruption = KeyboardInterrupt("PRIVATE_SUBMIT_INTERRUPT")

    def interrupt(
        connection: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        if statement.startswith("INSERT INTO screening_successes"):
            raise interruption

    event.listen(Engine, "before_cursor_execute", interrupt)
    try:
        with pytest.raises(KeyboardInterrupt) as raised:
            service.submit(
                claim,
                SuccessCandidate(
                    b'{"boundary":"in_scope","reason_zh":"Atmospheric measurements."}'
                ),
            )
        assert raised.value is interruption
    finally:
        event.remove(Engine, "before_cursor_execute", interrupt)
    assert service.status(receipt.receipt_id).state == "running"
    assert [value["event"] for value in read_events(data.data_root)] == [
        "claimed",
        "interrupted",
    ]


@pytest.mark.parametrize("mode", ["symlink", "too_small", "sink_error"])
def test_logging_failure_preserves_exact_success_receipt_and_artifact(
    tmp_path: Path,
    mode: str,
    capfd: pytest.CaptureFixture[str],
) -> None:
    from collections.abc import Mapping

    from paper_radar.screening_tasks import SuccessCandidate, SuccessReceipt

    data = archive(tmp_path)
    target = tmp_path / "target"
    target.mkdir()
    if mode == "symlink":
        (data.data_root / "logs").symlink_to(target, target_is_directory=True)

    class BrokenSink:
        def emit(self, event: Mapping[str, object]) -> None:
            raise OSError("SENTINEL_PRIVATE_LOG_PATH")

    sink = (
        BrokenSink()
        if mode == "sink_error"
        else FileSink(
            data.data_root, max_bytes=1 if mode == "too_small" else 1024 * 1024
        )
    )
    now = datetime(2026, 1, 1, tzinfo=UTC)
    service = ScreeningTasks(
        data.database, data.data_root, clock=lambda: now, sink=sink
    )
    receipt = service.register(request_for(data))
    claim = service.claim(receipt.receipt_id)
    raw = b' {"boundary":"in_scope","reason_zh":"Original private success."}\n'
    candidate = SuccessCandidate(raw)
    result = service.submit(claim, candidate)
    assert isinstance(result, SuccessReceipt)
    baseline = ScreeningTasks(data.database, data.data_root, clock=lambda: now)
    assert baseline.submit(claim, candidate) == result
    assert baseline.load_success(result.success_id).raw_response == raw
    assert list(target.iterdir()) == []
    out, err = capfd.readouterr()
    assert out == ""
    assert err in {"", "运行日志写入失败，业务继续。\n"}


def test_all_private_failure_material_stays_out_of_three_outputs(
    tmp_path: Path,
    capfd: pytest.CaptureFixture[str],
) -> None:
    data = archive(tmp_path)
    sentinels = [
        f"SENTINEL_{name}"
        for name in (
            "API_KEY",
            "COOKIE",
            "AUTHORIZATION",
            "TDM",
            "INSTITUTION",
            "SESSION",
            "PROFILE",
            "PROMPT",
            "ABSTRACT",
            "BODY",
            "EXCERPT",
            "MODEL_RESPONSE",
            "TEMP_URL",
            "RPC_REQUEST",
            "RPC_RESPONSE",
            "JSONL",
            "STDERR",
            "TOOL_ERROR",
            "CONTACT_EMAIL",
            "PROXY",
            "ABSOLUTE_PATH",
            "USERNAME",
            "HOSTNAME",
            "ENV_VALUE",
        )
    ]
    handles: list[str] = []
    service = ScreeningTasks(
        data.database,
        data.data_root,
        clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        sink=FileSink(data.data_root),
    )
    receipt = service.register(request_for(data))

    def executor(
        stage_input: StageInput, correction: str | None, handle: str
    ) -> FailureReport:
        handles.append(handle)
        raise RuntimeError(" ".join(sentinels))

    assert (
        service.run_once(receipt.receipt_id, executor).kind
        == FailureKind.EXECUTOR_ERROR
    )
    claim = service.claim(receipt.receipt_id)
    service.renew(claim.renewal_handle)
    service.fail(claim, FailureReport(FailureKind.TIMEOUT))
    out, err = capfd.readouterr()
    text = (data.data_root / "logs/runtime.jsonl").read_text() + out + err
    assert not any(
        value in text
        for value in [*sentinels, *handles, claim.credential, claim.renewal_handle]
    )
    assert "renew" not in [event["event"] for event in read_events(data.data_root)]


@pytest.mark.parametrize("phase", ["before_commit", "after_commit"])
def test_process_exit_window_keeps_database_authoritative(
    tmp_path: Path, phase: str
) -> None:
    import subprocess
    import sys

    from paper_radar.screening_tasks import SuccessReceipt

    data = archive(tmp_path)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    baseline = ScreeningTasks(data.database, data.data_root, clock=lambda: now)
    receipt = baseline.register(request_for(data))
    code = """
import os, sys
from datetime import UTC, datetime
from pathlib import Path
from sqlalchemy import Engine, event
from paper_radar.runtime_logging import FileSink
from paper_radar.screening_tasks import ScreeningTasks, SuccessCandidate
class ExitSink:
    def emit(self, value):
        if value["event"] == "succeeded" and sys.argv[4] == "after_commit":
            os._exit(0)
        FileSink(Path(sys.argv[2])).emit(value)
@event.listens_for(Engine, "after_cursor_execute")
def stop(connection, cursor, statement, parameters, context, executemany):
    if (sys.argv[4] == "before_commit"
            and statement.startswith("INSERT INTO screening_successes")):
        os._exit(0)
tasks = ScreeningTasks(Path(sys.argv[1]), Path(sys.argv[2]),
    clock=lambda: datetime(2026,1,1,tzinfo=UTC), sink=ExitSink())
tasks.run_once(sys.argv[3], lambda *_: SuccessCandidate(
    b'{"boundary":"in_scope","reason_zh":"Atmospheric observations."}'))
"""
    child = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
            str(data.database),
            str(data.data_root),
            receipt.receipt_id,
            phase,
        ],
        capture_output=True,
        timeout=20,
    )
    assert (child.returncode, child.stdout, child.stderr) == (0, b"", b"")
    assert [value["event"] for value in read_events(data.data_root)] == ["claimed"]
    status = baseline.status(receipt.receipt_id)
    assert status.used_attempts == 1
    assert status.state == ("succeeded" if phase == "after_commit" else "running")
    successes = baseline.query_successes(
        paper_id=data.paper_id, stage="boundary", snapshot_id=data.snapshot_id
    )
    if phase == "after_commit":
        assert len(successes) == 1
        assert isinstance(successes[0].receipt, SuccessReceipt)
        assert (
            baseline.load_success(successes[0].receipt.success_id).raw_response
            == b'{"boundary":"in_scope","reason_zh":"Atmospheric observations."}'
        )
    else:
        assert successes == ()


def test_invalid_candidate_logs_only_failure_kind_and_keeps_payload_private(
    tmp_path: Path,
    capfd: pytest.CaptureFixture[str],
) -> None:
    from paper_radar.screening_tasks import FailureReceipt, SuccessCandidate

    data = archive(tmp_path)
    service = ScreeningTasks(
        data.database,
        data.data_root,
        clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        sink=FileSink(data.data_root),
    )
    receipt = service.register(request_for(data))
    result = service.run_once(
        receipt.receipt_id,
        lambda *_: SuccessCandidate(b"SENTINEL_RAW_FAILED_MODEL_RESPONSE"),
    )
    assert isinstance(result, FailureReceipt)
    assert result.kind == FailureKind.OUTPUT_INVALID
    logged = read_events(data.data_root)
    assert [value["event"] for value in logged] == ["claimed", "failed"]
    assert logged[-1]["kind"] == "output_invalid"
    assert logged[-1]["paper_id"] == data.paper_id and logged[-1]["stage"] == "boundary"
    out, err = capfd.readouterr()
    assert (
        "SENTINEL"
        not in (data.data_root / "logs/runtime.jsonl").read_text() + out + err
    )
    assert (
        service.query_successes(
            paper_id=data.paper_id, stage="boundary", snapshot_id=data.snapshot_id
        )
        == ()
    )
