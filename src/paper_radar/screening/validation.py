"""Screening 结构输出的公共纯验证入口。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal, overload

from pydantic import ValidationError

from paper_radar.screening.context import ValuePredictionContext
from paper_radar.screening.errors import (
    OutputErrorCategory,
    OutputValidationError,
    OutputValidationIssue,
)
from paper_radar.screening.kinds import OutputKind
from paper_radar.screening.schema import BoundaryOutput, ValuePredictionOutput
from paper_radar.screening.text import is_meaningful_text, states_input_is_insufficient

_KNOWN_BOUNDARY_FIELDS = frozenset(BoundaryOutput.model_fields)
_KNOWN_VALUE_PREDICTION_FIELDS = frozenset(ValuePredictionOutput.model_fields)
_KNOWN_VALUE_CONTEXT_FIELDS = frozenset(ValuePredictionContext.model_fields)
_REQUIRED_VALUE_TEXT_FIELDS = (
    "research_value_reason_zh",
    "reuse_feasibility_reason_zh",
    "abstract_brief_zh",
    "why_it_may_matter_zh",
)

_GUIDANCE: dict[OutputErrorCategory, str] = {
    OutputErrorCategory.UNKNOWN_KIND: "请使用已注册的输出种类。",
    OutputErrorCategory.INVALID_JSON: "请提交完整且语法正确的 JSON。",
    OutputErrorCategory.MISSING_FIELD: "请补充该必填字段。",
    OutputErrorCategory.EXTRA_FIELD: "请删除契约未定义的字段。",
    OutputErrorCategory.INVALID_TYPE: "请按契约使用正确的数据类型。",
    OutputErrorCategory.INVALID_ENUM: "请使用契约列出的受控值。",
    OutputErrorCategory.INVALID_TEXT: "请提供非空、非占位的有效文本。",
    OutputErrorCategory.MISSING_CONTEXT: "请提供该输出所需的只读上下文。",
    OutputErrorCategory.CONTEXT_MISMATCH: "请使输出种类、字段与只读上下文保持一致。",
    OutputErrorCategory.BUSINESS_RULE: "请按该字段适用的业务规则修改输出。",
}


def _issue(location: str, category: OutputErrorCategory) -> OutputValidationIssue:
    return OutputValidationIssue(
        location=location,
        category=category,
        guidance_zh=_GUIDANCE[category],
    )


def _safe_location(
    parts: tuple[int | str, ...],
    category: OutputErrorCategory,
    known_fields: frozenset[str],
) -> str:
    if category is OutputErrorCategory.EXTRA_FIELD:
        return "$.<额外字段>"

    location = "$"
    for part in parts:
        if isinstance(part, int):
            location += f"[{part}]"
        elif part in known_fields:
            location += f".{part}"
        else:
            location += ".<额外字段>"
    return location


def _category_for_pydantic_error(error: Mapping[str, object]) -> OutputErrorCategory:
    error_type = error["type"]
    if error_type == "json_invalid":
        return OutputErrorCategory.INVALID_JSON
    if error_type == "missing":
        return OutputErrorCategory.MISSING_FIELD
    if error_type == "extra_forbidden":
        return OutputErrorCategory.EXTRA_FIELD
    if error_type == "literal_error":
        if isinstance(error.get("input"), str):
            return OutputErrorCategory.INVALID_ENUM
        return OutputErrorCategory.INVALID_TYPE
    if error_type in {"greater_than_equal", "less_than_equal"}:
        return OutputErrorCategory.BUSINESS_RULE
    if error_type == "enum":
        return OutputErrorCategory.INVALID_ENUM
    return OutputErrorCategory.INVALID_TYPE


def _issues_from_pydantic(
    error: ValidationError,
    known_fields: frozenset[str],
) -> tuple[OutputValidationIssue, ...]:
    issues: list[OutputValidationIssue] = []
    for detail in error.errors(include_url=False, include_context=False):
        category = _category_for_pydantic_error(detail)
        issues.append(
            _issue(_safe_location(detail["loc"], category, known_fields), category)
        )
    return tuple(issues)


def _value_prediction_business_issues(
    output: ValuePredictionOutput,
    context: ValuePredictionContext,
) -> tuple[OutputValidationIssue, ...]:
    issues: list[OutputValidationIssue] = []
    for field_name in _REQUIRED_VALUE_TEXT_FIELDS:
        if not is_meaningful_text(getattr(output, field_name)):
            issues.append(_issue(f"$.{field_name}", OutputErrorCategory.INVALID_TEXT))

    if output.display_title_zh is not None:
        if context.original_title_is_zh:
            issues.append(
                _issue(
                    "$.display_title_zh",
                    OutputErrorCategory.CONTEXT_MISMATCH,
                )
            )
        elif not is_meaningful_text(output.display_title_zh):
            issues.append(
                _issue("$.display_title_zh", OutputErrorCategory.INVALID_TEXT)
            )

    if (
        not output.reuse_feasibility_inferable
        and is_meaningful_text(output.reuse_feasibility_reason_zh)
        and not states_input_is_insufficient(output.reuse_feasibility_reason_zh)
    ):
        issues.append(
            _issue(
                "$.reuse_feasibility_reason_zh",
                OutputErrorCategory.BUSINESS_RULE,
            )
        )

    if output.research_value >= 3 and not output.value_types:
        issues.append(_issue("$.value_types", OutputErrorCategory.BUSINESS_RULE))

    seen_value_types: set[object] = set()
    for index, value_type in enumerate(output.value_types):
        if value_type in seen_value_types:
            issues.append(
                _issue(f"$.value_types[{index}]", OutputErrorCategory.BUSINESS_RULE)
            )
        seen_value_types.add(value_type)

    seen_topic_ids: set[str] = set()
    for index, topic_id in enumerate(output.topic_ids):
        if topic_id in seen_topic_ids or topic_id not in context.enabled_topic_ids:
            issues.append(
                _issue(f"$.topic_ids[{index}]", OutputErrorCategory.BUSINESS_RULE)
            )
        seen_topic_ids.add(topic_id)
    return tuple(issues)


def _validate_value_prediction_context(
    context: object,
) -> ValuePredictionContext:
    if context is None:
        raise OutputValidationError(
            (_issue("$.context", OutputErrorCategory.MISSING_CONTEXT),)
        )
    if isinstance(context, ValuePredictionContext):
        return context
    if not isinstance(context, Mapping):
        raise OutputValidationError(
            (_issue("$.context", OutputErrorCategory.CONTEXT_MISMATCH),)
        )

    controlled_context: ValuePredictionContext | None = None
    context_issues: tuple[OutputValidationIssue, ...] | None = None
    try:
        controlled_context = ValuePredictionContext.model_validate(dict(context))
    except ValidationError as error:
        issues: list[OutputValidationIssue] = []
        for detail in error.errors(include_url=False, include_context=False):
            is_missing = detail["type"] == "missing"
            category = (
                OutputErrorCategory.MISSING_CONTEXT
                if is_missing
                else OutputErrorCategory.CONTEXT_MISMATCH
            )
            location = "$.context"
            for part in detail["loc"]:
                if isinstance(part, int):
                    location += f"[{part}]"
                elif part in _KNOWN_VALUE_CONTEXT_FIELDS:
                    location += f".{part}"
                else:
                    location += ".<额外字段>"
            issues.append(_issue(location, category))
        context_issues = tuple(issues)

    if context_issues is not None:
        raise OutputValidationError(context_issues)
    assert controlled_context is not None
    return controlled_context


@overload
def validate_output(
    kind: Literal[OutputKind.BOUNDARY, "boundary"],
    payload: object,
    context: object = None,
) -> BoundaryOutput: ...


@overload
def validate_output(
    kind: Literal[OutputKind.VALUE_PREDICTION, "value_prediction"],
    payload: object,
    context: object = None,
) -> ValuePredictionOutput: ...


@overload
def validate_output(
    kind: object,
    payload: object,
    context: object = None,
) -> BoundaryOutput | ValuePredictionOutput: ...


def validate_output(
    kind: object,
    payload: object,
    context: object = None,
) -> BoundaryOutput | ValuePredictionOutput:
    """验证输出的结构和适用业务规则后返回权威类型。"""
    if kind not in (OutputKind.BOUNDARY, OutputKind.VALUE_PREDICTION):
        raise OutputValidationError(
            (_issue("$.kind", OutputErrorCategory.UNKNOWN_KIND),)
        )
    if kind == OutputKind.VALUE_PREDICTION:
        value_context = _validate_value_prediction_context(context)
        value_validation_issues: tuple[OutputValidationIssue, ...] | None = None
        try:
            if isinstance(payload, str | bytes | bytearray):
                value_output = ValuePredictionOutput.model_validate_json(payload)
            else:
                structured_payload = (
                    dict(payload) if isinstance(payload, Mapping) else payload
                )
                value_output = ValuePredictionOutput.model_validate(structured_payload)
        except ValidationError as error:
            value_validation_issues = _issues_from_pydantic(
                error,
                _KNOWN_VALUE_PREDICTION_FIELDS,
            )
        if value_validation_issues is not None:
            raise OutputValidationError(value_validation_issues)
        business_issues = _value_prediction_business_issues(
            value_output,
            value_context,
        )
        if business_issues:
            raise OutputValidationError(business_issues)
        return value_output

    if context is not None and (not isinstance(context, Mapping) or len(context) > 0):
        raise OutputValidationError(
            (_issue("$.context", OutputErrorCategory.CONTEXT_MISMATCH),)
        )

    validation_issues: tuple[OutputValidationIssue, ...] | None = None
    try:
        if isinstance(payload, str | bytes | bytearray):
            output = BoundaryOutput.model_validate_json(payload)
        else:
            structured_payload = (
                dict(payload) if isinstance(payload, Mapping) else payload
            )
            output = BoundaryOutput.model_validate(structured_payload)
    except ValidationError as error:
        validation_issues = _issues_from_pydantic(error, _KNOWN_BOUNDARY_FIELDS)

    if validation_issues is not None:
        raise OutputValidationError(validation_issues)

    if not is_meaningful_text(output.reason_zh):
        raise OutputValidationError(
            (_issue("$.reason_zh", OutputErrorCategory.INVALID_TEXT),)
        )

    return output
