"""独立于 ExecutionReason 的受控准入原因;参数只接受闭合枚举。"""

from dataclasses import dataclass
from enum import StrEnum

from paper_radar.live_evidence.types import BindingComponent, Capability


class ReasonCode(StrEnum):
    LEDGER_UNTRUSTED = "ledger_untrusted"
    EVIDENCE_CONFLICT = "evidence_conflict"
    MATERIAL_MISMATCH = "material_mismatch"
    COVERAGE_INCOMPLETE = "coverage_incomplete"
    TIME_INVALID = "evidence_time_invalid"
    TIME_FUTURE = "evidence_time_future"
    CLOCK_ROLLBACK = "clock_rollback"
    EXPIRED = "evidence_expired"
    EVIDENCE_MISSING = "evidence_missing"
    CAPABILITY_REQUIRED = "capability_required"
    NOT_RECEIVED = "evidence_not_received"
    NOT_ACTIVATED = "evidence_not_activated"
    REVOKED = "evidence_revoked"
    NOT_APPLICABLE = "evidence_not_applicable"
    APPLICABILITY_UNKNOWN = "evidence_applicability_unknown"
    REGISTRY_VERSION = "registry_version_mismatch"
    USE_UNDEFINED = "admission_use_undefined"
    SCOPE_MISMATCH = "evidence_scope_mismatch"
    BINDING_DRIFT = "binding_drift"


@dataclass(frozen=True, slots=True)
class AdmissionReason:
    code: ReasonCode
    capability: Capability | None = None
    component: BindingComponent | None = None

    def __post_init__(self) -> None:
        if type(self.code) is not ReasonCode:
            raise ValueError("reason_code_invalid")
        if self.capability is not None and type(self.capability) is not Capability:
            raise ValueError("reason_capability_invalid")
        if self.component is not None and type(self.component) is not BindingComponent:
            raise ValueError("reason_component_invalid")
        if self.code is ReasonCode.BINDING_DRIFT:
            if self.component is None or self.capability is not None:
                raise ValueError("reason_parameter_invalid")
        elif self.component is not None:
            raise ValueError("reason_parameter_invalid")
        if self.code is ReasonCode.CAPABILITY_REQUIRED and self.capability is None:
            raise ValueError("reason_parameter_invalid")

    @property
    def token(self) -> str:
        if self.code is ReasonCode.BINDING_DRIFT:
            assert self.component is not None
            return f"{self.code.value}:{self.component.value}"
        if self.code is ReasonCode.CAPABILITY_REQUIRED:
            assert self.capability is not None
            return f"{self.code.value}:{self.capability.value}"
        return self.code.value
