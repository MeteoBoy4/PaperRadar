"""Screening 结果、来源与原因组合的唯一权威定义。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Annotated, Any, ClassVar, Literal, Self, Union

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    TypeAdapter,
    create_model,
    model_validator,
)


class ScreeningResult(StrEnum):
    """筛选建议、决定与失败投影共用的三态结果。"""

    ACCEPTED = "accepted"
    PENDING = "pending"
    DENIED = "denied"


class ScreeningSource(StrEnum):
    """产生建议、人工决定或只读失败投影的受控来源。"""

    SUGGESTION_RULE = "suggestion_rule"
    BLIND_CALIBRATION = "blind_calibration"
    REGULAR_REVIEW = "regular_review"
    DIRECT_MANUAL_DECISION = "direct_manual_decision"
    METADATA_ABANDONMENT = "metadata_abandonment"
    MANUAL_READ_REQUEST = "manual_read_request"
    FIXED_CALIBRATION_MEMBER_PROJECTION = "fixed_calibration_member_projection"
    FAILURE_QUEUE_PROJECTION = "failure_queue_projection"


class DecisionReason(StrEnum):
    """原方案 §7.5 固定的 16 个决定与处理原因。"""

    HIGH_RESEARCH_VALUE = "high_research_value"
    RESEARCH_AND_REUSE = "research_and_reuse"
    OUT_OF_SCOPE = "out_of_scope"
    BOUNDARY_UNCERTAIN = "boundary_uncertain"
    VALUE_REUSE_CONFLICT = "value_reuse_conflict"
    REUSE_UNKNOWN = "reuse_unknown"
    REUSE_ESCALATION_UNAVAILABLE = "reuse_escalation_unavailable"
    LOW_VALUE = "low_value"
    LOW_REUSE_FEASIBILITY = "low_reuse_feasibility"
    USER_JUDGMENT = "user_judgment"
    UNCLEAR_FROM_AVAILABLE_INPUT = "unclear_from_available_input"
    DEFER_JUDGMENT = "defer_judgment"
    OUTSIDE_CURRENT_FOCUS = "outside_current_focus"
    INSUFFICIENT_METADATA = "insufficient_metadata"
    MANUAL_READ_REQUEST = "manual_read_request"
    MODEL_FAILURE = "model_failure"


SCREENING_RESULT_DESCRIPTIONS_ZH = MappingProxyType(
    {
        ScreeningResult.ACCEPTED: "值得进入全文精读",
        ScreeningResult.PENDING: "当前证据不足或留待复核",
        ScreeningResult.DENIED: "停止新的自动下游处理",
    }
)

SCREENING_SOURCE_DESCRIPTIONS_ZH = MappingProxyType(
    {
        ScreeningSource.SUGGESTION_RULE: "建议规则",
        ScreeningSource.BLIND_CALIBRATION: "盲评",
        ScreeningSource.REGULAR_REVIEW: "普通复核",
        ScreeningSource.DIRECT_MANUAL_DECISION: "直接人工决定",
        ScreeningSource.METADATA_ABANDONMENT: "元数据人工放弃",
        ScreeningSource.MANUAL_READ_REQUEST: "人工精读请求",
        ScreeningSource.FIXED_CALIBRATION_MEMBER_PROJECTION: ("固定校准成员失败投影"),
        ScreeningSource.FAILURE_QUEUE_PROJECTION: "模型失败队列投影",
    }
)

DECISION_REASON_DESCRIPTIONS_ZH = MappingProxyType(
    {
        DecisionReason.HIGH_RESEARCH_VALUE: "研究价值高",
        DecisionReason.RESEARCH_AND_REUSE: "研究价值与复用可行性均达到规则要求",
        DecisionReason.OUT_OF_SCOPE: "超出研究边界",
        DecisionReason.BOUNDARY_UNCERTAIN: "研究边界无法确定",
        DecisionReason.VALUE_REUSE_CONFLICT: "研究价值与复用信号冲突",
        DecisionReason.REUSE_UNKNOWN: "摘要层复用可行性无法判断",
        DecisionReason.REUSE_ESCALATION_UNAVAILABLE: "复用升级所需合法摘录不可得",
        DecisionReason.LOW_VALUE: "研究价值低",
        DecisionReason.LOW_REUSE_FEASIBILITY: "复用可行性低",
        DecisionReason.USER_JUDGMENT: "用户判断值得精读",
        DecisionReason.UNCLEAR_FROM_AVAILABLE_INPUT: "现有输入不足以判断",
        DecisionReason.DEFER_JUDGMENT: "用户延后判断",
        DecisionReason.OUTSIDE_CURRENT_FOCUS: "不属于当前关注重点",
        DecisionReason.INSUFFICIENT_METADATA: "用户因必要元数据不足而放弃",
        DecisionReason.MANUAL_READ_REQUEST: "用户明确请求全文精读",
        DecisionReason.MODEL_FAILURE: "模型在当前输入上未产生合法结果",
    }
)


@dataclass(frozen=True, slots=True)
class DecisionReasonDefinition:
    """一个原因对应的唯一结果及全部合法来源。"""

    result: ScreeningResult
    sources: frozenset[ScreeningSource]


_SUGGESTION = ScreeningSource.SUGGESTION_RULE
_HUMAN_DECISION_SOURCES = frozenset(
    {
        ScreeningSource.BLIND_CALIBRATION,
        ScreeningSource.REGULAR_REVIEW,
        ScreeningSource.DIRECT_MANUAL_DECISION,
    }
)

DECISION_REASON_DEFINITIONS = MappingProxyType(
    {
        DecisionReason.HIGH_RESEARCH_VALUE: DecisionReasonDefinition(
            ScreeningResult.ACCEPTED, frozenset({_SUGGESTION})
        ),
        DecisionReason.RESEARCH_AND_REUSE: DecisionReasonDefinition(
            ScreeningResult.ACCEPTED, frozenset({_SUGGESTION})
        ),
        DecisionReason.OUT_OF_SCOPE: DecisionReasonDefinition(
            ScreeningResult.DENIED, _HUMAN_DECISION_SOURCES | {_SUGGESTION}
        ),
        DecisionReason.BOUNDARY_UNCERTAIN: DecisionReasonDefinition(
            ScreeningResult.PENDING, frozenset({_SUGGESTION})
        ),
        DecisionReason.VALUE_REUSE_CONFLICT: DecisionReasonDefinition(
            ScreeningResult.PENDING, frozenset({_SUGGESTION})
        ),
        DecisionReason.REUSE_UNKNOWN: DecisionReasonDefinition(
            ScreeningResult.PENDING, frozenset({_SUGGESTION})
        ),
        DecisionReason.REUSE_ESCALATION_UNAVAILABLE: DecisionReasonDefinition(
            ScreeningResult.PENDING, frozenset({_SUGGESTION})
        ),
        DecisionReason.LOW_VALUE: DecisionReasonDefinition(
            ScreeningResult.DENIED, _HUMAN_DECISION_SOURCES | {_SUGGESTION}
        ),
        DecisionReason.LOW_REUSE_FEASIBILITY: DecisionReasonDefinition(
            ScreeningResult.DENIED, _HUMAN_DECISION_SOURCES | {_SUGGESTION}
        ),
        DecisionReason.USER_JUDGMENT: DecisionReasonDefinition(
            ScreeningResult.ACCEPTED, _HUMAN_DECISION_SOURCES
        ),
        DecisionReason.UNCLEAR_FROM_AVAILABLE_INPUT: DecisionReasonDefinition(
            ScreeningResult.PENDING, _HUMAN_DECISION_SOURCES
        ),
        DecisionReason.DEFER_JUDGMENT: DecisionReasonDefinition(
            ScreeningResult.PENDING, _HUMAN_DECISION_SOURCES
        ),
        DecisionReason.OUTSIDE_CURRENT_FOCUS: DecisionReasonDefinition(
            ScreeningResult.PENDING, _HUMAN_DECISION_SOURCES
        ),
        DecisionReason.INSUFFICIENT_METADATA: DecisionReasonDefinition(
            ScreeningResult.DENIED,
            frozenset({ScreeningSource.METADATA_ABANDONMENT}),
        ),
        DecisionReason.MANUAL_READ_REQUEST: DecisionReasonDefinition(
            ScreeningResult.ACCEPTED,
            frozenset({ScreeningSource.MANUAL_READ_REQUEST}),
        ),
        DecisionReason.MODEL_FAILURE: DecisionReasonDefinition(
            ScreeningResult.PENDING,
            frozenset(
                {
                    ScreeningSource.FIXED_CALIBRATION_MEMBER_PROJECTION,
                    ScreeningSource.FAILURE_QUEUE_PROJECTION,
                }
            ),
        ),
    }
)


def _require_enum_string[EnumType: StrEnum](
    value: object,
    enum_type: type[EnumType],
) -> object:
    if isinstance(value, enum_type) or type(value) is str:
        return value
    raise ValueError("受控值必须使用字符串序列化值")


StrictScreeningResult = Annotated[
    ScreeningResult,
    BeforeValidator(lambda value: _require_enum_string(value, ScreeningResult)),
]
StrictScreeningSource = Annotated[
    ScreeningSource,
    BeforeValidator(lambda value: _require_enum_string(value, ScreeningSource)),
]
StrictDecisionReason = Annotated[
    DecisionReason,
    BeforeValidator(lambda value: _require_enum_string(value, DecisionReason)),
]


class ScreeningReasonInput(BaseModel):
    """调用方提交的严格三字段原因组合。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    result: StrictScreeningResult
    source: StrictScreeningSource
    reason: StrictDecisionReason

    def invalid_combination_fields(
        self,
    ) -> tuple[Literal["result", "source"], ...]:
        """返回与当前原因的权威组合不一致的字段。"""
        definition = DECISION_REASON_DEFINITIONS[self.reason]
        invalid_fields: list[Literal["result", "source"]] = []
        if self.result is not definition.result:
            invalid_fields.append("result")
        if self.source not in definition.sources:
            invalid_fields.append("source")
        return tuple(invalid_fields)


