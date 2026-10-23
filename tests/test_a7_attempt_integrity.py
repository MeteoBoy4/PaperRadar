"""执行事实经公共只读完整性边界重验,损坏不自动修复。"""

import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import pytest

from paper_radar.screening_tasks import (
    FailureKind,
    FailureReport,
    ScreeningTasks,
    TaskError,
    TaskReason,
)
from tests.a7_registration_support import archive, request_for


@pytest.mark.parametrize(
    "damage",
    [
        "lease_missing",
        "gap",
        "request_task",
        "claim_basis",
        "lease_time",
        "claim_time",
        "settlement_time",
        "recovery_before_expiry",
        "failure_origin",
        "second_without_settlement",
        "credential_digest",
        "claim_time_overflow",
    ],
)
def test_invalid_attempt_history_is_rejected_read_only(
    tmp_path: Path, damage: str
) -> None:
    data = archive(tmp_path)
    service = ScreeningTasks(
        data.database, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    receipt = service.register(request_for(data))
    other = service.register(
        request_for(data, stage="value", original_title_is_zh=False)
    )
    first = service.claim(receipt.receipt_id)
    service.fail(first, FailureReport(FailureKind.TIMEOUT))
    service.claim(receipt.receipt_id)
    with closing(sqlite3.connect(data.database)) as connection:
        if damage == "lease_missing":
            connection.execute("DELETE FROM screening_leases WHERE attempt_no=2")
        elif damage == "gap":
            connection.execute("DELETE FROM screening_failures")
            connection.execute("DELETE FROM screening_leases WHERE attempt_no=1")
            connection.execute("DELETE FROM screening_attempts WHERE attempt_no=1")
        elif damage == "request_task":
            connection.execute(
                "UPDATE screening_attempts SET receipt_id=?", (other.receipt_id,)
            )
        elif damage == "claim_basis":
            connection.execute("UPDATE screening_attempts SET selection_id=NULL")
        elif damage == "lease_time":
            connection.execute(
                "UPDATE screening_leases SET "
                "expires_at='2026-01-01T00:09:59.000000+00:00'"
            )
        elif damage == "claim_time":
            connection.execute(
                "UPDATE screening_attempts SET claimed_at='2026-01-01T00:00:00'"
            )
        elif damage == "claim_time_overflow":
            connection.execute(
                "UPDATE screening_attempts SET "
                "claimed_at='9999-12-31T23:59:59.999999+00:00'"
            )
        elif damage == "settlement_time":
            connection.execute(
                "UPDATE screening_failures SET "
                "settled_at='2025-12-31T23:59:59.000000+00:00'"
            )
        elif damage == "recovery_before_expiry":
            connection.execute(
                "UPDATE screening_failures SET kind='outcome_unknown',origin='recovery'"
            )
        elif damage == "failure_origin":
            connection.execute("UPDATE screening_failures SET origin='exception'")
        elif damage == "second_without_settlement":
            connection.execute("DELETE FROM screening_failures")
        else:
            connection.execute(
                "UPDATE screening_attempts SET credential_sha256='invalid' "
                "WHERE attempt_no=1"
            )
        connection.commit()
        before = connection.iterdump()
        snapshot = tuple(before)
    with pytest.raises(TaskError) as error:
        service.validate_all()
    assert error.value.reason == TaskReason.CORRUPT_REFERENCE
    with closing(sqlite3.connect(data.database)) as connection:
        assert tuple(connection.iterdump()) == snapshot
