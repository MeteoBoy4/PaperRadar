"""纯配置选择与 Profile 契约。"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator

PROFILE_FIELDS = (
    "background",
    "core_questions",
    "transferable_methods",
    "available_data_and_tools",
    "theory_and_cognitive_interests",
    "constraints_and_exclusions",
)
_VERSION = re.compile(r"^[a-z][a-z0-9._-]{0,63}$")


class SlotStatus(StrEnum):
    CONFIGURED = "configured"
    UNCONFIGURED = "unconfigured"
    PLACEHOLDER = "placeholder"


class ModelSelectors(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    screening: str | None = None
    reuse_assessment: str | None = None
    reading: str | None = None


class PromptSelectors(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    boundary: str | None = None
    value: str | None = None
    reuse: str | None = None
    reading: str | None = None


class ContractSelectors(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    boundary: str | None = None
    value_prediction: str | None = None
    reuse_assessment: str | None = None
    decision_reasons: str | None = None


class Settings(BaseModel):
    """settings.yaml 只含选择。后续票逐种开放非空选择。"""

    model_config = ConfigDict(extra="forbid", strict=True)

    profile: str | None = None
    topics: str | None = None
    journals: str | None = None
    models: ModelSelectors = ModelSelectors()
    prompts: PromptSelectors = PromptSelectors()
    contracts: ContractSelectors = ContractSelectors()
    escalation: str | None = None
    extraction: str | None = None

    @field_validator("profile")
    @classmethod
    def valid_profile_version(cls, value: str | None) -> str | None:
        if value is not None and not _VERSION.fullmatch(value):
            raise ValueError("声明版本格式无效")
        return value


class Profile(BaseModel):
    """段落缺失表示未配置。所有已给段落必须是文本。"""

    model_config = ConfigDict(extra="forbid", strict=True)

    version: str
    background: str | None = None
    core_questions: str | None = None
    transferable_methods: str | None = None
    available_data_and_tools: str | None = None
    theory_and_cognitive_interests: str | None = None
    constraints_and_exclusions: str | None = None

    @field_validator("version")
    @classmethod
    def valid_version(cls, value: str) -> str:
        if not _VERSION.fullmatch(value):
            raise ValueError("声明版本格式无效")
        return value


def profile_field_status(value: str | None) -> SlotStatus:
    if value is None:
        return SlotStatus.UNCONFIGURED
    if value.strip() in ("", "..."):
        return SlotStatus.PLACEHOLDER
    return SlotStatus.CONFIGURED
