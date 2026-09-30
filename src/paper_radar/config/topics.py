"""用户维护的严格主题集合与已启用语义。不包含投影身份。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator

from paper_radar.config.schema import valid_declared_version

_TOPIC_ID = re.compile(r"^[a-z][a-z0-9-]{0,63}$")


class TopicsStatus(StrEnum):
    CONFIGURED = "configured"
    UNCONFIGURED = "unconfigured"


class Topic(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: str
    name: str
    description: str
    enabled: bool

    @field_validator("id")
    @classmethod
    def valid_id(cls, value: str) -> str:
        if not _TOPIC_ID.fullmatch(value):
            raise ValueError("主题 ID 必须是受控小写 slug")
        return value

    @field_validator("name", "description")
    @classmethod
    def nonblank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("主题名称和描述必须非空")
        return value


@dataclass(frozen=True, slots=True)
class EnabledTopic:
    id: str
    name: str
    description: str


class Topics(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    version: str
    topics: list[Topic]

    @field_validator("version")
    @classmethod
    def valid_version(cls, value: str) -> str:
        return valid_declared_version(value)

    @field_validator("topics")
    @classmethod
    def unique_ids(cls, value: list[Topic]) -> list[Topic]:
        if len({topic.id for topic in value}) != len(value):
            raise ValueError("主题 ID 不得重复")
        return sorted(value, key=lambda topic: topic.id)

    @property
    def enabled_topics(self) -> tuple[EnabledTopic, ...]:
        return tuple(
            EnabledTopic(topic.id, topic.name, topic.description)
            for topic in self.topics
            if topic.enabled
        )
