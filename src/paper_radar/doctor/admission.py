"""同一准入事实的只读展示;不读取宿主、不授予或重新解释能力资格。"""

import json
from dataclasses import dataclass
from datetime import datetime

from paper_radar.doctor.service import Check, Result
from paper_radar.live_evidence.evidence import Applicability
from paper_radar.live_evidence.reasons import (
    AdmissionReason,
    ReasonCode,
    observation_reason_text,
)
from paper_radar.live_evidence.service import AdmissionProjection
from paper_radar.live_evidence.types import (
    AdmissionUse,
    Capability,
    EvidenceStatus,
    Requirement,
)


@dataclass(frozen=True, slots=True)
class AdmissionRow:
    capability: Capability
    use: AdmissionUse
    requirement: Requirement
    result: Result
    evidence: EvidenceStatus
    original_state: EvidenceStatus | None
    reasons: tuple[str, ...]
    basis: str | None
    scope: str | None
    evidence_at: datetime | None
    verified_at: datetime | None
    expires_at: datetime | None
    expired: bool | None
    received: bool
    evidence_active: bool
    revoked: bool
    applicability: Applicability
    qualified: bool
    source: str | None
    next_step: str


@dataclass(frozen=True, slots=True)
class UsageDisclosure:
    """已观测下界与 Pi 自报用量;缺失值保留 unknown,不能换算成零成本。"""

    request_lower_bound: int | None = None
    pi_tokens: int | None = None
    request_layer: str | None = None
    request_source: str | None = None
    request_window: str | None = None

    def __post_init__(self) -> None:
        if any(
            value is not None and (type(value) is not int or value < 0)
            for value in (self.request_lower_bound, self.pi_tokens)
        ):
            raise ValueError("usage_disclosure_invalid")


def _action(reasons: tuple[AdmissionReason, ...], fallback: str) -> str:
    # 仅按权威原因选择用户动作,不从展示文字推导资格。
    for reason in reasons:
        text = observation_reason_text(reason.code)
        if text:
            return text
    actions = (
        (
            ReasonCode.CLOCK_ROLLBACK,
            "核实 UTC 墙钟与账本水位线；修复回退后重试，不重计原验证时间。",
        ),
        (
            ReasonCode.LEDGER_UNTRUSTED,
            "请所有者核对受保护账本、观察来源的权限、完整性与新鲜度；禁止自动修复或重建。",
        ),
        (
            ReasonCode.EXPIRED,
            "由所有者另批重验；接收或再次激活不延长原验证期限，不自动重跑。",
        ),
        (
            ReasonCode.REVOKED,
            "原撤销保持不可逆；请所有者核对漂移并另取有效证据，不恢复旧激活。",
        ),
    )
    codes = {reason.code for reason in reasons}
    return next((action for code, action in actions if code in codes), fallback)


def admission_rows(projection: AdmissionProjection) -> tuple[AdmissionRow, ...]:
    """只映射权威给出的 requirement/qualified/reasons,不另维护能力清单。"""
    sources = dict(projection.sources)
    rows = []
    for item in projection.decision.capabilities:
        claim = item.claim
        required = item.requirement is Requirement.REQUIRED
        result = (
            Result.PASSED
            if not required or item.qualified
            else Result.MISSING
            if claim is None
            else Result.INVALID
        )
        step = (
            "当前绑定不适用；保留历史状态，不单独阻断。"
            if item.requirement is Requirement.NOT_APPLICABLE
            else "本项当前资格通过；每次执行仍重新核验。"
            if item.qualified
            else "保留 unknown 与原状态；仅在所有者授权计划内补充观察，不自动重跑。"
            if not required
            else (
                "先核对分项原因、绑定和期限；由所有者接收并明确证据激活，缺口保持阻断。"
            )
        )
        rows.append(
            AdmissionRow(
                item.capability,
                projection.decision.use,
                item.requirement,
                result,
                EvidenceStatus.VERIFIED if item.qualified else EvidenceStatus.UNKNOWN,
                claim.status if claim else None,
                tuple(reason.token for reason in item.reasons),
                claim.basis if claim else None,
                claim.scope if claim else None,
                claim.evidence_at if claim else None,
                claim.verified_at if claim else None,
                item.expires_at,
                item.expired,
                item.received,
                item.evidence_active,
                item.revoked,
                item.applicability,
                item.qualified,
                sources.get(item.capability),
                _action(item.reasons, step),
            )
        )
    return tuple(rows)


