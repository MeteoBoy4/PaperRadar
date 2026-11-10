"""产品检查点共享权威及受控结算映射;收紧动作在业务事务外执行。"""

from contextlib import suppress
from datetime import datetime

from paper_radar.live_evidence.ledger import LedgerError
from paper_radar.live_evidence.lifecycle import use_id_for
from paper_radar.live_evidence.observation import ObservationChanged
from paper_radar.live_evidence.reasons import ReasonCode
from paper_radar.live_evidence.service import (
    AdmissionProjection,
    AdmissionRequest,
    request_revocation,
    request_use_revocation,
)
from paper_radar.live_evidence.types import (
    AdmissionUse,
    BindingComponent,
    Capability,
    Requirement,
)
from paper_radar.pi_execution.admission import load_admission_evidence
from paper_radar.pi_execution.errors import ExecutionError


class AdmissionGuard:
    """只保存当次拒绝所需来源;不缓存授予、不持有账本连接。"""

    def __init__(self, use: AdmissionUse) -> None:
        self.use = use
        self.projection: AdmissionProjection | None = None
        self.sources: dict[Capability, str] = {}
        self.observation_failure: str | None = None
        self.observation_components: frozenset[BindingComponent] = frozenset()

    def check(self, request: AdmissionRequest, *, now: datetime) -> AdmissionProjection:
        previous = self.projection
        projection = load_admission_evidence(request, now=now)
        self.projection = projection
        self.sources.update(projection.sources)
        if (
            previous is not None
            and previous.watermark is not None
            and (
                projection.watermark is None
                or projection.watermark < previous.watermark
            )
        ) or not projection.decision.executable:
            raise ExecutionError("evidence_missing")
        return projection

    def note_observation_failure(
        self, error: LedgerError, projection: AdmissionProjection | None = None
    ) -> None:
        """保留受控原因,避免映射成evidence_missing后混淆租期与来源丢失。"""
        self.observation_failure = error.category
        if isinstance(error, ObservationChanged):
            self.observation_components = error.components
        if projection is not None:
            self.projection = projection
            self.sources.update(projection.sources)
            if error.category == "observation_drift" and projection.refresh is not None:
                self.observation_components = frozenset(
                    projection.refresh.changed_components
                )

    def note_placement_failure(self, error: ExecutionError) -> None:
        """握手/manager临时不可用只拒当次;实际漂移与来源失信仍收紧。"""
        if (
            error.reason.startswith("placement_")
            or error.reason == "resolver_unavailable"
        ):
            self.observation_failure = getattr(error, "source_reason", error.reason)

    def tighten_after_denial(self, *, now: datetime) -> None:
        """资格缺口只拒绝当次;已知漂移/来源失信才持久收紧。"""
        projection = self.projection
        known_drift = projection is not None and any(
            reason.code
            in {
                ReasonCode.LEDGER_UNTRUSTED,
                ReasonCode.EVIDENCE_CONFLICT,
                ReasonCode.BINDING_DRIFT,
                ReasonCode.MATERIAL_MISMATCH,
            }
            for reason in projection.decision.reasons
        )
        if not known_drift and self.observation_failure in {
            "observation_stale",
            "observation_unavailable",
            "clock_rollback",
            "evidence_time_invalid",
            "evidence_time_future",
            "placement_unavailable",
            "placement_handshake_timeout",
        }:
            return
        projection = self.projection
        if (
            self.observation_failure is None
            and projection is not None
            and not projection.decision.executable
            and not any(
                reason.code
                in {
                    ReasonCode.LEDGER_UNTRUSTED,
                    ReasonCode.EVIDENCE_CONFLICT,
                    ReasonCode.BINDING_DRIFT,
                    ReasonCode.MATERIAL_MISMATCH,
                }
                for reason in projection.decision.reasons
            )
        ):
            return
        self.tighten(now=now)

    def tighten(
        self, *, now: datetime, failed_capabilities: frozenset[Capability] | None = None
    ) -> None:
        """失去来源时使用先前已读来源;helper/意图失败仍保持调用方拒绝。"""
        projection = self.projection
        components: set[BindingComponent] = set(self.observation_components)
        failed: set[Capability] = set(failed_capabilities or ())
        if projection is not None and failed_capabilities is None:
            for assessment in projection.decision.capabilities:
                if assessment.requirement is Requirement.REQUIRED and any(
                    reason.code
                    in {ReasonCode.BINDING_DRIFT, ReasonCode.MATERIAL_MISMATCH}
                    for reason in assessment.reasons
                ):
                    failed.add(assessment.capability)
                for reason in assessment.reasons:
                    if (
                        reason.code is ReasonCode.BINDING_DRIFT
                        and reason.component is not None
                    ):
                        components.add(reason.component)
        grouped: dict[str, set[Capability]] = {}
        for capability, source in self.sources.items():
            if not failed or capability in failed:
                grouped.setdefault(source, set()).add(capability)
        use_id = use_id_for(self.use)
        if not grouped:
            with suppress(LedgerError, OSError):
                request_use_revocation(use_id, now=now)
            return
        for source, capabilities in grouped.items():
            try:
                request_revocation(
                    source,
                    use_id,
                    now=now,
                    components=(
                        frozenset(components)
                        if components or failed_capabilities is not None
                        else None
                    ),
                    failed_capabilities=frozenset(capabilities),
                )
            except (LedgerError, OSError):
                # 无法持久收紧不是授予;原错误仍向调用方传播。
                continue
