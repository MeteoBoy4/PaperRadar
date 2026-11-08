"""纯值判定;时钟与事实由调用方显式提供,不读宿主或账本。"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from paper_radar.live_evidence.evidence import (
    Applicability,
    CapabilityClaim,
    CapabilityEvidence,
    ExecutionBinding,
)
from paper_radar.live_evidence.reasons import AdmissionReason, ReasonCode
from paper_radar.live_evidence.registry import AdmissionRegistry
from paper_radar.live_evidence.time_policy import claim_time_reason, clock_reason
from paper_radar.live_evidence.types import (
    AdmissionUse,
    BindingComponent,
    Capability,
    EvidenceStatus,
    ExpiryClass,
    RegistryError,
    Requirement,
)


@dataclass(frozen=True, slots=True)
class CapabilityAssessment:
    capability: Capability
    requirement: Requirement
    claim: CapabilityClaim | None
    received: bool
    evidence_active: bool
    revoked: bool
    applicability: Applicability
    expires_at: datetime | None
    expired: bool | None
    reasons: tuple[AdmissionReason, ...]

    @property
    def qualified(self) -> bool:
        return self.requirement is not Requirement.NOT_APPLICABLE and not self.reasons

    @property
    def disclosure_unknown(self) -> bool:
        return self.requirement is Requirement.DISCLOSURE and not self.qualified


@dataclass(frozen=True, slots=True)
class AdmissionDecision:
    use: AdmissionUse
    registry_version: str
    capabilities: tuple[CapabilityAssessment, ...]
    reasons: tuple[AdmissionReason, ...]

    @property
    def executable(self) -> bool:
        return not self.reasons

    def for_capability(self, capability: Capability) -> CapabilityAssessment:
        return next(item for item in self.capabilities if item.capability is capability)


def evaluate_admission(
    registry: AdmissionRegistry,
    use: AdmissionUse,
    evidence: tuple[CapabilityEvidence, ...],
    *,
    binding: ExecutionBinding,
    now: datetime,
    checked_components: frozenset[BindingComponent] = frozenset(),
    ledger_watermark: datetime | None = None,
    privileged_components: frozenset[BindingComponent] = frozenset(),
    material_identity: str | None = None,
) -> AdmissionDecision:
    invalid_clock = clock_reason(now, ledger_watermark)
    if invalid_clock is not None:
        return AdmissionDecision(
            use, registry.version, (), (AdmissionReason(invalid_clock),)
        )
    try:
        rules = registry.requirements_for(use)
    except RegistryError:
        return AdmissionDecision(
            use, registry.version, (), (AdmissionReason(ReasonCode.USE_UNDEFINED),)
        )
    indexed: dict[tuple[AdmissionUse, Capability], CapabilityEvidence] = {}
    for candidate in evidence:
        time_error = claim_time_reason(candidate.claim, now)
        if time_error is not None:
            return AdmissionDecision(
                use, registry.version, (), (AdmissionReason(time_error),)
            )
        key = (candidate.use, candidate.capability)
        if key in indexed:
            return AdmissionDecision(
                use,
                registry.version,
                (),
                (AdmissionReason(ReasonCode.EVIDENCE_CONFLICT),),
            )
        indexed[key] = candidate
    assessments: list[CapabilityAssessment] = []
    blocking: list[AdmissionReason] = []
    for rule in rules:
        record = indexed.get((use, rule.capability))
        reasons: list[AdmissionReason] = []
        expires_at: datetime | None = None
        expired: bool | None = None
        if record is None:
            reasons.append(
                AdmissionReason(ReasonCode.EVIDENCE_MISSING, rule.capability)
            )
        else:
            if record.claim.status is not EvidenceStatus.VERIFIED:
                reasons.append(
                    AdmissionReason(ReasonCode.CAPABILITY_REQUIRED, rule.capability)
                )
            lifetime_days = rule.maximum_age_days
            if rule.expiry_class in {ExpiryClass.PROVIDER, ExpiryClass.UNCLASSIFIED}:
                lifetime_days = (
                    min(lifetime_days, 30) if lifetime_days is not None else 30
                )
            elif (
                not rule.dependencies <= checked_components | privileged_components
                and lifetime_days is None
            ):
                reasons.append(
                    AdmissionReason(ReasonCode.COVERAGE_INCOMPLETE, rule.capability)
                )
            if record.claim.verified_at is not None:
                expired = False
                if lifetime_days is not None:
                    expires_at = record.claim.verified_at.astimezone(UTC) + timedelta(
                        days=lifetime_days
                    )
                    expired = now >= expires_at
                    if expired:
                        reasons.append(
                            AdmissionReason(ReasonCode.EXPIRED, rule.capability)
                        )
            if not record.received:
                reasons.append(
                    AdmissionReason(ReasonCode.NOT_RECEIVED, rule.capability)
                )
            if not record.evidence_active:
                reasons.append(
                    AdmissionReason(ReasonCode.NOT_ACTIVATED, rule.capability)
                )
            if record.revoked:
                reasons.append(AdmissionReason(ReasonCode.REVOKED, rule.capability))
            if record.applicability is not Applicability.APPLICABLE:
                reasons.append(
                    AdmissionReason(
                        ReasonCode.NOT_APPLICABLE
                        if record.applicability is Applicability.NOT_APPLICABLE
                        else ReasonCode.APPLICABILITY_UNKNOWN,
                        rule.capability,
                    )
                )
            if record.registry_version != registry.version:
                reasons.append(
                    AdmissionReason(ReasonCode.REGISTRY_VERSION, rule.capability)
                )
            if record.use != use:
                reasons.append(
                    AdmissionReason(ReasonCode.SCOPE_MISMATCH, rule.capability)
                )
            if rule.material_dependent and (
                not material_identity or record.material_identity != material_identity
            ):
                reasons.append(
                    AdmissionReason(ReasonCode.MATERIAL_MISMATCH, rule.capability)
                )
            for component in sorted(rule.dependencies):
                if record.binding.value(component) != binding.value(component):
                    reasons.append(
                        AdmissionReason(ReasonCode.BINDING_DRIFT, component=component)
                    )
        if rule.requirement is Requirement.NOT_APPLICABLE:
            reasons = []
        assessment = CapabilityAssessment(
            rule.capability,
            rule.requirement,
            record.claim if record else None,
            record.received if record else False,
            record.evidence_active if record else False,
            record.revoked if record else False,
            record.applicability if record else Applicability.UNKNOWN,
            expires_at,
            expired,
            tuple(reasons),
        )
        assessments.append(assessment)
        if rule.requirement is Requirement.REQUIRED:
            blocking.extend(reasons)
    return AdmissionDecision(
        use, registry.version, tuple(assessments), tuple(dict.fromkeys(blocking))
    )
