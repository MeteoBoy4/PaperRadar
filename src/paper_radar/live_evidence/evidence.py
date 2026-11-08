"""普通值形式的原始能力主张与资格维度;不构造信任来源。"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from paper_radar.live_evidence.types import (
    AdmissionUse,
    BindingComponent,
    Capability,
    EvidenceStatus,
    RegistryError,
)


class Applicability(StrEnum):
    APPLICABLE = "applicable"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ExecutionBinding:
    components: tuple[tuple[BindingComponent, str], ...] = field(repr=False)

    def __post_init__(self) -> None:
        names = [component for component, _ in self.components]
        if len(names) != len(set(names)):
            raise RegistryError("binding_duplicate")
        if set(names) != set(BindingComponent) or any(
            not value for _, value in self.components
        ):
            raise RegistryError("binding_incomplete")

    def value(self, component: BindingComponent) -> str:
        return dict(self.components)[component]


@dataclass(frozen=True, slots=True)
class CapabilityClaim:
    status: EvidenceStatus
    basis: str = field(repr=False)
    scope: str = field(repr=False)
    verified_at: datetime | None = None
    evidence_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class CapabilityEvidence:
    capability: Capability
    use: AdmissionUse
    registry_version: str
    binding: ExecutionBinding
    claim: CapabilityClaim
    received: bool
    evidence_active: bool
    revoked: bool
    applicability: Applicability = Applicability.APPLICABLE
    material_identity: str | None = field(default=None, repr=False)
