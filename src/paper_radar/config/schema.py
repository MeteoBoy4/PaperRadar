"""纯配置选择与 Profile 契约。"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

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


MODEL_SLOTS = ("screening", "reuse_assessment", "reading")
MODEL_PLACEHOLDERS = frozenset(
    {"REQUIRED", "REQUIRED_FOR_FORMAL_CALIBRATION", "REQUIRED_FOR_READ"}
)


class ModelProtocol(StrEnum):
    JSON_SCHEMA = "json_schema"
    JSON_OBJECT = "json_object"
    PROMPT_ONLY = "prompt_only"


class ModelSlot(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    provider: str | None = None
    model: str | None = None
    protocol: ModelProtocol | None = None
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    top_p: float = Field(default=1.0, gt=0.0, le=1.0)

    @field_validator("protocol", mode="before")
    @classmethod
    def valid_protocol(cls, value: object) -> ModelProtocol | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("协议必须是受控文本")
        return ModelProtocol(value)


class Models(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    version: str
    screening: ModelSlot | None
    reuse_assessment: ModelSlot | None
    reading: ModelSlot | None

    @field_validator("version")
    @classmethod
    def valid_version(cls, value: str) -> str:
        if not _VERSION.fullmatch(value):
            raise ValueError("声明版本格式无效")
        return value


def model_slot_status(value: ModelSlot | None) -> SlotStatus:
    if value is None:
        return SlotStatus.UNCONFIGURED
    fields = (value.provider, value.model)
    if any(text is not None and text.strip() in MODEL_PLACEHOLDERS for text in fields):
        return SlotStatus.PLACEHOLDER
    if value.protocol is None or any(
        text is None or not text.strip() for text in fields
    ):
        return SlotStatus.UNCONFIGURED
    return SlotStatus.CONFIGURED


class PromptSelectors(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    boundary: str | None = None
    value: str | None = None
    reuse: str | None = None
    reading: str | None = None

    @field_validator("boundary", "value", "reuse", "reading")
    @classmethod
    def valid_version(cls, value: str | None) -> str | None:
        if value is not None and not _VERSION.fullmatch(value):
            raise ValueError("声明版本格式无效")
        return value


class ContractSelectors(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    boundary: str | None = None
    value_prediction: str | None = None
    reuse_assessment: str | None = None
    decision_reasons: str | None = None

    @field_validator(
        "boundary", "value_prediction", "reuse_assessment", "decision_reasons"
    )
    @classmethod
    def valid_version(cls, value: str | None) -> str | None:
        if value is not None and not _VERSION.fullmatch(value):
            raise ValueError("声明版本格式无效")
        return value


class Settings(BaseModel):
    """settings.yaml 只含选择。后续票逐种开放非空选择。"""

    model_config = ConfigDict(extra="forbid", strict=True)

    profile: str | None = None
    topics: str | None = None
    journals: str | None = None
    models: str | None = None
    prompts: PromptSelectors = PromptSelectors()
    contracts: ContractSelectors = ContractSelectors()
    escalation: str | None = None
    extraction: str | None = None

    @field_validator("profile", "models")
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
