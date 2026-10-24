"""Read 结构输出的权威 Pydantic 定义。"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from paper_radar.reading.value_types import ValueType


def _require_value_type(value: object) -> ValueType:
    if isinstance(value, ValueType):
        return value
    if type(value) is str:
        return ValueType(value)
    raise ValueError("价值类型必须使用字符串序列化值")


_StrictValueType = Annotated[ValueType, BeforeValidator(_require_value_type)]
_OneToFiveScore = Annotated[int, Field(ge=1, le=5)]


class _ReadModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, hide_input_in_errors=True
    )

    def __repr_args__(self) -> tuple[tuple[str | None, object], ...]:
        return ()


class EvidenceRef(_ReadModel):
    """精读分析对单条证据的引用。"""

    evidence_id: Annotated[str, Field(min_length=1)]


class SupportedStatement(_ReadModel):
    """具有证据引用的精读陈述。"""

    statement: str
    evidence: Annotated[list[EvidenceRef], Field(min_length=1)]


class ReusablePoint(_ReadModel):
    """共用自身证据引用的可复用内容及其使用方式。"""

    item: str
    how_to_reuse: str
    evidence: Annotated[list[EvidenceRef], Field(min_length=1)]


class ReadAnalysisOutput(_ReadModel):
    """Read 阶段的全文精读分析。"""

    output_language: Literal["zh", "en"]
    one_sentence_conclusion: str
    research_question: str
    methods_summary: str
    data_summary: str
    main_findings: list[SupportedStatement]
    research_value: _OneToFiveScore
    research_value_reason: SupportedStatement
    reuse_feasibility: _OneToFiveScore
    reuse_feasibility_reason: SupportedStatement
    required_adaptations: list[str]
    reusable_points: list[ReusablePoint]
    key_limitations: list[SupportedStatement]
    open_questions: list[str]
    value_types: Annotated[
        list[_StrictValueType], Field(description="精读分析允许返回的七类受控价值。")
    ]
    why_it_matters: str
    next_action: str
    degraded_content_warnings: list[str]
