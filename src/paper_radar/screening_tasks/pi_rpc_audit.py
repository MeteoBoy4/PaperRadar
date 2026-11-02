"""pi_rpc 持久审计的唯一格式 Schema。"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from paper_radar.pi_protocol import PROTOCOL_PROFILES

Version = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")]
ProgramVersion = Annotated[
    str, Field(pattern=r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
]
ReportedName = Annotated[str, Field(min_length=1, max_length=2048)]
TokenCount = Annotated[int, Field(ge=0)]


class _ExecutionIdentity(BaseModel):
    """启动组合提供的执行身份;不包含路径或任何认证材料。"""

    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, hide_input_in_errors=True
    )
    supply_id: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    install_id: Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")]
    pi_version: ProgramVersion
    node_version: ProgramVersion
    adapter_version: Version
    protocol_profile: Literal["pi-rpc-1.4.0-v1"]
    launch_policy_version: Version
    isolation_policy_version: Version
    auth_mode: Literal["chatgpt_subscription"]
    credential_provider: Literal["openai"]
    credential_source: Literal["owner_provisioned_dir"]
    proxy_used: bool
    proxy_port: Annotated[int, Field(ge=1, le=65535)] | None

    @model_validator(mode="after")
    def consistent(self) -> _ExecutionIdentity:
        if (self.proxy_port is not None) != self.proxy_used:
            raise ValueError("proxy state mismatch")
        if PROTOCOL_PROFILES.get(self.pi_version) != self.protocol_profile:
            raise ValueError("protocol profile mismatch")
        return self


class PiRpcExecutionAudit(_ExecutionIdentity):
    """当前执行审计元数据;通道字段与格式3一致。"""

    channel: Literal["prompt_only"]


class _CandidateFields(BaseModel):
    """nullable 字段仍必填。"""

    executor_kind: Literal["pi_rpc"]
    reported_provider: ReportedName
    reported_model: ReportedName
    provider_request_id: None
    input_tokens: TokenCount | None
    output_tokens: TokenCount | None


class PiRpcAudit(PiRpcExecutionAudit, _CandidateFields):
    """当前写入格式3;不接收旧字段或别名。"""

    format_version: Literal[3]


class LegacyPiRpcAudit(_ExecutionIdentity, _CandidateFields):
    """只读兼容已持久化的格式2;不迁移原审计或 submission_digest。"""

    format_version: Literal[2]
    protocol: Literal["prompt_only"]
