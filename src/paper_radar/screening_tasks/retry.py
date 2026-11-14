"""显式 retry:映射当前输入,原子结算并追加唯一后继。"""

from collections.abc import Callable
from uuid import uuid4

from sqlalchemy import Connection, select

from paper_radar.papers import PaperFacts, resolve_revision
from paper_radar.screening_tasks.attempt_models import ATTEMPTS_PER_GENERATION
from paper_radar.screening_tasks.attempt_repository import (
    read_attempts,
    recover_attempt,
)
from paper_radar.screening_tasks.attempt_rules import derive_status, utc_now
from paper_radar.screening_tasks.errors import TaskError, TaskReason
from paper_radar.screening_tasks.execution import AttemptService
from paper_radar.screening_tasks.models import RequestReceipt
from paper_radar.screening_tasks.repository import (
    evidence_values,
    receipt_row,
    replay_request,
    require_stage_mapping,
    to_receipt,
)
from paper_radar.screening_tasks.rules import (
    parse_retry,
    request_digest,
    retry_receipt_id,
)
from paper_radar.screening_tasks.tables import budgets, requests, successes, tasks


class RetryService:
    def __init__(self, attempts: AttemptService) -> None:
        self.attempts = attempts

    def failed(
        self,
        *,
        paper_id: str,
        snapshot_id: str,
        request_id: str,
        reason: str,
        actor: str,
        stage: str | None = None,
        write_guard: Callable[[Connection], None] | None = None,
    ) -> RequestReceipt:
        from paper_radar.screening_tasks.query import QueryService

        if stage not in (None, "boundary", "value") or any(
            not isinstance(value, str) or not value.strip()
            for value in (request_id, reason, actor)
        ):
            raise TaskError(TaskReason.INVALID_REQUEST)
        # 重放优先于当前映射和失败列表;父身份仍由权威历史恢复。
        with self.attempts.connection(write=False) as connection:
            old = connection.execute(
                select(requests.c.receipt_id, tasks.c.parent_task_id)
                .join(tasks, requests.c.task_id == tasks.c.task_id)
                .where(requests.c.request_id == request_id)
            ).first()
            if old is not None:
                row = receipt_row(connection, old.receipt_id)
                if row is None or old.parent_task_id is None:
                    raise TaskError(TaskReason.REQUEST_CONFLICT)
                selected_stage = row["stage"] if stage is None else stage
                return self.register(
                    dict(
                        paper_id=paper_id,
                        snapshot_id=snapshot_id,
                        request_id=request_id,
                        reason=reason,
                        actor=actor,
                        stage=selected_stage,
                        parent_task_id=old.parent_task_id,
                    ),
                    write_guard=write_guard,
                )
        failures = tuple(
            (query.stage, task)
            for selected_stage in (
                (stage,) if stage is not None else ("boundary", "value")
            )
            for query in (
                QueryService(self.attempts).query(
                    paper_id=paper_id, stage=selected_stage, snapshot_id=snapshot_id
                ),
            )
            for task in query.current_failures
        )
        if not failures:
            raise TaskError(TaskReason.NOT_FAILED)
        if len(failures) != 1:
            raise TaskError(TaskReason.AMBIGUOUS_FAILURE)
        parent_stage, parent = failures[0]
        return self.register(
            dict(
                paper_id=paper_id,
                snapshot_id=snapshot_id,
                request_id=request_id,
                reason=reason,
                actor=actor,
                stage=parent_stage,
                parent_task_id=parent.task_id,
            ),
            write_guard=write_guard,
        )

    def register(
        self,
        raw: object,
        *,
        write_guard: Callable[[Connection], None] | None = None,
    ) -> RequestReceipt:
        request = parse_retry(raw)
        with self.attempts.connection(write=False) as connection:
            replayed = replay_request(connection, request)
            if replayed is not None:
                return replayed
        mapping = PaperFacts(self.attempts.database).map_screening_inputs(
            paper_id=request.paper_id, snapshot_id=request.snapshot_id
        )
        stage_input, evidence = require_stage_mapping(mapping, request.stage)
        basis = evidence_values(evidence)
        with self.attempts.connection(write=True) as connection:
            replayed = replay_request(connection, request)
            if replayed is not None:
                return replayed
            current = resolve_revision(connection, paper_id=request.paper_id)
            if evidence_values(current) != basis:
                raise TaskError(TaskReason.FACTS_CHANGED)
            parent = (
                connection.execute(
                    select(
                        tasks,
                        budgets.c.paper_id,
                        budgets.c.stage,
                        budgets.c.fingerprint,
                    )
                    .join(budgets, tasks.c.budget_id == budgets.c.budget_id)
                    .where(tasks.c.task_id == request.parent_task_id)
                )
                .mappings()
                .first()
            )
            if parent is None:
                raise TaskError(TaskReason.TASK_NOT_FOUND)
            if (parent["paper_id"], parent["stage"], parent["fingerprint"]) != (
                request.paper_id,
                request.stage,
                stage_input.fingerprint,
            ):
                raise TaskError(TaskReason.FACTS_CHANGED)
            successor = connection.execute(
                select(tasks.c.task_id).where(
                    tasks.c.parent_task_id == request.parent_task_id
                )
            ).scalar_one_or_none()
            if successor is not None:
                raise TaskError(TaskReason.ALREADY_RETRIED, successor_task_id=successor)
            if (
                connection.execute(
                    select(successes.c.success_id).where(
                        successes.c.budget_id == parent["budget_id"]
                    )
                ).first()
                is not None
            ):
                raise TaskError(TaskReason.ALREADY_SUCCEEDED)
            latest = connection.execute(
                select(tasks.c.task_id)
                .where(tasks.c.budget_id == parent["budget_id"])
                .order_by(tasks.c.generation.desc())
                .limit(1)
            ).scalar_one()
            if latest != request.parent_task_id:
                raise TaskError(TaskReason.NOT_LATEST)
            now = utc_now(self.attempts.clock)
            rows = read_attempts(connection, request.parent_task_id)
            status = derive_status(request.parent_task_id, rows, now)
            # 只有第二次已到期的 attempt 可以在同一事务变为失败终态并开后继。
            if (
                status.state == "lease_expired"
                and status.used_attempts == ATTEMPTS_PER_GENERATION
            ):
                recover_attempt(connection, rows[-1], now)
                rows = read_attempts(connection, request.parent_task_id)
                status = derive_status(request.parent_task_id, rows, now)
            if status.state != "failed":
                raise TaskError(TaskReason.NOT_FAILED)
            if write_guard is not None:
                write_guard(connection)
            task_id = str(uuid4())
            connection.execute(
                tasks.insert().values(
                    task_id=task_id,
                    budget_id=parent["budget_id"],
                    generation=parent["generation"] + 1,
                    parent_task_id=request.parent_task_id,
                )
            )
            identifier = retry_receipt_id(request)
            connection.execute(
                requests.insert().values(
                    receipt_id=identifier,
                    request_id=request.request_id,
                    request_sha256=request_digest(request),
                    task_id=task_id,
                    source="retry",
                    snapshot_id=request.snapshot_id,
                    reason=request.reason,
                    actor=request.actor,
                    **basis,
                )
            )
            row = receipt_row(connection, identifier)
            if row is None:
                raise TaskError(TaskReason.CORRUPT_REFERENCE)
            return to_receipt(row)
