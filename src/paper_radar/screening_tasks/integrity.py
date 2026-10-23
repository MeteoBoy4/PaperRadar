"""只读语义重验;绝不修复、升级或执行任务。"""

from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import Connection, select

from paper_radar.papers import PaperFacts, resolve_revision
from paper_radar.screening_tasks.errors import TaskError, TaskReason
from paper_radar.screening_tasks.frozen import load_frozen
from paper_radar.screening_tasks.repository import evidence_values, receipt_row
from paper_radar.screening_tasks.rules import parse_request, receipt_id, request_digest
from paper_radar.screening_tasks.tables import budgets, inputs, requests, tasks
from paper_radar.stage_inputs import StageInput


def _require(value: bool) -> None:
    if not value:
        raise TaskError(TaskReason.CORRUPT_REFERENCE)


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
                select(tasks).where(tasks.c.budget_id == budget["budget_id"])
            )
            .mappings()
            .all()
        )
        _require(len(generations) == 1 and generations[0]["generation"] == 0)
        task = generations[0]
        _require(str(UUID(task["task_id"])) == task["task_id"])
        task_refs.add(task["task_id"])
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
        has_baseline_request = False
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
            if row["stage"] == "value":
                raw["original_title_is_zh"] = budget["original_title_is_zh"]
            request = parse_request(raw)
            _require(request_digest(request) == row["request_sha256"])
            basis = {
                key: row[key] for key in ("version_id", "revision_no", "selection_id")
            }
            _require(receipt_id(request, basis, row["fingerprint"]) == identifier)
            revision = resolve_revision(
                connection, version_id=row["version_id"], revision_no=row["revision_no"]
            )
            _require(revision.paper_id == budget["paper_id"])
            _require(evidence_values(revision) == basis)
            _mapping_matches(database, row, frozen.stage_input)
            receipt_refs.add(identifier)
            if row["snapshot_id"] == budget["snapshot_id"] and basis == {
                key: budget[key] for key in basis
            }:
                has_baseline_request = True
        _require(has_baseline_request)
    _require(
        input_refs == set(connection.execute(select(inputs.c.fingerprint)).scalars())
    )
    _require(task_refs == set(connection.execute(select(tasks.c.task_id)).scalars()))
    _require(
        receipt_refs == set(connection.execute(select(requests.c.receipt_id)).scalars())
    )
