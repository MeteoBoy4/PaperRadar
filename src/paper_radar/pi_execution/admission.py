"""只消费普通值的执行证据判定;无认证、保护或资源创建依赖。"""

from dataclasses import dataclass, field
from typing import Literal

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


def load_admission_evidence(binding: EvidenceBinding) -> AdmissionEvidence | None:
    """当前无经过 Cwd/Live 接收的事实来源;不从配置/JSON 接收通过声明。"""
    return None


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