class ScreeningReasonRecord(ScreeningReasonInput):
    """已通过组合规则校验的 Screening 原因记录。"""

    _identity_sources: ClassVar[frozenset[ScreeningSource] | None] = None

    @model_validator(mode="after")
    def _require_legal_combination_and_identity(self) -> Self:
        valid_combination = not self.invalid_combination_fields()
        valid_identity = (
            self._identity_sources is None or self.source in self._identity_sources
        )
        if not valid_combination or not valid_identity:
            raise ValueError("结果、来源与原因组合不合法")
        return self


class ScreeningSuggestion(ScreeningReasonRecord):
    """由确定性建议规则产生、可供后续流程使用的建议。"""

    _identity_sources = frozenset({ScreeningSource.SUGGESTION_RULE})


class ScreeningDecision(ScreeningReasonRecord):
    """由受控人工入口产生、可追加保存的筛选决定。"""

    _identity_sources = _HUMAN_DECISION_SOURCES | {
        ScreeningSource.METADATA_ABANDONMENT,
        ScreeningSource.MANUAL_READ_REQUEST,
    }


class ScreeningFailureProjection(ScreeningReasonRecord):
    """模型失败的只读 pending 投影。它不是建议或决定事件。"""

    _identity_sources = frozenset(
        {
            ScreeningSource.FIXED_CALIBRATION_MEMBER_PROJECTION,
            ScreeningSource.FAILURE_QUEUE_PROJECTION,
        }
    )


