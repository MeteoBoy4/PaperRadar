"""执行事实的语义闭包;不读取时钟,不回收过期租约。"""

import re
from datetime import timedelta
from itertools import pairwise
from pathlib import Path
from typing import Any

from sqlalchemy import Connection, select

from paper_radar.papers import PaperFacts, resolve_revision
from paper_radar.screening_tasks.attempt_models import LEASE_SECONDS, FailureKind
from paper_radar.screening_tasks.attempt_rules import read_timestamp
from paper_radar.screening_tasks.errors import TaskError, TaskReason
from paper_radar.screening_tasks.repository import evidence_values, receipt_row
from paper_radar.screening_tasks.tables import attempts, failures, leases, tasks


def _require(condition: bool) -> None:
    if not condition:
        raise TaskError(TaskReason.CORRUPT_REFERENCE)


def validate_attempts(database: Path, connection: Connection) -> None:
    attempt_rows = [
        dict(row) for row in connection.execute(select(attempts)).mappings()
    ]
    lease_rows = {
        (row["task_id"], row["attempt_no"]): dict(row)
        for row in connection.execute(select(leases)).mappings()
    }
    failure_rows = {
        (row["task_id"], row["attempt_no"]): dict(row)
        for row in connection.execute(select(failures)).mappings()
    }
    keys = {(row["task_id"], row["attempt_no"]) for row in attempt_rows}
    _require(keys == set(lease_rows) and set(failure_rows) <= keys)
    task_ids = set(connection.execute(select(tasks.c.task_id)).scalars())
    _require(all(row["task_id"] in task_ids for row in attempt_rows))
    by_task: dict[str, list[dict[str, Any]]] = {}
    credentials: set[str] = set()
    renewals: set[str] = set()
    for row in attempt_rows:
        by_task.setdefault(row["task_id"], []).append(row)
        for field, known in (
            ("credential_sha256", credentials),
            ("renewal_sha256", renewals),
        ):
            _require(
                type(row[field]) is str
                and re.fullmatch(r"[0-9a-f]{64}", row[field]) is not None
            )
            _require(row[field] not in known)
            known.add(row[field])
        request = receipt_row(connection, row["receipt_id"])
        _require(request is not None)
        assert request is not None
        _require(request["task_id"] == row["task_id"])
        basis = {key: row[key] for key in ("version_id", "revision_no", "selection_id")}
        revision = resolve_revision(
            connection, version_id=row["version_id"], revision_no=row["revision_no"]
        )
        _require(
            revision.paper_id == request["paper_id"]
            and evidence_values(revision) == basis
        )
        mapping = PaperFacts(database).map_screening_inputs(
            version_id=row["version_id"],
            revision_no=row["revision_no"],
            snapshot_id=request["snapshot_id"],
        )
        mapped = mapping.boundary if request["stage"] == "boundary" else mapping.value
        _require(mapped.reason is None and mapped.value is not None)
        assert mapped.value is not None
        _require(mapped.value.fingerprint == request["fingerprint"])
        claimed = read_timestamp(row["claimed_at"])
        key = (row["task_id"], row["attempt_no"])
        expires = read_timestamp(lease_rows[key]["expires_at"])
        _require(expires - claimed >= timedelta(seconds=LEASE_SECONDS))
        if key in failure_rows:
            failure = failure_rows[key]
            settled = read_timestamp(failure["settled_at"])
            _require(settled >= claimed)
            kind = FailureKind(failure["kind"])
            if failure["origin"] == "recovery":
                _require(kind == FailureKind.OUTCOME_UNKNOWN and settled >= expires)
            elif failure["origin"] == "exception":
                _require(kind == FailureKind.EXECUTOR_ERROR)
            else:
                _require(
                    failure["origin"] == "executor"
                    and kind
                    in {
                        FailureKind.TIMEOUT,
                        FailureKind.CANCELLED,
                        FailureKind.PROTOCOL_ERROR,
                        FailureKind.EXECUTOR_ERROR,
                    }
                )
    for task_id, rows in by_task.items():
        ordered = sorted(rows, key=lambda row: row["attempt_no"])
        _require(
            [row["attempt_no"] for row in ordered] == list(range(1, len(ordered) + 1))
            and len(ordered) <= 2
        )
        for previous, current in pairwise(ordered):
            key = (task_id, previous["attempt_no"])
            _require(key in failure_rows)
            _require(
                read_timestamp(failure_rows[key]["settled_at"])
                <= read_timestamp(current["claimed_at"])
            )
