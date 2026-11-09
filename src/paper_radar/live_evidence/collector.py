"""β 采集结果转换为冻结回执;未观察的组件只给 unknown 摘要。"""

from dataclasses import dataclass
from datetime import datetime

from paper_radar.live_evidence.observation import CurrentObservation
from paper_radar.live_evidence.receipt import (
    ApprovedPlan,
    CaseResult,
    EvidenceReceipt,
    FailureRecord,
    ReceiptClaim,
    UseId,
    content_sha256,
    validate_against_plan,
)
from paper_radar.live_evidence.types import BindingComponent as B
from paper_radar.live_evidence.types import Capability as C
from paper_radar.live_evidence.types import EvidenceStatus as S
from paper_radar.pi_execution.site_binding import component_digest

SITE_CASES = (
    "metadata",
    "outside-read-denied",
    "cwd-write-denied",
    "install-write-denied",
    "attempt-write-allowed",
    "core-zero",
    "node-version",
)
# 明确站点能力映射;供应商能力与特权出站/observer 不从本地元数据推导。
_SITE_DEPENDENCIES = {
    C.AUTH_CACHE_CURRENT: {B.AUTH_CACHE_CURRENT},
    C.AUTH_CACHE_BASELINE: {B.AUTH_CACHE_BASELINE},
    C.CWD_ANCESTORS: {B.CWD_ANCESTORS},
    C.FILE_ISOLATION: {B.FILE_ISOLATION, B.ISOLATION_POLICY},
    C.ZERO_CORE: {B.CORE_LIMITS},
    C.APPORT_IDENTITY: {B.APPORT},
    C.SUPPLY_TREE: {B.SUPPLY, B.SUPPLY_TREE},
    C.INSTANCE_TREE: {B.INSTANCE, B.INSTANCE_TREE},
    C.PI_VERSION: {B.PI_VERSION, B.NODE_PLATFORM},
    C.LAUNCH_POLICY: {B.LAUNCH_POLICY},
    C.ISOLATION_POLICY: {B.ISOLATION_POLICY},
    C.HOST_RUNTIME: {B.HOST, B.BOOT, B.KERNEL, B.LANDLOCK_ABI},
}


@dataclass(frozen=True)
class SiteObservation:
    components: dict[B, str]
    checks: tuple[tuple[str, bool], ...]


def build_site_receipt(
    plan: ApprovedPlan,
    observed: SiteObservation,
    *,
    use_id: UseId,
    started_at: datetime,
    completed_at: datetime,
    use_ids: tuple[UseId, ...] | None = None,
) -> tuple[EvidenceReceipt, CurrentObservation]:
    """单轮,首失败停止;60秒观察不改变回执中的原验证时间。"""
    if plan.kind != "site_beta" or not observed.checks:
        raise ValueError("collector_plan_invalid")
    cases: list[CaseResult] = []
    failures: list[FailureRecord] = []
    for case_id, passed in observed.checks:
        cases.append(
            CaseResult(
                case_id=case_id,
                outcome="passed" if passed else "failed",
                auth_calls=0,
                model_calls=0,
                network_requests=0,
            )
        )
        if not passed:
            failures.append(
                FailureRecord(
                    case_id=case_id,
                    reason="resource_unavailable"
                    if case_id == "metadata"
                    else "isolation_failed",
                )
            )
            break
    checked = set(observed.components) - {B.IPV4_EGRESS, B.OBSERVER}
    isolation_passed = not failures and len(cases) == len(plan.cases)
    if not isolation_passed:
        checked -= {B.FILE_ISOLATION, B.CORE_LIMITS}
    binding = {
        component: observed.components.get(
            component, component_digest({"unobserved": component.value})
        )
        for component in B
    }
    claims: list[ReceiptClaim] = []
    for capability in C:
        dependencies = _SITE_DEPENDENCIES.get(capability)
        verified = dependencies is not None and dependencies <= checked
        if capability in {C.FILE_ISOLATION, C.ZERO_CORE, C.PI_VERSION}:
            verified = verified and isolation_passed
        claims.append(
            ReceiptClaim(
                capability=capability,
                use_id=use_id,
                case_id=cases[-1].case_id
                if verified
                and capability in {C.FILE_ISOLATION, C.ZERO_CORE, C.PI_VERSION}
                else cases[0].case_id,
                status=S.VERIFIED if verified else S.UNKNOWN,
                basis="site_probe" if verified else "not_observed",
                scope="current_site" if verified else "not_observed",
                verified_at=completed_at if verified else None,
                evidence_at=completed_at,
            )
        )
    selected_uses = use_ids or (use_id,)
    if len(set(selected_uses)) != len(selected_uses):
        raise ValueError("collector_use_duplicate")
    all_claims = tuple(
        claim.model_copy(update={"use_id": selected})
        for selected in selected_uses
        for claim in claims
    )
    receipt = EvidenceReceipt(
        format_version="v1",
        registry_version="live-admission-v1",
        plan_id=plan.plan_id,
        plan_sha256=content_sha256(plan),
        collector_sha256=plan.collector_sha256,
        round_number=1,
        started_at=started_at,
        completed_at=completed_at,
        binding=binding,
        cases=tuple(cases),
        failure_history=tuple(failures),
        claims=all_claims,
    )
    validate_against_plan(receipt, plan, now=completed_at)
    current = CurrentObservation(
        observed_at=completed_at,
        binding=binding,
        checked_components=tuple(component for component in B if component in checked),
    )
    return receipt, current
