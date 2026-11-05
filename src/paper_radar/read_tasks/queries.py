"""Read历史查询使用显式Connection;没有租约回收或配置激活。"""

import json
from datetime import datetime

from sqlalchemy import Connection, select
from sqlalchemy.engine import RowMapping

from paper_radar.read_tasks import tables as t
from paper_radar.read_tasks.models import (
    ReadAttempt,
    ReadFailure,
    ReadTask,
    ReadTaskError,
)
from paper_radar.reading.acceptance_v2 import ReadV2Category, ReadV2Issue
from paper_radar.reading.context import ExtractionIdentity


def budget_for(connection: Connection, task_id: str) -> RowMapping:
    row = (
        connection.execute(
            select(t.budgets)
            .select_from(
                t.budgets.join(t.tasks, t.budgets.c.budget_id == t.tasks.c.budget_id)
            )
            .where(t.tasks.c.task_id == task_id)
        )
        .mappings()
        .first()
    )
    if row is None:
        raise ReadTaskError("task_not_found")
    return row


def identity_of(row: RowMapping) -> ExtractionIdentity:
    return ExtractionIdentity(
        row["extraction_fingerprint"], row["reading_sha256"], row["evidence_map_sha256"]
    )


def deadline(connection: Connection, row: RowMapping) -> datetime:
    value = connection.execute(
        select(t.renewals.c.lease_until)
        .where(t.renewals.c.attempt_id == row["attempt_id"])
        .order_by(t.renewals.c.sequence.desc())
    ).scalar()
    return datetime.fromisoformat(value or row["lease_until"])


def task_view(connection: Connection, task_id: str) -> ReadTask:
    budget = budget_for(connection, task_id)
    task = (
        connection.execute(select(t.tasks).where(t.tasks.c.task_id == task_id))
        .mappings()
        .one()
    )
    attempts = []
    for row in connection.execute(
        select(t.attempts)
        .where(t.attempts.c.task_id == task_id)
        .order_by(t.attempts.c.ordinal)
    ).mappings():
        outcome = (
            connection.execute(
                select(t.outcomes).where(t.outcomes.c.attempt_id == row["attempt_id"])
            )
            .mappings()
            .first()
        )
        issues = (
            ()
            if outcome is None
            else tuple(
                ReadV2Issue(v["location"], ReadV2Category(v["category"]))
                for v in json.loads(outcome["issues_json"])
            )
        )
        attempts.append(
            ReadAttempt(
                row["attempt_id"],
                row["ordinal"],
                datetime.fromisoformat(row["claimed_at"]),
                deadline(connection, row),
                ReadFailure(outcome["failure"])
                if outcome and outcome["failure"]
                else None,
                datetime.fromisoformat(outcome["settled_at"]) if outcome else None,
                issues,
                basis=json.loads(row["basis_json"]),
                metadata_basis=json.loads(row["metadata_json"]),
            )
        )
    analysis_id = connection.execute(
        select(t.analyses.c.analysis_id).where(t.analyses.c.task_id == task_id)
    ).scalar()
    return ReadTask(
        task_id,
        budget["paper_id"],
        budget["fingerprint"],
        task["generation"],
        task["parent_task_id"],
        budget["snapshot_id"],
        identity_of(budget),
        budget["output_language"],
        tuple(attempts),
        analysis_id,
        retry_reason=task["retry_reason"],
        retry_actor=task["retry_actor"],
    )
