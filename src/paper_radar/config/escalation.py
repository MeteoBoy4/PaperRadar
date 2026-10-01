"""复用升级参数和受控算法身份。不执行摘录选择或建议规则。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator

from paper_radar.config.schema import valid_declared_version


class ExcerptSelectorVersion(StrEnum):
    V1 = "v1"


class SuggestionRuleVersion(StrEnum):
    V1 = "v1"


@dataclass(frozen=True, slots=True)
class EscalationSemantics:
    reuse_escalation_research_values: tuple[int, ...]
    excerpt_priority: tuple[Literal["availability", "methods"], ...]
    excerpt_selector_version: ExcerptSelectorVersion
    suggestion_rule_version: SuggestionRuleVersion


class Escalation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, validate_default=True)

    version: str
    reuse_escalation_research_values: list[Annotated[StrictInt, Field(ge=1, le=5)]] = (
        Field(default_factory=lambda: [3], min_length=1)
    )
    excerpt_priority: list[Literal["availability", "methods"]]
    excerpt_selector_version: ExcerptSelectorVersion
    suggestion_rule_version: SuggestionRuleVersion

    @field_validator("version")
    @classmethod
    def valid_version(cls, value: str) -> str:
        return valid_declared_version(value)

    @field_validator("reuse_escalation_research_values")
    @classmethod
    def unique_research_values(cls, value: list[int]) -> list[int]:
        if len(set(value)) != len(value):
            raise ValueError("触发研究价值不得重复")
        return sorted(value)

    @field_validator("excerpt_priority")
    @classmethod
    def fixed_excerpt_priority(
        cls, value: list[Literal["availability", "methods"]]
    ) -> list[Literal["availability", "methods"]]:
        if value != ["availability", "methods"]:
            raise ValueError("V1 只支持 availability 优先于 methods")
        return value

    @field_validator("excerpt_selector_version", mode="before")
    @classmethod
    def supported_selector(cls, value: object) -> ExcerptSelectorVersion:
        if not isinstance(value, str):
            raise ValueError("摘录选择器必须是受控版本")
        return ExcerptSelectorVersion(value)

    @field_validator("suggestion_rule_version", mode="before")
    @classmethod
    def supported_rule(cls, value: object) -> SuggestionRuleVersion:
        if not isinstance(value, str):
            raise ValueError("建议规则必须是受控版本")
        return SuggestionRuleVersion(value)

    @property
    def semantics(self) -> EscalationSemantics:
        """供后续投影使用。不包含声明标签或原始字节哈希。"""
        return EscalationSemantics(
            tuple(self.reuse_escalation_research_values),
            tuple(self.excerpt_priority),
            self.excerpt_selector_version,
            self.suggestion_rule_version,
        )
