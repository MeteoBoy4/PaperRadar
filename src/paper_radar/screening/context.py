"""Screening 输出验证使用的只读业务上下文。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ValuePredictionContext(BaseModel):
    """一次价值预测验证所需的上游只读事实。"""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    enabled_topic_ids: frozenset[str]
    original_title_is_zh: bool


class ReuseAssessmentContext(BaseModel):
    """一次复用升级验证所需的已归类摘录映射。"""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    excerpt_kinds: dict[str, Literal["availability", "methods"]] = Field(strict=True)
