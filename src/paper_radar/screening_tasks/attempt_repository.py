"""连接级尝试事实读取、能力校验及回收结算;不拥有事务或执行流程。"""

import re
from datetime import datetime
from typing import Any

from sqlalchemy import Connection, select

from paper_radar.screening_tasks.attempt_models import FailureKind, FailureReceipt
from paper_radar.screening_tasks.attempt_rules import read_timestamp, timestamp
from paper_radar.screening_tasks.errors import TaskError, TaskReason
from paper_radar.screening_tasks.success_rules import decode_issues
from paper_radar.screening_tasks.tables import attempts, failures, leases, successes


def require_secret(value: str) -> None:
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise TaskError(TaskReason.INVALID_CREDENTIAL)


def require_attempt_time(row: dict[str, Any], now: datetime) -> None:
    if now < read_timestamp(row["claimed_at"]):
        raise TaskError(TaskReason.INVALID_CLOCK)


def recover_attempt(connection: Connection, row: dict[str, Any], now: datetime) -> None:
    require_attempt_time(row, now)
    connection.execute(
        failures.insert().values(
            task_id=row["task_id"],
            attempt_no=row["attempt_no"],
            kind=FailureKind.OUTCOME_UNKNOWN.value,
            origin="recovery",
            settled_at=timestamp(now),
        )
    )


def failure_receipt(row: dict[str, Any]) -> FailureReceipt:
    return FailureReceipt(
        row["task_id"],
        row["attempt_no"],
        FailureKind(row["kind"]),
        row["origin"],
        read_timestamp(row["settled_at"]),
        decode_issues(row["issues_json"]),
    )


def read_attempts(connection: Connection, task_id: str) -> list[dict[str, Any]]:
    rows = [
        dict(row)
        for row in connection.execute(
            select(
                attempts,
                leases.c.expires_at,
                failures.c.kind,
                failures.c.origin,
                failures.c.settled_at,
                failures.c.issues_json,
                successes.c.success_id,
            )
            .outerjoin(
                leases,
                (leases.c.task_id == attempts.c.task_id)
                & (leases.c.attempt_no == attempts.c.attempt_no),
            )
            .outerjoin(
                failures,
                (failures.c.task_id == attempts.c.task_id)
                & (failures.c.attempt_no == attempts.c.attempt_no),
            )
            .outerjoin(
                successes,
                (successes.c.task_id == attempts.c.task_id)
                & (successes.c.attempt_no == attempts.c.attempt_no),
            )
            .where(attempts.c.task_id == task_id)
            .order_by(attempts.c.attempt_no)
        ).mappings()
    ]
    if (
        any(row["expires_at"] is None for row in rows)
        or [row["attempt_no"] for row in rows] != list(range(1, len(rows) + 1))
        or len(rows) > 2
    ):
        raise TaskError(TaskReason.CORRUPT_REFERENCE)
    if any(
        row["success_id"] is not None and row["kind"] is not None for row in rows
    ) or any(row["kind"] is None for row in rows[:-1]):
        raise TaskError(TaskReason.CORRUPT_REFERENCE)
    return rows
