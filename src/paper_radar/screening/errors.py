"""Screening 输出验证的稳定、脱敏错误词汇。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class OutputErrorCategory(StrEnum):
    """公共验证入口允许返回的受控错误类别。"""

    UNKNOWN_KIND = "unknown_kind"
    INVALID_JSON = "invalid_json"
    MISSING_FIELD = "missing_field"
    EXTRA_FIELD = "extra_field"
    INVALID_TYPE = "invalid_type"
    INVALID_ENUM = "invalid_enum"
    INVALID_TEXT = "invalid_text"
    MISSING_CONTEXT = "missing_context"
    CONTEXT_MISMATCH = "context_mismatch"
    BUSINESS_RULE = "business_rule"


@dataclass(frozen=True, slots=True)
class OutputValidationIssue:
    """单个不含调用方输入值的验证问题。"""

    location: str
    category: OutputErrorCategory
    guidance_zh: str


class OutputValidationError(ValueError):
    """公共输出验证失败。消息仅由脱敏问题生成。"""

    def __init__(self, issues: tuple[OutputValidationIssue, ...]) -> None:
        if not issues:
            raise ValueError("输出验证错误必须至少包含一个问题")
        self.issues = issues
        message = "；".join(
            f"{issue.location} [{issue.category.value}] {issue.guidance_zh}"
            for issue in issues
        )
        super().__init__(message)
