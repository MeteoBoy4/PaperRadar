"""成功与候选失败的恢复闭包,复用 A1/A3/A5 权威入口。"""

import re

from sqlalchemy import Connection, select

from paper_radar.screening_tasks.attempt_rules import read_timestamp
from paper_radar.screening_tasks.errors import TaskError, TaskReason
from paper_radar.screening_tasks.frozen import load_frozen
from paper_radar.screening_tasks.success import SuccessService
from paper_radar.screening_tasks.success_rules import (
    decode_issues,
    encode_issues,
    model_matches,
    require_success_id,
    stored_candidate,
)
from paper_radar.screening_tasks.tables import (
    attempts,
    budgets,
    failures,
    requests,
    successes,
    tasks,
)


def require(condition: bool) -> None:
    if not condition:
        raise TaskError(TaskReason.CORRUPT_REFERENCE)


def validate_successes(service: SuccessService, connection: Connection) -> None:
    for row in connection.execute(select(successes)).mappings():
        content = service.load(row["success_id"])
        require_success_id(row["success_id"])
        candidate = stored_candidate(content.raw_response, row["audit_json"])
        budget = dict(
            connection.execute(
                select(budgets).where(budgets.c.budget_id == row["budget_id"])
            )
            .mappings()
            .one()
        )
        frozen = load_frozen(service.attempts.database, connection, budget)
        require(
            budget["stage"] in {"boundary", "value"}
            and model_matches(candidate, frozen.snapshot)
        )
        task = (
            connection.execute(select(tasks).where(tasks.c.task_id == row["task_id"]))
            .mappings()
            .one()
        )
        require(task["budget_id"] == row["budget_id"])
        attempt = (
            connection.execute(
                select(attempts).where(
                    attempts.c.task_id == row["task_id"],
                    attempts.c.attempt_no == row["attempt_no"],
                )
            )
            .mappings()
            .one()
        )
        require(
            read_timestamp(row["settled_at"]) >= read_timestamp(attempt["claimed_at"])
        )
    for row in connection.execute(
        select(requests).where(requests.c.cached_success_id.is_not(None))
    ).mappings():
        success = (
            connection.execute(
                select(successes).where(
                    successes.c.success_id == row["cached_success_id"]
                )
            )
            .mappings()
            .one()
        )
        task = (
            connection.execute(select(tasks).where(tasks.c.task_id == row["task_id"]))
            .mappings()
            .one()
        )
        require(task["budget_id"] == success["budget_id"])
        require(
            connection.execute(
                select(attempts.c.task_id).where(
                    attempts.c.receipt_id == row["receipt_id"]
                )
            ).first()
            is None
        )
    for row in connection.execute(select(failures)).mappings():
        issues = decode_issues(row["issues_json"])
        authority = row["kind"] in {"output_invalid", "model_mismatch"}
        require(bool(issues) == (row["kind"] == "output_invalid"))
        require(encode_issues(issues) == row["issues_json"])
        require((row["submission_sha256"] is not None) == authority)
        require((row["audit_json"] is not None) == authority)
        if authority:
            require(
                type(row["submission_sha256"]) is str
                and re.fullmatch(r"[0-9a-f]{64}", row["submission_sha256"]) is not None
            )
            candidate = stored_candidate(b"", row["audit_json"])
            budget = dict(
                connection.execute(
                    select(budgets)
                    .join(tasks, tasks.c.budget_id == budgets.c.budget_id)
                    .where(tasks.c.task_id == row["task_id"])
                )
                .mappings()
                .one()
            )
            frozen = load_frozen(service.attempts.database, connection, budget)
            require(decode_issues(row["issues_json"], stage=budget["stage"]) == issues)
            require(
                model_matches(candidate, frozen.snapshot)
                == (row["kind"] == "output_invalid")
            )