def _value(value: str | datetime | bool | None) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, bool):
        return str(value).lower()
    return json.dumps(value, ensure_ascii=False)


def render_admission_row(row: AdmissionRow) -> str:
    reason = ",".join(row.reasons) or (
        "qualified" if row.qualified else "not_applicable"
    )
    return (
        f"capability={row.capability.value} result={row.result.value} "
        f"evidence={row.evidence.value} original_state="
        f"{row.original_state.value if row.original_state else 'absent'} "
        f"requirement={row.requirement.value} "
        f"use={row.use.consumer.value}-{row.use.thinking_level.value} "
        f"call_site={row.use.call_site.value} "
        f"reason={reason} "
        f"basis={_value(row.basis)} scope={_value(row.scope)} "
        f"evidence_at={_value(row.evidence_at)} verified_at={_value(row.verified_at)} "
        f"expires_at={_value(row.expires_at)} expired={_value(row.expired)} "
        f"received={_value(row.received)} "
        f"evidence_active={_value(row.evidence_active)} "
        f"revoked={_value(row.revoked)} applicability={row.applicability.value} "
        f"qualified={_value(row.qualified)} source={_value(row.source)} "
        f"下一步：{row.next_step}"
    )


def render_admission_fragment(
    projection: AdmissionProjection, *, usage: UsageDisclosure | None = None
) -> str:
    """供 B/H 嵌入的中文片段,与论文列表及其容量计算无关。"""
    usage = usage or UsageDisclosure()
    request_lower_bound = (
        usage.request_lower_bound
        if usage.request_lower_bound is not None
        else "unknown"
    )
    decision = projection.decision
    use = decision.use
    reasons = ",".join(reason.token for reason in decision.reasons) or "admitted"
    observed_at = projection.observation.observed_at if projection.observation else None
    refreshed_at = projection.refresh.recorded_at if projection.refresh else None
    refresh_result = projection.refresh.result if projection.refresh else "unknown"
    header = (
        "执行能力与证据披露（不计入每日五项/全文三项论文容量）：\n"
        f"use={use.consumer.value}-{use.thinking_level.value} "
        f"call_site={use.call_site.value} registry={decision.registry_version} "
        f"executable={_value(decision.executable)} reason={reasons} "
        f"watermark={_value(projection.watermark)} "
        f"pending_revocation={_value(projection.pending_revocation)} "
        f"observed_at={_value(observed_at)} "
        f"refresh_result={refresh_result} "
        f"refresh_at={_value(refreshed_at)}\n"
        + " ".join(
            filter(
                None,
                (observation_reason_text(reason.code) for reason in decision.reasons),
            )
        )
        + "\n"
        f"请求可证下界={request_lower_bound} "
        "精确请求数=unknown "
        f"request_layer={_value(usage.request_layer)} "
        f"request_source={_value(usage.request_source)} "
        f"request_window={_value(usage.request_window)} "
        f"Pi token 用量={usage.pi_tokens if usage.pi_tokens else 'unknown'}；"
        "Pi 自报用量不证明精确请求数；隐藏重试/预热/刷新可能不可见；"
        "缺失或 totalTokens=0 不代表零成本。"
    )
    return "\n".join(
        (header, *(render_admission_row(row) for row in admission_rows(projection)))
    )


def projection_checks(projection: AdmissionProjection) -> tuple[Check, ...]:
    """全局准入结论决定必要项;分项片段始终独立披露。"""
    decision = projection.decision
    tokens = tuple(dict.fromkeys(reason.token for reason in decision.reasons))
    result = (
        Result.PASSED
        if decision.executable
        else Result.MISSING
        if tokens == ("evidence_missing",)
        else Result.INVALID
    )
    return (
        Check(
            "admission",
            result,
            ",".join(tokens) or "admitted",
            _action(
                decision.reasons,
                "按当前格与绑定核对分项；Live 证据接收和激活由所有者显式执行。",
            ),
        ),
        Check(
            "admission_evidence",
            Result.PASSED,
            "independent_disclosure",
            "披露型 unknown 不改变退出码；原状态和原因见分项。",
            required=False,
            detail=render_admission_fragment(projection),
        ),
    )
