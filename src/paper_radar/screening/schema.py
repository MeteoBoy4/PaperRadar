"""Screening 结构输出的权威 Pydantic 定义。"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictBool,
    StrictStr,
)

from paper_radar.screening.value_types import ValueType


def _require_value_type_string(value: object) -> object:
    if isinstance(value, ValueType) or type(value) is str:
        return value
    raise ValueError("价值类型必须使用字符串序列化值")


_StrictValueType = Annotated[
    ValueType,
    BeforeValidator(_require_value_type_string),
]
_Score = Annotated[int, Field(strict=True, ge=1, le=5)]
_StrictStringList = Annotated[list[StrictStr], Field(strict=True)]


class BoundaryOutput(BaseModel):
    """Screening 第一阶段的研究边界判断。"""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    boundary: Literal["in_scope", "out_of_scope", "uncertain"]
    reason_zh: str


class ValuePredictionOutput(BaseModel):
    """Screening 第二阶段的摘要层价值预测。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    research_value: _Score
    research_value_reason_zh: StrictStr
    reuse_feasibility: _Score
    reuse_feasibility_reason_zh: StrictStr
    reuse_feasibility_inferable: StrictBool
    value_types: Annotated[list[_StrictValueType], Field(strict=True)]
    topic_ids: _StrictStringList
    display_title_zh: StrictStr | None = None
    abstract_brief_zh: StrictStr
    why_it_may_matter_zh: StrictStr
