"""任务登记关系的连接级读写;事务由公共服务持有。"""

from typing import Any
from uuid import uuid4

from sqlalchemy import Connection, select

from paper_radar.papers import MappingEvidence, RevisionView
from paper_radar.screening_tasks.errors import TaskError, TaskReason
from paper_radar.screening_tasks.models import (
    BoundaryRequest,
    RequestReceipt,
    ValueRequest,
)
from paper_radar.screening_tasks.rules import receipt_id, request_digest
from paper_radar.screening_tasks.tables import budgets, inputs, requests, tasks
from paper_radar.stage_inputs import StageInput


def evidence_values(evidence: RevisionView) -> dict[str, Any]:
    return {
        "version_id": evidence.version_id,
        "revision_no": evidence.revision_no,
        "selection_id": evidence.selection.selection_id if evidence.selection else None,
    }


def receipt_row(connection: Connection, identifier: str) -> dict[str, Any] | None:
    row = (
        connection.execute(
            select(
                requests,
                tasks.c.generation,
                tasks.c.budget_id,
                budgets.c.paper_id,
                budgets.c.stage,
                budgets.c.fingerprint,
            )
            .join(tasks, requests.c.task_id == tasks.c.task_id)
            .join(budgets, tasks.c.budget_id == budgets.c.budget_id)
            .where(requests.c.receipt_id == identifier)
        )
        .mappings()
        .first()
    )
    return dict(row) if row is not None else None


def to_receipt(row: dict[str, Any]) -> RequestReceipt:
    return RequestReceipt(
        **{
            key: row[key]
            for key, spec in RequestReceipt.__dataclass_fields__.items()
            if spec.init
        }
    )


def replay_request(
    connection: Connection, request: BoundaryRequest | ValueRequest
) -> RequestReceipt | None:
    if request.source != "manual":
        return None
    row = connection.execute(
        select(requests.c.receipt_id).where(requests.c.request_id == request.request_id)
    ).first()
    if row is None:
        return None
    existing = receipt_row(connection, row.receipt_id)
    if existing is None:
        raise TaskError(TaskReason.CORRUPT_REFERENCE)
    if existing["request_sha256"] != request_digest(request):
        raise TaskError(TaskReason.REQUEST_CONFLICT)
    return to_receipt(existing)


def register_request(
    connection: Connection,
    request: BoundaryRequest | ValueRequest,
    stage_input: StageInput,
    evidence: MappingEvidence,
) -> RequestReceipt:
    replayed = replay_request(connection, request)
    if replayed is not None:
        return replayed
    basis = evidence_values(evidence)
    identifier = receipt_id(request, basis, stage_input.fingerprint)
    existing = receipt_row(connection, identifier)
    if existing is not None:
        if isinstance(request, ValueRequest):
            frozen_language = connection.execute(
                select(budgets.c.original_title_is_zh).where(
                    budgets.c.budget_id == existing["budget_id"]
                )
            ).scalar_one()
            if frozen_language != request.original_title_is_zh:
                raise TaskError(TaskReason.CONTEXT_CONFLICT)
        if existing["request_sha256"] != request_digest(request):
            raise TaskError(TaskReason.REQUEST_CONFLICT)
        return to_receipt(existing)
    input_row = (
        connection.execute(
            select(inputs).where(inputs.c.fingerprint == stage_input.fingerprint)
        )
        .mappings()
        .first()
    )
    if input_row is None:
        connection.execute(
            inputs.insert().values(
                fingerprint=stage_input.fingerprint,
                stage=request.stage,
                payload=stage_input.payload_bytes,
                format_version=1,
            )
        )
    elif (
        input_row["payload"] != stage_input.payload_bytes
        or input_row["stage"] != request.stage
    ):
        raise TaskError(TaskReason.CORRUPT_REFERENCE)
    budget = (
        connection.execute(
            select(budgets).where(
                budgets.c.paper_id == request.paper_id,
                budgets.c.stage == request.stage,
                budgets.c.fingerprint == stage_input.fingerprint,
            )
        )
        .mappings()
        .first()
    )
    language = (
        request.original_title_is_zh if isinstance(request, ValueRequest) else None
    )
    if budget is None:
        budget_id = str(uuid4())
        connection.execute(
            budgets.insert().values(
                budget_id=budget_id,
                paper_id=request.paper_id,
                stage=request.stage,
                fingerprint=stage_input.fingerprint,
                snapshot_id=request.snapshot_id,
                original_title_is_zh=language,
                **basis,
            )
        )
        task_id = str(uuid4())
        connection.execute(
            tasks.insert().values(task_id=task_id, budget_id=budget_id, generation=0)
        )
    else:
        budget_id = budget["budget_id"]
        if budget["original_title_is_zh"] != language:
            raise TaskError(TaskReason.CONTEXT_CONFLICT)
        task_id = connection.execute(
            select(tasks.c.task_id)
            .where(tasks.c.budget_id == budget_id)
            .order_by(tasks.c.generation.desc())
            .limit(1)
        ).scalar_one()
    connection.execute(
        requests.insert().values(
            receipt_id=identifier,
            request_id=request.request_id,
            request_sha256=request_digest(request),
            task_id=task_id,
            source=request.source,
            snapshot_id=request.snapshot_id,
            scheduled_day=request.scheduled_day,
            reason=request.reason,
            actor=request.actor,
            **basis,
        )
    )
    result = receipt_row(connection, identifier)
    if result is None:
        raise TaskError(TaskReason.CORRUPT_REFERENCE)
    return to_receipt(result)
