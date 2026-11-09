"""产品检查点共享权威及受控结算映射;收紧动作在业务事务外执行。"""

from datetime import datetime

from paper_radar.live_evidence.ledger import LedgerError
from paper_radar.live_evidence.reasons import ReasonCode
from paper_radar.live_evidence.receipt import UseId
from paper_radar.live_evidence.service import (
    AdmissionProjection,
    AdmissionRequest,
    request_revocation,
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

    def tighten(self, *, now: datetime) -> None:
        """失去来源时使用先前已读来源;helper/意图失败仍保持调用方拒绝。"""
        projection = self.projection
        components: set[BindingComponent] = set()
        failed: set[Capability] = set()
        if projection is not None:
            for assessment in projection.decision.capabilities:
                if (
                    assessment.requirement is Requirement.REQUIRED
                    and assessment.reasons
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
        # UseId 是闭合格名,不接受产品提供的自由参数。
        use_id: UseId
        key = (self.use.consumer.value, self.use.thinking_level.value)
        uses: dict[tuple[str, str], UseId] = {
            ("boundary", "low"): "boundary-low",
            ("boundary", "high"): "boundary-high",
            ("value", "low"): "value-low",
            ("value", "high"): "value-high",
            ("read", "low"): "read-low",
            ("read", "high"): "read-high",
        }
        use_id = uses[key]
        for source, capabilities in grouped.items():
            try:
                request_revocation(
                    source,
                    use_id,
                    now=now,
                    components=frozenset(components) if components else None,
                    failed_capabilities=frozenset(capabilities),
                )
            except (LedgerError, OSError):
                # 无法持久收紧不是授予;原错误仍向调用方传播。
                continue
