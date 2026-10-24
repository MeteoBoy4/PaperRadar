"""仅用于离线 A8 的 prepare→run_once 接线;生产执行来源不开放。"""

from time import monotonic

from paper_radar.llm import CallDescriptionError, render_request
from paper_radar.llm.rpc import run_call, validate_request
from paper_radar.llm.rpc_types import (
    DEFAULT_LIMITS,
    Cancellation,
    MonotonicClock,
    RpcCandidate,
    RpcCategory,
    RpcLimits,
    SessionFactory,
)
from paper_radar.screening_tasks import (
    FailureKind,
    FailureReceipt,
    FailureReport,
    ScreeningTasks,
    SuccessCandidate,
    SuccessReceipt,
    TaskError,
    TaskReason,
)
from paper_radar.stage_inputs import StageInput
from tests.a8_call_support import prepare_call

FAILURE_KINDS = {
    RpcCategory.TIMEOUT: FailureKind.TIMEOUT,
    RpcCategory.CANCELLED: FailureKind.CANCELLED,
    RpcCategory.ENVIRONMENT: FailureKind.EXECUTOR_ERROR,
    RpcCategory.PROTOCOL: FailureKind.PROTOCOL_ERROR,
}


def run_attempt(
    tasks: ScreeningTasks,
    receipt_id: str,
    factory: SessionFactory,
    *,
    clock: MonotonicClock = monotonic,
    cancelled: Cancellation = lambda: False,
    limits: RpcLimits = DEFAULT_LIMITS,
) -> SuccessReceipt | FailureReceipt:
    description = prepare_call(tasks, receipt_id)
    if validate_request(render_request(description)) is not None:
        raise TaskError(TaskReason.INVALID_CONTEXT)

    def executor(
        stage_input: StageInput, correction: str | None, _renewal: str
    ) -> SuccessCandidate | FailureReport:
        if (
            stage_input.fingerprint != description.fingerprint
            or stage_input.payload_bytes != description.stage_input_payload
            or stage_input.stage.value != description.stage
        ):
            return FailureReport(FailureKind.PROTOCOL_ERROR)
        try:
            message = render_request(description, correction)
        except CallDescriptionError:
            return FailureReport(FailureKind.PROTOCOL_ERROR)
        result = run_call(
            description,
            message,
            factory,
            clock=clock,
            cancelled=cancelled,
            limits=limits,
        )
        if isinstance(result, RpcCandidate):
            return SuccessCandidate(
                result.raw_response,
                reported_provider=result.provider,
                reported_model=result.model,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
            )
        return FailureReport(FAILURE_KINDS[result.category])

    return tasks.run_once(receipt_id, executor)
