"""连接级尝试事实读取、能力校验及回收结算;不拥有事务或执行流程。"""

import re
from datetime import datetime

from sqlalchemy import Connection, select

from paper_radar.screening_tasks.attempt_models import (
    AttemptRow,
    Claim,
    FailureKind,
    FailureReceipt,
)
from paper_radar.screening_tasks.attempt_rules import digest, read_timestamp, timestamp
from paper_radar.screening_tasks.errors import TaskError, TaskReason
from paper_radar.screening_tasks.success_rules import decode_issues
from paper_radar.screening_tasks.tables import attempts, failures, leases, successes


def require_secret(value: str) -> None:
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise TaskError(TaskReason.INVALID_CREDENTIAL)


def require_attempt_time(row: AttemptRow, now: datetime) -> None:
    if now < read_timestamp(row["claimed_at"]):
        raise TaskError(TaskReason.INVALID_CLOCK)


def recover_attempt(connection: Connection, row: AttemptRow, now: datetime) -> None:
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


def failure_receipt(row: AttemptRow) -> FailureReceipt:
    kind, origin, settled = row["kind"], row["origin"], row["settled_at"]
    if kind is None or origin is None or settled is None:
        raise TaskError(TaskReason.CORRUPT_REFERENCE)
    return FailureReceipt(
        row["task_id"],
        row["attempt_no"],
        FailureKind(kind),
        origin,
        read_timestamp(settled),
        decode_issues(row["issues_json"]),
    )


def read_attempts(connection: Connection, task_id: str) -> list[AttemptRow]:
    rows = [
        AttemptRow(
            task_id=row["task_id"],
            attempt_no=row["attempt_no"],
            receipt_id=row["receipt_id"],
            version_id=row["version_id"],
            revision_no=row["revision_no"],
            selection_id=row["selection_id"],
            claimed_at=row["claimed_at"],
            credential_sha256=row["credential_sha256"],
            renewal_sha256=row["renewal_sha256"],
            expires_at=row["expires_at"],
            kind=row["kind"],
            origin=row["origin"],
            settled_at=row["settled_at"],
            issues_json=row["issues_json"],
            success_id=row["success_id"],
        )
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


def credential_attempt(connection: Connection, claim: Claim) -> tuple[AttemptRow, bool]:
    """核对指定尝试的凭据并返回是否为最新;重放/结算策略由调用流程决定。"""
    require_secret(claim.credential)
    rows = read_attempts(connection, claim.task_id)
    row = next((item for item in rows if item["attempt_no"] == claim.attempt_no), None)
    if row is None or row["credential_sha256"] != digest(claim.credential):
        raise TaskError(TaskReason.INVALID_CREDENTIAL)
    return row, row["attempt_no"] == rows[-1]["attempt_no"]
