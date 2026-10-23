"""版本化共享查询区分当前失败、剩余预算和到期未结算。"""

import json
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

from paper_radar.screening_tasks import FailureKind, FailureReport, ScreeningTasks
from tests.a7_registration_support import archive, request_for

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_query_is_safe_readonly_history_and_current_failure_set(tmp_path: Path) -> None:
    data = archive(tmp_path)
    now = NOW
    service = ScreeningTasks(data.database, data.data_root, clock=lambda: now)
    first = service.register(request_for(data))
    service.fail(service.claim(first.receipt_id), FailureReport(FailureKind.TIMEOUT))

    def query():
        return service.query(
            paper_id=data.paper_id, stage="boundary", snapshot_id=data.snapshot_id
        )

    result = query()
    assert result.format_version == 1
    assert result.kind == "task_query_result"
    assert result.current_failures == ()
    budget = result.budgets[0]
    assert budget.applicability == "current"
    assert budget.latest_generation == 0
    assert budget.tasks[0].state == "retryable"
    assert budget.tasks[0].remaining_attempts == 1
    claim = service.claim(first.receipt_id)
    now += timedelta(seconds=600)
    expired = query()
    assert expired.budgets[0].tasks[0].state == "lease_expired"
    assert expired.current_failures == ()
    assert service.status(first.receipt_id).state == "lease_expired"
    successor = service.retry(
        {
            "paper_id": data.paper_id,
            "stage": "boundary",
            "snapshot_id": data.snapshot_id,
            "parent_task_id": first.task_id,
            "request_id": "SECRET-REQUEST",
            "reason": "SECRET-REASON",
            "actor": "SECRET-ACTOR",
        }
    )
    updated = query()
    assert updated.current_failures == ()
    assert updated.budgets[0].latest_generation == 1
    assert updated.budgets[0].tasks[0].attempts[-1].failure.kind == "outcome_unknown"
    assert updated.budgets[0].tasks[1].task_id == successor.task_id
    serialized = json.dumps(asdict(updated), default=str)
    for forbidden in (
        "SECRET-",
        claim.credential,
        claim.renewal_handle,
        "payload",
        "original_title_is_zh",
        "credential_sha256",
    ):
        assert forbidden not in serialized
    for _ in range(2):
        service.fail(
            service.claim(successor.receipt_id), FailureReport(FailureKind.CANCELLED)
        )
    assert [task.task_id for task in query().current_failures] == [successor.task_id]
    service.validate_all()


def test_query_preserves_safe_a1_failure_paths_and_explicit_shape(
    tmp_path: Path,
) -> None:
    from sqlalchemy import Engine, event

    from paper_radar.screening_tasks import SuccessCandidate

    data = archive(tmp_path)
    service = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    receipt = service.register(request_for(data))
    for _ in range(2):
        service.submit(
            service.claim(receipt.receipt_id),
            SuccessCandidate(
                b'{"boundary":"in_scope","reason_zh":5,"PRIVATE_SENTINEL":true}'
            ),
        )
    statements = []

    def observe(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement.split()[0].upper())

    event.listen(Engine, "before_cursor_execute", observe)
    try:
        result = service.query(
            paper_id=data.paper_id, stage="boundary", snapshot_id=data.snapshot_id
        )
    finally:
        event.remove(Engine, "before_cursor_execute", observe)
    assert not {"INSERT", "UPDATE", "DELETE", "ALTER", "CREATE", "DROP"}.intersection(
        statements
    )
    assert len(result.current_failures) == 1
    issues = result.current_failures[0].attempts[-1].failure.issues
    assert any(
        issue.category == "invalid_type" and issue.location == "$.reason_zh"
        for issue in issues
    )
    assert "PRIVATE_SENTINEL" not in json.dumps(asdict(result), default=str)
    assert set(asdict(result)) == {
        "paper_id",
        "stage",
        "snapshot_id",
        "current_fingerprint",
        "reason",
        "budgets",
        "current_failures",
        "kind",
        "format_version",
    }
    unknown = service.query(
        paper_id=data.paper_id, stage="boundary", snapshot_id="0" * 64
    )
    assert unknown.reason == "snapshot_not_found"
    assert unknown.budgets[0].applicability == "undeterminable"
    assert unknown.current_failures == ()


def test_query_invalid_stage_is_controlled_even_for_unhashable_input(
    tmp_path: Path,
) -> None:
    import pytest

    from paper_radar.screening_tasks import TaskError

    data = archive(tmp_path)
    with pytest.raises(TaskError) as error:
        ScreeningTasks(data.database, clock=lambda: NOW).query(
            paper_id=data.paper_id,
            stage=[],
            snapshot_id=data.snapshot_id,
        )
    assert error.value.reason == "invalid_request"
