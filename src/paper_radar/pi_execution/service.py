"""领取前准备与一次受控执行;任务预算/成功接收仍由 ScreeningTasks 拥有。"""

import math
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic

from paper_radar.config import ConfigError, load_config_snapshot
from paper_radar.live_evidence.ledger import LedgerError
from paper_radar.live_evidence.types import (
    AdmissionUse,
    CallSite,
    Capability,
    Consumer,
    ThinkingLevel,
)
from paper_radar.llm import (
    CallDescription,
    CallDescriptionError,
    DescriptionReason,
    build_call,
    render_request,
)
from paper_radar.llm.rpc import run_call, validate_request
from paper_radar.llm.rpc_types import (
    DEFAULT_LIMITS,
    Cancellation,
    MonotonicClock,
    RpcCandidate,
    RpcCategory,
    RpcLimits,
)
from paper_radar.pi_execution.admission import (
    EvidenceBinding,
    bind_description,
)
from paper_radar.pi_execution.admission_checkpoints import (
    AdmissionCheckpoints,
    PreclaimAdmissionDenied,
)
from paper_radar.pi_execution.admission_guard import AdmissionGuard
from paper_radar.pi_execution.errors import ExecutionError
from paper_radar.pi_execution.launcher import LaunchIdentity, prepare_launch
from paper_radar.pi_execution.resources import (
    ExecutionRoots,
    check_system_prompt,
    expected_cwd_section,
)
from paper_radar.pi_supply import SupplyError, activation_history, show_supply
from paper_radar.runtime_logging import Sink
from paper_radar.runtime_logging.events import Clock
from paper_radar.screening_tasks import (
    FailureKind,
    FailureReceipt,
    FailureReport,
    PiRpcExecutionAudit,
    ScreeningTasks,
    SuccessCandidate,
    SuccessReceipt,
    TaskError,
    TaskReason,
)
from paper_radar.stage_inputs import StageInput

_FAILURE_KINDS = {
    RpcCategory.TIMEOUT: FailureKind.TIMEOUT,
    RpcCategory.CANCELLED: FailureKind.CANCELLED,
    RpcCategory.ENVIRONMENT: FailureKind.EXECUTOR_ERROR,
    RpcCategory.PROTOCOL: FailureKind.PROTOCOL_ERROR,
}


def prepare_call(tasks: ScreeningTasks, receipt_id: str) -> CallDescription:
    receipt = tasks.get_receipt(receipt_id)
    frozen = tasks.load_input(receipt_id)
    try:
        audit = load_config_snapshot(tasks.database, receipt.snapshot_id)
        return build_call(frozen.stage_input, frozen.snapshot, audit)
    except ConfigError:
        raise TaskError(TaskReason.CORRUPT_REFERENCE) from None
    except CallDescriptionError as error:
        reasons = {
            DescriptionReason.INVALID_CONTEXT: TaskReason.INVALID_CONTEXT,
            DescriptionReason.PROJECTION_MISMATCH: TaskReason.CONTEXT_CONFLICT,
            DescriptionReason.CORRUPT_REFERENCE: TaskReason.CORRUPT_REFERENCE,
        }
        raise TaskError(reasons[error.reason]) from None


