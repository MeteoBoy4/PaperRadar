"""Screening 输出验证使用的只读业务上下文。"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StrictStr

from paper_radar.screening.excerpt_kinds import ContextExcerptKind, ExcerptKind


def _freeze_excerpt_kinds(
    value: Mapping[str, ExcerptKind],
) -> Mapping[str, ExcerptKind]:
    if any(not excerpt_id.strip() for excerpt_id in value):
        raise ValueError("摘录 ID 必须是非空文本")
    return MappingProxyType(dict(value))


_FrozenExcerptKinds = Annotated[
    Mapping[StrictStr, ContextExcerptKind],
    AfterValidator(_freeze_excerpt_kinds),
]


class ValuePredictionContext(BaseModel):
    """一次价值预测验证所需的上游只读事实。"""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    enabled_topic_ids: frozenset[str]
    original_title_is_zh: bool


class ReuseAssessmentContext(BaseModel):
    """一次复用升级验证所需的已归类摘录映射。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    excerpt_kinds: _FrozenExcerptKinds = Field(strict=True)
