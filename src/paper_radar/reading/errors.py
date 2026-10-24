"""Read 调用方上下文错误与模型输出拒绝的脱敏词汇。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from paper_radar.reading.diagnostics import ReadDiagnostic


class ReadErrorCategory(StrEnum):
    INVALID_CONTEXT = "invalid_context"
    INVALID_IDENTITY = "invalid_identity"
    DUPLICATE_ID = "duplicate_id"
    IDENTITY_MISMATCH = "identity_mismatch"
    INVALID_PAGE = "invalid_page"
    INVALID_SOURCE = "invalid_source"
    UNKNOWN_SOURCE = "unknown_source"
    UNKNOWN_PAGE = "unknown_page"
    INVALID_BBOX = "invalid_bbox"
    INVALID_CHARSPAN = "invalid_charspan"
    EMPTY_SUPPORT = "empty_support"
    DUPLICATE_PROVENANCE = "duplicate_provenance"
    UNSUPPORTED_SOURCE = "unsupported_source"
    UNSUPPORTED_MODE = "unsupported_mode"
    MISSING_ALLOWED_EVIDENCE = "missing_allowed_evidence"
    UNEXPECTED_ALLOWED_EVIDENCE = "unexpected_allowed_evidence"
    INVALID_ALLOWED_EVIDENCE = "invalid_allowed_evidence"
    UNKNOWN_ALLOWED_EVIDENCE = "unknown_allowed_evidence"
    INVALID_JSON = "invalid_json"
    MISSING_FIELD = "missing_field"
    EXTRA_FIELD = "extra_field"
    INVALID_TYPE = "invalid_type"
    INVALID_ENUM = "invalid_enum"
    INVALID_TEXT = "invalid_text"
    INVALID_SCORE = "invalid_score"
    LANGUAGE_MISMATCH = "language_mismatch"
    VALUE_TYPES_REQUIRED = "value_types_required"
    DUPLICATE_VALUE_TYPE = "duplicate_value_type"
    INVALID_EVIDENCE_ID = "invalid_evidence_id"
    DUPLICATE_EVIDENCE = "duplicate_evidence"
    UNKNOWN_EVIDENCE = "unknown_evidence"
    EVIDENCE_REQUIRED = "evidence_required"
    RESTRICTED_NUMERIC_SUPPORT = "restricted_numeric_support"
    RESTRICTED_SOURCE_REFERENCE = "restricted_source_reference"
    EVIDENCE_NOT_ALLOWED = "evidence_not_allowed"


@dataclass(frozen=True, slots=True)
class ReadIssue:
    location: str
    category: ReadErrorCategory
    guidance_zh: str = "请按 Read 公共契约检查该位置的类型、来源或必填内容。"


class ReadContextError(ValueError):
    """调用方材料错误;不属于模型输出失败。"""

    def __init__(self, issues: tuple[ReadIssue, ...]) -> None:
        self.issues = issues
        super().__init__(
            "；".join(
                f"{i.location} [{i.category.value}] {i.guidance_zh}" for i in issues
            )
        )


class ReadOutputError(ValueError):
    """模型候选被权威接收规则拒绝。"""

    def __init__(
        self,
        issues: tuple[ReadIssue, ...],
        *,
        diagnostics: tuple[ReadDiagnostic, ...] = (),
    ) -> None:
        self.issues = issues
        self.diagnostics = diagnostics
        super().__init__(
            "；".join(
                f"{i.location} [{i.category.value}] {i.guidance_zh}" for i in issues
            )
        )
