"""共享只读查询:同一任务事实视图,绝不结算租约或推断业务资格。"""

from typing import Literal

from sqlalchemy import select

from paper_radar.papers import PaperFacts
from paper_radar.screening_tasks.attempt_repository import (
    failure_receipt,
    read_attempts,
)
from paper_radar.screening_tasks.attempt_rules import (
    derive_status,
    read_timestamp,
    utc_now,
)
from paper_radar.screening_tasks.errors import TaskError, TaskReason
from paper_radar.screening_tasks.execution import AttemptService
from paper_radar.screening_tasks.query_models import (
    AttemptView,
    BudgetView,
    TaskQueryResult,
    TaskView,
)
from paper_radar.screening_tasks.repository import receipt_row, to_receipt
from paper_radar.screening_tasks.tables import budgets, requests, tasks


class QueryService:
    def __init__(self, attempts: AttemptService) -> None:
        self.attempts = attempts

    def query(self, *, paper_id: str, stage: str, snapshot_id: str) -> TaskQueryResult:
        if (
            not isinstance(stage, str)
            or stage not in {"boundary", "value"}
            or not isinstance(paper_id, str)
            or not isinstance(snapshot_id, str)
        ):
            raise TaskError(TaskReason.INVALID_REQUEST)
        stage_value: Literal["boundary", "value"] = (
            "boundary" if stage == "boundary" else "value"
        )
        now = utc_now(self.attempts.clock)
        mapping = PaperFacts(self.attempts.database).map_screening_inputs(
            paper_id=paper_id, snapshot_id=snapshot_id
        )
        mapped = mapping.boundary if stage == "boundary" else mapping.value
        if mapped.reason is None and mapped.value is None:
            raise TaskError(TaskReason.CORRUPT_REFERENCE)
        current = (
            mapped.value.fingerprint if mapped.reason is None and mapped.value else None
        )
        views = []
        current_failures = []
        with self.attempts.connection(write=False) as connection:
            for budget in connection.execute(
                select(budgets)
                .where(budgets.c.paper_id == paper_id, budgets.c.stage == stage)
                .order_by(budgets.c.budget_id)
            ).mappings():
                task_views = []
                for task in connection.execute(
                    select(tasks)
                    .where(tasks.c.budget_id == budget["budget_id"])
                    .order_by(tasks.c.generation)
                ).mappings():
                    rows = read_attempts(connection, task["task_id"])
                    status = derive_status(task["task_id"], rows, now)
                    receipts = []
                    for identifier in connection.execute(
                        select(requests.c.receipt_id)
                        .where(requests.c.task_id == task["task_id"])
                        .order_by(requests.c.receipt_id)
                    ).scalars():
                        row = receipt_row(connection, identifier)
                        if row is None:
                            raise TaskError(TaskReason.CORRUPT_REFERENCE)
                        receipts.append(to_receipt(row))
                    task_views.append(
                        TaskView(
                            task_id=task["task_id"],
                            budget_id=budget["budget_id"],
                            generation=task["generation"],
                            parent_task_id=task["parent_task_id"],
                            state=status.state,
                            used_attempts=status.used_attempts,
                            remaining_attempts=status.remaining_attempts,
                            requests=tuple(receipts),
                            attempts=tuple(
                                AttemptView(
                                    attempt_no=row["attempt_no"],
                                    receipt_id=row["receipt_id"],
                                    version_id=row["version_id"],
                                    revision_no=row["revision_no"],
                                    selection_id=row["selection_id"],
                                    claimed_at=read_timestamp(row["claimed_at"]),
                                    expires_at=read_timestamp(row["expires_at"]),
                                    failure=failure_receipt(row)
                                    if row["kind"] is not None
                                    else None,
                                    success_id=row["success_id"],
                                )
                                for row in rows
                            ),
                        )
                    )
                if not task_views:
                    raise TaskError(TaskReason.CORRUPT_REFERENCE)
                latest = task_views[-1]
                applicability: Literal["current", "historical", "undeterminable"] = (
                    "undeterminable"
                    if mapped.reason is not None
                    else (
                        "current" if current == budget["fingerprint"] else "historical"
                    )
                )
                views.append(
                    BudgetView(
                        budget_id=budget["budget_id"],
                        fingerprint=budget["fingerprint"],
                        applicability=applicability,
                        reason=mapped.reason,
                        latest_generation=latest.generation,
                        latest_task_id=latest.task_id,
                        tasks=tuple(task_views),
                    )
                )
                if applicability == "current" and latest.state == "failed":
                    current_failures.append(latest)
        return TaskQueryResult(
            paper_id=paper_id,
            stage=stage_value,
            snapshot_id=snapshot_id,
            current_fingerprint=current,
            reason=mapped.reason,
            budgets=tuple(views),
            current_failures=tuple(current_failures),
        )