type ScreeningReason = (
    ScreeningSuggestion | ScreeningDecision | ScreeningFailureProjection
)


def _identity_model(source: ScreeningSource) -> type[ScreeningReasonRecord]:
    if source is ScreeningSource.SUGGESTION_RULE:
        return ScreeningSuggestion
    if source in ScreeningDecision._identity_sources:
        return ScreeningDecision
    if source in ScreeningFailureProjection._identity_sources:
        return ScreeningFailureProjection
    raise AssertionError("受控来源缺少记录身份")


def _combination_model(
    reason: DecisionReason,
    definition: DecisionReasonDefinition,
    source: ScreeningSource,
) -> type[ScreeningReasonRecord]:
    literal: Any = Literal
    model = create_model(
        "_".join(
            (
                "ReasonCombination",
                definition.result.value,
                source.value,
                reason.value,
            )
        ),
        __base__=_identity_model(source),
        result=(literal[definition.result], ...),
        source=(literal[source], ...),
        reason=(literal[reason], ...),
    )
    return model


_COMBINATION_MODELS = tuple(
    _combination_model(reason, definition, source)
    for reason, definition in DECISION_REASON_DEFINITIONS.items()
    for source in sorted(definition.sources, key=lambda item: item.value)
)
_union: Any = Union
_SCREENING_REASON_ADAPTER: TypeAdapter[ScreeningReason] = TypeAdapter(
    _union[_COMBINATION_MODELS]
)


def build_screening_reason(input_value: ScreeningReasonInput) -> ScreeningReason:
    """从已做结构校验的输入构造保留来源身份的权威类型。"""
    return _SCREENING_REASON_ADAPTER.validate_python(
        input_value.model_dump(mode="python")
    )


def screening_reason_json_schema() -> dict[str, Any]:
    """从权威组合类型生成表达全部合法三元组的 JSON Schema。"""
    return _SCREENING_REASON_ADAPTER.json_schema(mode="validation")
