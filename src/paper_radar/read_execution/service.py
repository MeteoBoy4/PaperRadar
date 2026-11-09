"""Read专用执行顺序;共享Pi资源与协议,预算和接收由ReadTasks拥有。"""

import math
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic

from paper_radar.live_evidence.ledger import LedgerError
from paper_radar.live_evidence.types import (
    AdmissionUse,
    CallSite,
    Capability,
    Consumer,
    ThinkingLevel,
)
from paper_radar.llm import CallDescription, CallDescriptionError, render_request
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
from paper_radar.read_inputs import PreparedReadInput
from paper_radar.read_tasks import (
    ReadAnalysis,
    ReadFailure,
    ReadHandle,
    ReadTask,
    ReadTaskError,
    ReadTasks,
)
from paper_radar.read_tasks.execution import execution_resource
from paper_radar.read_tasks.pi_rpc import PiReadCandidate, PiReadFailure
from paper_radar.runtime_logging import Sink
from paper_radar.runtime_logging.events import Clock
from paper_radar.screening_tasks.pi_rpc_audit import PiRpcExecutionAudit

_FAILURES = {
    RpcCategory.TIMEOUT: ReadFailure.TIMEOUT,
    RpcCategory.CANCELLED: ReadFailure.CANCELLED,
    RpcCategory.ENVIRONMENT: ReadFailure.EXECUTOR_ERROR,
    RpcCategory.PROTOCOL: ReadFailure.PROTOCOL_ERROR,
}


def _limits(limits: RpcLimits) -> None:
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


class ReadExecution:
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
        self.tasks = ReadTasks(database, data_root, sink=sink, clock=clock)
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
        task_id: str,
        *,
        audit_snapshot_id: str | None = None,
        limits: RpcLimits = DEFAULT_LIMITS,
        cancelled: Cancellation = lambda: False,
        clock: MonotonicClock = monotonic,
    ) -> ReadAnalysis | ReadTask:
        _limits(limits)
        if self.roots.data_root.resolve() != self.data_root.resolve():
            raise ExecutionError("resources_invalid")
        # 等锁不持SQLite事务,不占attempt,不先刷新短期token。
        with execution_resource(self.data_root):
            prepared_input = self.tasks.prepare_execution(
                task_id, audit_snapshot_id=audit_snapshot_id
            )
            description = prepared_input.description
            try:
                history = activation_history(self.database)
                if not history:
                    raise ExecutionError("install_unavailable")
                selected = history[-1]
                record = show_supply(self.database, selected.supply_id)
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
            if description.sampling != "provider_default":
                raise ExecutionError("sampling_mapping_unavailable")
            try:
                use = AdmissionUse(
                    CallSite.READ,
                    Consumer(description.stage),
                    ThinkingLevel(description.thinking_level),
                )
            except ValueError:
                raise ExecutionError("evidence_missing") from None
            guard = AdmissionGuard(use)
            try:
                return self._run_admitted(
                    task_id, prepared_input, binding, guard, limits, cancelled, clock
                )
            except (ExecutionError, LedgerError, SupplyError):
                guard.tighten_after_denial(now=self._now())
                raise

    def _run_admitted(
        self,
        task_id: str,
        prepared_input: PreparedReadInput,
        binding: EvidenceBinding,
        guard: AdmissionGuard,
        limits: RpcLimits,
        cancelled: Cancellation,
        clock: MonotonicClock,
    ) -> ReadAnalysis | ReadTask:
        description = prepared_input.description

        checkpoints = AdmissionCheckpoints(
            self.database, self.credentials_dir, guard, self._now
        )
        request = checkpoints.before_prepare(binding)
        # 同时失败必须优先准入;这里只在准入后检查完整最坏修正帧。
        if not prepared_input.budget.accepted:
            raise ReadTaskError("read_input_over_budget")

        def validate_frame(
            candidate: PreparedReadInput, correction: str | None
        ) -> None:
            if (
                candidate.stage_input != prepared_input.stage_input
                or candidate.context != prepared_input.context
            ):
                raise ReadTaskError("corrupt_reference")
            try:
                message = render_request(description, correction)
            except CallDescriptionError:
                raise ReadTaskError("corrupt_reference") from None
            if validate_request(message) is not None:
                raise ReadTaskError("read_input_over_budget")

        validate_frame(prepared_input, self.tasks.prepare_correction(task_id))
        check_system_prompt(description.system_prompt)
        with prepare_launch(
            self.database,
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

            def preclaim(candidate: PreparedReadInput, correction: str | None) -> None:
                validate_frame(candidate, correction)
                checkpoints.preclaim(rebound)

            audit = PiRpcExecutionAudit.model_validate(
                {
                    **asdict(prepared.identity),
                    "adapter_version": description.adapter_version,
                    "protocol_profile": description.protocol_profile,
                    "channel": description.protocol,
                }
            )

            def executor(handle: ReadHandle) -> PiReadCandidate | PiReadFailure:
                if (
                    handle.description.fingerprint,
                    handle.description.stage_input_payload,
                    handle.description.stage,
                ) != (
                    description.fingerprint,
                    description.stage_input_payload,
                    "read",
                ):
                    return PiReadFailure(ReadFailure.PROTOCOL_ERROR)
                result = run_call(
                    description,
                    render_request(description, handle.correction),
                    prepared,
                    clock=clock,
                    cancelled=cancelled,
                    limits=limits,
                    expected_cwd_section=expected_cwd_section(),
                )
                if isinstance(result, RpcCandidate):
                    return PiReadCandidate(
                        result.raw_response,
                        audit,
                        result.provider,
                        result.model,
                        result.input_tokens,
                        result.output_tokens,
                        audit_snapshot_id=description.audit_snapshot_id,
                    )
                guard.tighten(now=self._now())
                return PiReadFailure(_FAILURES[result.category])

            try:
                result = self.tasks.run_pi_once(task_id, executor, preclaim=preclaim)
                if (
                    isinstance(result, ReadTask)
                    and result.attempts
                    and result.attempts[-1].failure is ReadFailure.MODEL_MISMATCH
                ):
                    guard.tighten(
                        now=self._now(),
                        failed_capabilities=frozenset({Capability.MODEL_IDENTITY}),
                    )
                return result
            except PreclaimAdmissionDenied:
                raise ExecutionError("evidence_missing") from None
