"""用户维护的期刊身份与信誉集合。不参与阶段语义或就绪判断。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_core import PydanticCustomError

from paper_radar.config.errors import ConfigValidationReason
from paper_radar.config.schema import valid_declared_version

_ISSN = re.compile(r"^[0-9]{4}-?[0-9]{3}[0-9Xx]$")


class JournalTier(StrEnum):
    PREFERRED = "preferred"
    NORMAL = "normal"
    LOW = "low"


class JournalsStatus(StrEnum):
    CONFIGURED = "configured"
    UNCONFIGURED = "unconfigured"


def normalize_issn(value: str) -> str:
    if not _ISSN.fullmatch(value):
        raise PydanticCustomError(
            ConfigValidationReason.ISSN_FORMAT_INVALID.value, "ISSN 格式无效"
        )
    compact = value.replace("-", "").upper()
    checksum = sum(
        int(digit) * weight
        for digit, weight in zip(compact[:7], range(8, 1, -1), strict=True)
    )
    check_digit = 10 if compact[-1] == "X" else int(compact[-1])
    if (checksum + check_digit) % 11:
        raise PydanticCustomError(
            ConfigValidationReason.ISSN_CHECKSUM_INVALID.value, "ISSN 校验位无效"
        )
    return f"{compact[:4]}-{compact[4:]}"


@dataclass(frozen=True, slots=True)
class JournalSemantics:
    issn_l: str
    issns: tuple[str, ...]
    name: str
    tier: JournalTier


class Journal(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    issn_l: str
    issns: list[str] = Field(default_factory=list)
    name: str
    tier: JournalTier

    @field_validator("issn_l")
    @classmethod
    def valid_issn_l(cls, value: str) -> str:
        return normalize_issn(value)

    @field_validator("issns")
    @classmethod
    def valid_issns(cls, value: list[str]) -> list[str]:
        normalized = [normalize_issn(issn) for issn in value]
        if len(set(normalized)) != len(normalized):
            raise PydanticCustomError(
                ConfigValidationReason.JOURNAL_IDENTIFIERS_CONFLICT.value,
                "ISSN 列表不得重复",
            )
        return sorted(normalized)

    @field_validator("name")
    @classmethod
    def nonblank_name(cls, value: str) -> str:
        if not value.strip():
            raise PydanticCustomError(
                ConfigValidationReason.JOURNAL_NAME_EMPTY.value, "期刊名称必须非空"
            )
        return value

    @field_validator("tier", mode="before")
    @classmethod
    def valid_tier(cls, value: object) -> JournalTier:
        if not isinstance(value, str):
            raise PydanticCustomError(
                ConfigValidationReason.JOURNAL_TIER_INVALID.value,
                "期刊信誉必须是受控文本",
            )
        try:
            return JournalTier(value)
        except ValueError:
            raise PydanticCustomError(
                ConfigValidationReason.JOURNAL_TIER_INVALID.value, "期刊信誉档位无效"
            ) from None


class Journals(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    version: str
    journals: list[Journal]

    @field_validator("version")
    @classmethod
    def valid_version(cls, value: str) -> str:
        return valid_declared_version(value)

    @field_validator("journals")
    @classmethod
    def unique_identifiers(cls, value: list[Journal]) -> list[Journal]:
        seen: set[str] = set()
        for journal in value:
            identifiers = {journal.issn_l, *journal.issns}
            if seen & identifiers:
                raise PydanticCustomError(
                    ConfigValidationReason.JOURNAL_IDENTIFIERS_CONFLICT.value,
                    "跨期刊标识冲突",
                )
            seen.update(identifiers)
        return sorted(value, key=lambda journal: journal.issn_l)

    @property
    def semantics(self) -> tuple[JournalSemantics, ...]:
        return tuple(
            JournalSemantics(
                journal.issn_l, tuple(journal.issns), journal.name, journal.tier
            )
            for journal in self.journals
        )
