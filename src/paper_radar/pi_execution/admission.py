"""只消费普通值的执行证据判定;无认证、保护或资源创建依赖。"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Literal, overload

if TYPE_CHECKING:
    from paper_radar.live_evidence.service import AdmissionProjection, AdmissionRequest

from paper_radar.llm.models import CallDescription
from paper_radar.pi_execution.errors import ExecutionReason


@dataclass(frozen=True, slots=True)
class EvidenceBinding:
    supply_id: str
    install_id: str
    launch_policy_version: str
    isolation_policy_version: str
    cwd_section: str = field(repr=False)
    provider: str = field(repr=False)
    model: str = field(repr=False)
    thinking_level: str = field(repr=False)
    sampling: Literal["explicit", "provider_default"]
    temperature: float | None = field(repr=False)
    top_p: float | None = field(repr=False)
    protocol_profile: str
    auth_mode: str


@dataclass(frozen=True, slots=True)
class AdmissionEvidence:
    binding: EvidenceBinding
    cwd_isolation: bool
    rpc_compatibility: bool
    model_parameters: bool


def bind_description(
    description: CallDescription,
    *,
    supply_id: str,
    install_id: str,
    launch_policy_version: str,
    isolation_policy_version: str,
    cwd_section: str,
    auth_mode: str,
) -> EvidenceBinding:
    return EvidenceBinding(
        supply_id,
        install_id,
        launch_policy_version,
        isolation_policy_version,
        cwd_section,
        description.provider,
        description.model,
        description.thinking_level,
        description.sampling,
        description.temperature,
        description.top_p,
        description.protocol_profile,
        auth_mode,
    )


@overload
def load_admission_evidence(binding: EvidenceBinding) -> AdmissionEvidence | None: ...


@overload
def load_admission_evidence(
    binding: AdmissionRequest, *, now: datetime
) -> AdmissionProjection: ...


def load_admission_evidence(
    binding: EvidenceBinding | AdmissionRequest, *, now: datetime | None = None
) -> AdmissionEvidence | AdmissionProjection | None:
    """完整请求延迟加载受保护账本;旧的不完整绑定继续安全拒绝。"""
    if isinstance(binding, EvidenceBinding):
        return None
    from paper_radar.live_evidence.service import (
        AdmissionRequest,
    )
    from paper_radar.live_evidence.service import (
        load_admission_evidence as load_projection,
    )

    if type(binding) is not AdmissionRequest or now is None:
        raise ValueError("admission_request_invalid")
    return load_projection(binding, now=now)


def admit(
    binding: EvidenceBinding, evidence: AdmissionEvidence | None
) -> ExecutionReason | None:
    """结构合法、可回放和本次可执行分别判断。当前显式映射表为空。"""
    if (
        binding.sampling != "provider_default"
        or binding.temperature is not None
        or binding.top_p is not None
    ):
        return "sampling_mapping_unavailable"
    if evidence is None:
        return "evidence_missing"
    if type(evidence) is not AdmissionEvidence or evidence.binding != binding:
        return "evidence_mismatch"
    if evidence.cwd_isolation is not True:
        return "cwd_evidence_missing"
    if evidence.rpc_compatibility is not True:
        return "rpc_evidence_missing"
    if evidence.model_parameters is not True:
        return "model_evidence_missing"
    return None
