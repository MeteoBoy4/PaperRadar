"""专用Pi组合端口;test入口没有来源开关,共用Read接收权威。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from paper_radar.read_tasks.service import ReadTasks

from collections.abc import Callable
from dataclasses import dataclass, field

from pydantic import ValidationError

from paper_radar.execution_history import require_supply_reference
from paper_radar.read_inputs import PreparedReadInput
from paper_radar.read_tasks.models import (
    ReadAnalysis,
    ReadHandle,
    ReadTask,
    ReadTaskError,
)
from paper_radar.screening_tasks.pi_rpc_audit import PiRpcAudit, PiRpcExecutionAudit


@dataclass(frozen=True)
class PiReadCandidate:
    raw_response: bytes = field(repr=False)
    execution_audit: PiRpcExecutionAudit = field(repr=False)
    reported_provider: str = field(repr=False)
    reported_model: str = field(repr=False)
    input_tokens: int | None = field(default=None, repr=False)
    output_tokens: int | None = field(default=None, repr=False)


def validate_audit(
    service: ReadTasks, prepared: PreparedReadInput, audit_json: str
) -> PiRpcAudit:
    try:
        audit = PiRpcAudit.model_validate_json(audit_json)
        description = prepared.description
        require_supply_reference(
            service.database,
            supply_id=audit.supply_id,
            install_id=audit.install_id,
            pi_version=audit.pi_version,
            node_version=audit.node_version,
        )
        if (
            audit.pi_version,
            audit.adapter_version,
            audit.protocol_profile,
            audit.channel,
            audit.credential_provider,
            audit.reported_provider,
            audit.reported_model,
        ) != (
            description.pi_version,
            description.adapter_version,
            description.protocol_profile,
            description.protocol,
            description.provider,
            description.provider,
            description.model,
        ):
            raise ValueError
        return audit
    except (ValueError, TypeError, KeyError):
        raise ReadTaskError("corrupt_reference") from None


def submit_pi(
    service: ReadTasks, handle: ReadHandle, candidate: PiReadCandidate
) -> ReadAnalysis | ReadTask:
    if (
        type(candidate) is not PiReadCandidate
        or type(candidate.raw_response) is not bytes
        or type(candidate.execution_audit) is not PiRpcExecutionAudit
    ):
        raise ReadTaskError("invalid_request")
    prepared = service.prepare(handle.task_id)
    try:
        audit = PiRpcAudit.model_validate(
            {
                **candidate.execution_audit.model_dump(),
                "format_version": 3,
                "executor_kind": "pi_rpc",
                "reported_provider": candidate.reported_provider,
                "reported_model": candidate.reported_model,
                "provider_request_id": None,
                "input_tokens": candidate.input_tokens,
                "output_tokens": candidate.output_tokens,
            }
        )
    except ValidationError:
        raise ReadTaskError("invalid_request") from None
    if (audit.reported_provider, audit.reported_model) != (
        prepared.description.provider,
        prepared.description.model,
    ):
        return service.fail(handle, "model_mismatch")
    audit_json = audit.model_dump_json()
    validate_audit(service, prepared, audit_json)
    from paper_radar.read_tasks.acceptance import submit

    return submit(
        service,
        handle,
        candidate.raw_response,
        executor_kind="pi_rpc",
        audit_json=audit_json,
    )


def run_pi_once(
    service: ReadTasks,
    task_id: str,
    executor: Callable[[ReadHandle], PiReadCandidate],
    *,
    preclaim: Callable[[PreparedReadInput, str | None], None] | None = None,
) -> ReadAnalysis | ReadTask:
    """只由受控Pi执行组合调用;此端口不授予现场准入或启动模型。"""
    handle = service.claim(task_id, preclaim=preclaim)
    try:
        candidate = executor(handle)
    except Exception:
        return service.fail(handle, "executor_error")
    return submit_pi(service, handle, candidate)
