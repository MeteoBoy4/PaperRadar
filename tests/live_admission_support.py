"""纯离线合成分项记录;不作为产品证据来源。"""

from datetime import UTC, datetime

from paper_radar.live_evidence.evidence import (
    CapabilityClaim,
    CapabilityEvidence,
    ExecutionBinding,
)
from paper_radar.live_evidence.registry import INITIAL_REGISTRY
from paper_radar.live_evidence.types import (
    AdmissionUse,
    BindingComponent,
    Capability,
    EvidenceStatus,
    Requirement,
)

VERIFIED_AT = datetime(2026, 1, 1, 12, 0, 0, 123456, tzinfo=UTC)
NOW = datetime(2026, 1, 2, 12, 0, 0, 123456, tzinfo=UTC)
USE = INITIAL_REGISTRY.uses[0].use
BINDING = ExecutionBinding(
    tuple((component, "synthetic-" + component.value) for component in BindingComponent)
)


def records(use: AdmissionUse = USE) -> tuple[CapabilityEvidence, ...]:
    return tuple(
        CapabilityEvidence(
            capability=rule.capability,
            use=use,
            registry_version=INITIAL_REGISTRY.version,
            binding=BINDING,
            claim=CapabilityClaim(
                status=EvidenceStatus.VERIFIED
                if rule.requirement is Requirement.REQUIRED
                else EvidenceStatus.NOT_ASSESSED,
                basis="synthetic basis",
                scope="synthetic scope",
                verified_at=VERIFIED_AT
                if rule.requirement is Requirement.REQUIRED
                else None,
                evidence_at=VERIFIED_AT,
            ),
            received=True,
            evidence_active=True,
            revoked=False,
        )
        for rule in INITIAL_REGISTRY.requirements_for(use)
    )


def item(
    evidence: tuple[CapabilityEvidence, ...], capability: Capability
) -> CapabilityEvidence:
    return next(record for record in evidence if record.capability is capability)