class PiExecution:
    def __init__(
        self,
        database: Path,
        data_root: Path,
        *,
        roots: ExecutionRoots,
        credentials_dir: Path,
        auth_mode: str,
        proxy: str | None = None,
        sink: Sink | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.database, self.data_root = database, data_root
        self.tasks = ScreeningTasks(
            database, data_root, sink=sink, clock=clock or (lambda: datetime.now(UTC))
        )
        self.roots, self.credentials_dir = roots, credentials_dir
        self.auth_mode, self.proxy = auth_mode, proxy
        self._now = clock or (lambda: datetime.now(UTC))

    def _binding(
        self, description: CallDescription, identity: LaunchIdentity
    ) -> EvidenceBinding:
        return bind_description(
            description,
            supply_id=identity.supply_id,
            install_id=identity.install_id,
            launch_policy_version=identity.launch_policy_version,
            isolation_policy_version=identity.isolation_policy_version,
            cwd_section=expected_cwd_section(),
            auth_mode=identity.auth_mode,
            proxy=self.proxy,
        )

    def run_attempt(
        self,
        receipt_id: str,
        *,
        limits: RpcLimits = DEFAULT_LIMITS,
        cancelled: Cancellation = lambda: False,
        clock: MonotonicClock = monotonic,
    ) -> SuccessReceipt | FailureReceipt:
        if type(limits) is not RpcLimits or any(
            type(value) not in (int, float)
            or not math.isfinite(value)
            or value <= 0
            or value > maximum
            for value, maximum in zip(
                (
                    limits.initialization,
                    limits.total,
                    limits.close,
                    limits.terminate,
                    limits.poll,
                ),
                (
                    DEFAULT_LIMITS.initialization,
                    DEFAULT_LIMITS.total,
                    DEFAULT_LIMITS.close,
                    DEFAULT_LIMITS.terminate,
                    DEFAULT_LIMITS.poll,
                ),
                strict=True,
            )
        ):
            raise ExecutionError("timeout_invalid")
        description = prepare_call(self.tasks, receipt_id)

        def validate_frame(correction: str | None) -> None:
            try:
                message = render_request(description, correction)
            except CallDescriptionError:
                raise TaskError(TaskReason.INVALID_CONTEXT) from None
            if validate_request(message) is not None:
                raise TaskError(TaskReason.INVALID_CONTEXT)

        validate_frame(self.tasks.prepare_correction(receipt_id))
        check_system_prompt(description.system_prompt)
        if description.sampling != "provider_default":
            raise ExecutionError("sampling_mapping_unavailable")
        try:
            history = activation_history(self.tasks.database)
            if not history:
                raise ExecutionError("install_unavailable")
            selected = history[-1]
            record = show_supply(self.tasks.database, selected.supply_id)
            if record.manifest.pi_version != description.pi_version:
                raise ExecutionError("protocol_unsupported")
            identity = LaunchIdentity.for_install(
                selected.supply_id,
                selected.install_id,
                record.manifest,
                auth_mode=self.auth_mode,
                proxy=self.proxy,
            )
        except SupplyError:
            raise ExecutionError("install_unavailable") from None
        binding = self._binding(description, identity)
        try:
            use = AdmissionUse(
                CallSite.SCREENING,
                Consumer(description.stage),
                ThinkingLevel(description.thinking_level),
            )
        except ValueError:
            raise ExecutionError("evidence_missing") from None
        guard = AdmissionGuard(use)
        try:
            return self._run_admitted(
                receipt_id,
                description,
                binding,
                guard,
                validate_frame,
                limits,
                cancelled,
                clock,
            )
        except (ExecutionError, LedgerError, SupplyError) as error:
            if isinstance(error, ExecutionError):
                guard.note_placement_failure(error)
            guard.tighten_after_denial(now=self._now())
            raise

    def _run_admitted(
        self,
        receipt_id: str,
        description: CallDescription,
        binding: EvidenceBinding,
        guard: AdmissionGuard,
        validate_frame: Callable[[str | None], None],
        limits: RpcLimits,
        cancelled: Cancellation,
        clock: MonotonicClock,
    ) -> SuccessReceipt | FailureReceipt:
        checkpoints = AdmissionCheckpoints(
            self.database, self.credentials_dir, guard, self._now
        )
        request = checkpoints.before_prepare(binding)
        with prepare_launch(
            self.tasks.database,
            description,
            roots=self.roots,
            credentials_dir=self.credentials_dir,
            auth_mode=self.auth_mode,
            proxy=self.proxy,
            attempt_timeout=limits.total + limits.terminate + limits.close,
        ) as prepared:
            if self._binding(description, prepared.identity) != binding:
                raise ExecutionError("evidence_mismatch")
            rebound = checkpoints.after_prepare(
                request, self._binding(description, prepared.identity)
            )

            def preclaim(correction: str | None) -> None:
                validate_frame(correction)
                try:
                    prepared.recheck_placement()
                except ExecutionError as error:
                    guard.note_placement_failure(error)
                    raise PreclaimAdmissionDenied from None
                checkpoints.preclaim(rebound)

            audit = PiRpcExecutionAudit.model_validate(
                {
                    **asdict(prepared.identity),
                    "adapter_version": description.adapter_version,
                    "protocol_profile": description.protocol_profile,
                    "channel": description.protocol,
                }
            )

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
                    prepared,
                    clock=clock,
                    cancelled=cancelled,
                    limits=limits,
                    expected_cwd_section=expected_cwd_section(),
                )
                if isinstance(result, RpcCandidate):
                    return SuccessCandidate(
                        result.raw_response,
                        executor_kind="pi_rpc",
                        reported_provider=result.provider,
                        reported_model=result.model,
                        input_tokens=result.input_tokens,
                        output_tokens=result.output_tokens,
                        execution_audit=audit,
                    )
                guard.tighten(now=self._now())
                return FailureReport(_FAILURE_KINDS[result.category])

            try:
                result = self.tasks.run_once(receipt_id, executor, preclaim=preclaim)
                if (
                    isinstance(result, FailureReceipt)
                    and result.kind is FailureKind.MODEL_MISMATCH
                ):
                    guard.tighten(
                        now=self._now(),
                        failed_capabilities=frozenset({Capability.MODEL_IDENTITY}),
                    )
                return result
            except PreclaimAdmissionDenied:
                raise ExecutionError("evidence_missing") from None
