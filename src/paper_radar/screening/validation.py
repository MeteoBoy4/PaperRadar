"""Screening 结构输出的公共纯验证入口。"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import ValidationError

from paper_radar.screening.errors import (
    OutputErrorCategory,
    OutputValidationError,
    OutputValidationIssue,
)
from paper_radar.screening.kinds import OutputKind
from paper_radar.screening.schema import BoundaryOutput
from paper_radar.screening.text import is_meaningful_text

_KNOWN_BOUNDARY_FIELDS = frozenset(BoundaryOutput.model_fields)

_GUIDANCE: dict[OutputErrorCategory, str] = {
    OutputErrorCategory.UNKNOWN_KIND: "请使用已注册的输出种类。",
    OutputErrorCategory.INVALID_JSON: "请提交完整且语法正确的 JSON。",
    OutputErrorCategory.MISSING_FIELD: "请补充该必填字段。",
    OutputErrorCategory.EXTRA_FIELD: "请删除契约未定义的字段。",
    OutputErrorCategory.INVALID_TYPE: "请按契约使用正确的数据类型。",
    OutputErrorCategory.INVALID_ENUM: "请使用契约列出的受控值。",
    OutputErrorCategory.INVALID_TEXT: "请提供非空、非占位的有效文本。",
    OutputErrorCategory.MISSING_CONTEXT: "请提供该输出所需的只读上下文。",
    OutputErrorCategory.CONTEXT_MISMATCH: "请删除不适用于该输出的上下文。",
    OutputErrorCategory.BUSINESS_RULE: "请按该字段适用的业务规则修改输出。",
}


def _issue(location: str, category: OutputErrorCategory) -> OutputValidationIssue:
    return OutputValidationIssue(
        location=location,
        category=category,
        guidance_zh=_GUIDANCE[category],
    )


def _safe_location(parts: tuple[int | str, ...], category: OutputErrorCategory) -> str:
    if category is OutputErrorCategory.EXTRA_FIELD:
        return "$.<额外字段>"

    location = "$"
    for part in parts:
        if isinstance(part, int):
            location += f"[{part}]"
        elif part in _KNOWN_BOUNDARY_FIELDS:
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
    return OutputErrorCategory.INVALID_TYPE


def _issues_from_pydantic(error: ValidationError) -> tuple[OutputValidationIssue, ...]:
    issues: list[OutputValidationIssue] = []
    for detail in error.errors(include_url=False, include_context=False):
        category = _category_for_pydantic_error(detail)
        issues.append(_issue(_safe_location(detail["loc"], category), category))
    return tuple(issues)


def validate_output(
    kind: object,
    payload: object,
    context: object = None,
) -> BoundaryOutput:
    """验证输出的结构和适用业务规则后返回权威类型。"""
    if kind != OutputKind.BOUNDARY:
        raise OutputValidationError(
            (_issue("$.kind", OutputErrorCategory.UNKNOWN_KIND),)
        )
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
        validation_issues = _issues_from_pydantic(error)

    if validation_issues is not None:
        raise OutputValidationError(validation_issues)

    if not is_meaningful_text(output.reason_zh):
        raise OutputValidationError(
            (_issue("$.reason_zh", OutputErrorCategory.INVALID_TEXT),)
        )

    return output
