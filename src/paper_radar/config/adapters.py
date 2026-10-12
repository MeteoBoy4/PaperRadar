"""Pi 的封闭配置权威与只读语义。不含执行器或阶段比较器。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator
from pydantic_core import PydanticCustomError

from paper_radar.config.errors import VALIDATION_GUIDANCE, ConfigValidationReason
from paper_radar.config.identity import canonical_json, sha256
from paper_radar.config.schema import valid_declared_version

ADAPTER_NAME = "pi-rpc"
SYSTEM_PROMPT_NAME = "pi-system"
ADAPTER_SEMANTICS_FORMAT_VERSION = 1
_PI_VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_RESOURCE_HASH = re.compile(r"^[0-9a-f]{64}$")
ThinkingLevel = Literal["off", "minimal", "low", "medium", "high", "xhigh", "max"]


def _tuple_or_passthrough(value: object) -> object:
    return tuple(value) if isinstance(value, list) else value


class _FrozenConfig(BaseModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, validate_default=True
    )


class PiSystemPrompt(_FrozenConfig):
    """V1 唯一显式资源是替换默认系统指令的完整 Prompt。"""

    kind: Literal["system_prompt"] = "system_prompt"
    name: Literal["pi-system"] = "pi-system"
    version: str
    sha256: str

    @field_validator("sha256")
    @classmethod
    def valid_hash(cls, value: str) -> str:
        if not _RESOURCE_HASH.fullmatch(value):
            reason = ConfigValidationReason.RESOURCE_HASH_INVALID.value
            raise PydanticCustomError(reason, VALIDATION_GUIDANCE[reason])
        return value

    @field_validator("version")
    @classmethod
    def valid_version(cls, value: str) -> str:
        return valid_declared_version(value)


class PiPolicy(_FrozenConfig):
    """固定 V1 策略。无可放宽的开关或可调 attempt 预算。"""

    version: Literal["bounded-rpc-v1"] = "bounded-rpc-v1"
    session: Literal["ephemeral_per_attempt"] = "ephemeral_per_attempt"
    agent_retry: Literal["disabled"] = "disabled"
    provider_retry: Literal["disabled"] = "disabled"
    compaction: Literal["disabled"] = "disabled"
    summarization: Literal["disabled"] = "disabled"
    session_persistence: Literal["disabled"] = "disabled"
    resource_discovery: Literal["disabled"] = "disabled"
    extra_model_turns: Literal["disabled"] = "disabled"
    mcp: Literal["disabled"] = "disabled"
    tools: tuple[()] = ()

    @field_validator("tools", mode="before")
    @classmethod
    def tool_list(cls, value: object) -> object:
        return _tuple_or_passthrough(value)


class PiAdapter(_FrozenConfig):
    """普通声明版本与执行版本独立。模型选择仍由 models 唯一决定。"""

    version: str
    backend: Literal["pi-rpc"] = "pi-rpc"
    pi_version: str
    adapter_version: str
    thinking_level: ThinkingLevel
    policy: PiPolicy = PiPolicy()
    resources: tuple[PiSystemPrompt]

    @field_validator("pi_version")
    @classmethod
    def exact_pi_version(cls, value: str) -> str:
        if not _PI_VERSION.fullmatch(value):
            reason = ConfigValidationReason.PI_VERSION_INVALID.value
            raise PydanticCustomError(reason, VALIDATION_GUIDANCE[reason])
        return value

    @field_validator("version", "adapter_version")
    @classmethod
    def valid_version(cls, value: str) -> str:
        return valid_declared_version(value)

    @field_validator("resources", mode="before")
    @classmethod
    def resource_list(cls, value: object) -> object:
        return _tuple_or_passthrough(value)

    def semantics(self, system_prompt_text: str) -> AdapterSemantics:
        return AdapterSemantics(
            self.backend, self.thinking_level, self.policy, system_prompt_text
        )


@dataclass(frozen=True, slots=True)
class AdapterSemantics:
    """去除声明标签和执行审计版本。保留有效指令及受控策略语义。"""

    backend: Literal["pi-rpc"]
    thinking_level: ThinkingLevel
    policy: PiPolicy
    system_prompt_text: str = field(repr=False)

    @property
    def system_prompt_sha256(self) -> str:
        return sha256(self.system_prompt_text.encode("utf-8"))

    @property
    def payload_json(self) -> str:
        return canonical_json(
            {
                "kind": "adapter_semantics",
                "format_version": ADAPTER_SEMANTICS_FORMAT_VERSION,
                "backend": self.backend,
                "thinking_level": self.thinking_level,
                "policy": self.policy.model_dump(mode="json"),
                "resources": [
                    {
                        "kind": "system_prompt",
                        "name": SYSTEM_PROMPT_NAME,
                        "text": self.system_prompt_text,
                        "sha256": self.system_prompt_sha256,
                    }
                ],
            }
        ).decode("utf-8")

    @property
    def semantics_id(self) -> str:
        return sha256(self.payload_json.encode("utf-8"))
