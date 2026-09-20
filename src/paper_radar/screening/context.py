"""Screening 输出验证使用的只读业务上下文。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ValuePredictionContext(BaseModel):
    """一次价值预测验证所需的上游只读事实。"""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    enabled_topic_ids: frozenset[str]
    original_title_is_zh: bool
