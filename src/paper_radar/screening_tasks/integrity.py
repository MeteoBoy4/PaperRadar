"""只读语义重验;绝不修复、升级或执行任务。"""

from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, select

from paper_radar.papers import PaperFacts, resolve_revision
from paper_radar.screening_tasks.attempt_repository import (
    read_attempts,
)
from paper_radar.screening_tasks.errors import TaskError, TaskReason
from paper_radar.screening_tasks.frozen import load_frozen
from paper_radar.screening_tasks.models import (
    BoundaryRequest,
    RetryRequest,
    ValueRequest,
)
from paper_radar.screening_tasks.repository import evidence_values, receipt_row
from paper_radar.screening_tasks.rules import (
    parse_request,
    parse_retry,
    receipt_id,
    request_digest,
    retry_receipt_id,
)
from paper_radar.screening_tasks.tables import budgets, inputs, requests, tasks
from paper_radar.stage_inputs import StageInput


def _require(value: bool) -> None:
    if not value:
        raise TaskError(TaskReason.CORRUPT_REFERENCE)


def _stored_request(
    raw: dict[str, Any],
) -> BoundaryRequest | ValueRequest | RetryRequest:
    try:
        return parse_retry(raw) if "parent_task_id" in raw else parse_request(raw)
    except TaskError:
        raise TaskError(TaskReason.CORRUPT_REFERENCE) from None


def _mapping_matches(database: Path, row: dict[str, Any], expected: StageInput) -> None:
    mapping = PaperFacts(database).map_screening_inputs(
        version_id=row["version_id"],
        revision_no=row["revision_no"],
        snapshot_id=row["snapshot_id"],
    )
    mapped = mapping.boundary if row["stage"] == "boundary" else mapping.value
    _require(mapped.reason is None and mapped.value == expected)


def validate_registration(database: Path, connection: Connection) -> None:
    all_budgets = [dict(row) for row in connection.execute(select(budgets)).mappings()]
    input_refs = set()
    task_refs = set()
    receipt_refs = set()
    for budget in all_budgets:
        _require(str(UUID(budget["budget_id"])) == budget["budget_id"])
        frozen = load_frozen(database, connection, budget)
        _mapping_matches(database, budget, frozen.stage_input)
        baseline = resolve_revision(
            connection,
            version_id=budget["version_id"],
            revision_no=budget["revision_no"],
        )
        _require(baseline.paper_id == budget["paper_id"])
        _require(
            evidence_values(baseline)
            == {key: budget[key] for key in evidence_values(baseline)}
        )
        input_refs.add(budget["fingerprint"])
        generations = (
            connection.execute(
                select(tasks)
                .where(tasks.c.budget_id == budget["budget_id"])
                .order_by(tasks.c.generation)
            )
            .mappings()
            .all()
        )
        _require(bool(generations))
        _require(
            [task["generation"] for task in generations]
            == list(range(len(generations)))
        )
        has_baseline_request = False
        for index, task in enumerate(generations):
            _require(str(UUID(task["task_id"])) == task["task_id"])
            _require(
                task["parent_task_id"]
                == (generations[index - 1]["task_id"] if index else None)
            )
            if index:
                parent_rows = read_attempts(connection, task["parent_task_id"])
                _require(
                    len(parent_rows) == 2
                    and all(
                        row["kind"] is not None and row["success_id"] is None
                        for row in parent_rows
                    )
                )
            task_refs.add(task["task_id"])
            retry_count = 0
            identifiers = (
                connection.execute(
                    select(requests.c.receipt_id).where(
                        requests.c.task_id == task["task_id"]
                    )
                )
                .scalars()
                .all()
            )
            _require(bool(identifiers))
            for identifier in identifiers:
                row = receipt_row(connection, identifier)
                _require(row is not None)
                assert row is not None
                raw = {
                    key: row[key]
                    for key in (
                        "paper_id",
                        "snapshot_id",
                        "stage",
                        "source",
                        "scheduled_day",
                        "request_id",
                        "actor",
                        "reason",
                    )
                }
                request: BoundaryRequest | ValueRequest | RetryRequest
                if row["source"] == "retry":
                    retry_count += 1
                    _require(
                        task["parent_task_id"] is not None
                        and row["cached_success_id"] is None
                    )
                    retry_raw = {
                        key: raw[key]
                        for key in (
                            "paper_id",
                            "snapshot_id",
                            "stage",
                            "request_id",
                            "actor",
                            "reason",
                        )
                    }
                    retry_raw["parent_task_id"] = task["parent_task_id"]
                    request = _stored_request(retry_raw)
                else:
                    if row["stage"] == "value":
                        raw["original_title_is_zh"] = budget["original_title_is_zh"]
                    request = _stored_request(raw)
                _require(request_digest(request) == row["request_sha256"])
                basis = {
                    key: row[key]
                    for key in ("version_id", "revision_no", "selection_id")
                }
                expected_id = (
                    retry_receipt_id(request)
                    if isinstance(request, RetryRequest)
                    else receipt_id(request, basis, row["fingerprint"])
                )
                _require(expected_id == identifier)
                revision = resolve_revision(
                    connection,
                    version_id=row["version_id"],
                    revision_no=row["revision_no"],
                )
                _require(revision.paper_id == budget["paper_id"])
                _require(evidence_values(revision) == basis)
                _mapping_matches(database, row, frozen.stage_input)
                receipt_refs.add(identifier)
                if (
                    row["source"] != "retry"
                    and task["generation"] == 0
                    and row["snapshot_id"] == budget["snapshot_id"]
                    and basis == {key: budget[key] for key in basis}
                ):
                    has_baseline_request = True
            _require(retry_count == (1 if index else 0))
        _require(has_baseline_request)
    _require(
        input_refs == set(connection.execute(select(inputs.c.fingerprint)).scalars())
    )
    _require(task_refs == set(connection.execute(select(tasks.c.task_id)).scalars()))
    _require(
        receipt_refs == set(connection.execute(select(requests.c.receipt_id)).scalars())
    )
