"""Read v2 的完整候选接收;历史 v1 规则保持冻结。"""

import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Literal

from paper_radar.content_reliability import is_unreliable
from paper_radar.reading.context import (
    ExtractionIdentity,
    ReadContext,
    SourceSlice,
    valid_id,
)
from paper_radar.reading.errors import ReadContextError, ReadIssue, ReadOutputError
from paper_radar.reading.numbers import match_numbers
from paper_radar.reading.parsing import parse_candidate
from paper_radar.reading.schema import EvidenceRef, ReadAnalysisOutput
from paper_radar.screening.text import is_meaningful_text

EVIDENCE_RULE_VERSION = "read-evidence-v2"
NUMERIC_RULE_VERSION = "read-numeric-v2"
CONTENT_LIMITATION_RULE_VERSION = "read-content-limitation-v1"
DEGRADE_POLICY = "final_attempt"


class ReadV2Category(StrEnum):
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
    EVIDENCE_NOT_ALLOWED = "evidence_not_allowed"
    OUTPUT_WITHOUT_SUPPORT = "output_without_support"
    INVALID_DEGRADE_POLICY = "invalid_degrade_policy"
    INVALID_ATTEMPT_ORDINAL = "invalid_attempt_ordinal"


@dataclass(frozen=True, slots=True)
class ReadV2Issue:
    location: str
    category: ReadV2Category
    guidance_zh: str = "请按 Read v2 契约检查该位置的类型、来源或必填内容。"


class _ReadV2Error(ValueError):
    def __init__(self, issues: tuple[ReadV2Issue, ...]) -> None:
        self.issues = issues
        super().__init__(
            "；".join(
                f"{issue.location} [{issue.category.value}] {issue.guidance_zh}"
                for issue in issues
            )
        )


class ReadV2OutputError(_ReadV2Error):
    """完整模型候选拒绝;由任务层归为 output_invalid。"""


class ReadV2ContextError(_ReadV2Error):
    """调用方上下文、策略或序号错误;不得作为模型失败扣预算。"""


def _convert_issues(issues: tuple[ReadIssue, ...]) -> tuple[ReadV2Issue, ...]:
    return tuple(
        ReadV2Issue(i.location, ReadV2Category(i.category.value)) for i in issues
    )


def validate_read_context_v2(context: ReadContext) -> ReadContext:
    """领取前重验完整给定上下文;不授予真实来源、质量或用途资格。"""
    if type(context) is not ReadContext:
        raise ReadV2ContextError((ReadV2Issue("$", ReadV2Category.INVALID_CONTEXT),))
    issues: tuple[ReadV2Issue, ...] = ()
    checked = None
    try:
        checked = ReadContext(
            identity=context.identity,
            pages=context.pages,
            source_blocks=context.source_blocks,
            evidence=context.evidence,
            expected_language=context.expected_language,
            mode=context.mode,
            allowed_evidence=context.allowed_evidence,
        )
    except ReadContextError as error:
        issues = _convert_issues(error.issues)
    if issues:
        raise ReadV2ContextError(issues)
    assert checked is not None
    return checked


def _parse(raw: bytes) -> ReadAnalysisOutput:
    issues: tuple[ReadV2Issue, ...] = ()
    output = None
    try:
        output = parse_candidate(raw)
    except ReadOutputError as error:
        issues = _convert_issues(error.issues)
    if issues:
        raise ReadV2OutputError(issues)
    assert output is not None
    return output


def _meaningful(value: str) -> bool:
    return is_meaningful_text(value) and any(
        not c.isspace() and not unicodedata.category(c).startswith("P") for c in value
    )


def _whole_candidate_issues(
    output: ReadAnalysisOutput, context: ReadContext
) -> tuple[ReadV2Issue, ...]:
    issues: list[ReadV2Issue] = []
    texts = [
        ("$." + name, getattr(output, name))
        for name in (
            "one_sentence_conclusion",
            "research_question",
            "methods_summary",
            "data_summary",
            "why_it_matters",
            "next_action",
        )
    ]
    for name in ("required_adaptations", "open_questions", "degraded_content_warnings"):
        texts.extend(
            (f"$.{name}[{index}]", value)
            for index, value in enumerate(getattr(output, name))
        )
    for location, values, _, item_name, _ in _items(output):
        fields = (
            ("item", "how_to_reuse")
            if item_name == "reusable_points"
            else ("statement",)
        )
        texts.extend(
            (location + "." + key, value)
            for key, value in zip(fields, values, strict=True)
        )
    issues.extend(
        ReadV2Issue(location, ReadV2Category.INVALID_TEXT)
        for location, value in texts
        if not _meaningful(value)
    )
    if output.output_language != context.expected_language:
        issues.append(
            ReadV2Issue("$.output_language", ReadV2Category.LANGUAGE_MISMATCH)
        )
    if output.research_value >= 3 and not output.value_types:
        issues.append(ReadV2Issue("$.value_types", ReadV2Category.VALUE_TYPES_REQUIRED))
    for index, value in enumerate(output.value_types):
        if value in output.value_types[:index]:
            issues.append(
                ReadV2Issue(
                    f"$.value_types[{index}]", ReadV2Category.DUPLICATE_VALUE_TYPE
                )
            )
    return tuple(issues)


@dataclass(frozen=True, slots=True)
class ReadV2Position:
    source_id: str
    page_no: int
    bbox: tuple[float, float, float, float]
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class ReadV2Discard:
    location: str
    item_category: Literal["main_findings", "reusable_points", "key_limitations"]
    ordinal: int
    reason: ReadV2Category
    positions: tuple[ReadV2Position, ...] = ()


_ItemCategory = Literal["main_findings", "reusable_points", "key_limitations"]
_LIST_FIELDS: tuple[_ItemCategory, ...] = (
    "main_findings",
    "reusable_points",
    "key_limitations",
)


def _items(
    output: ReadAnalysisOutput,
) -> Iterator[tuple[str, list[str], list[EvidenceRef], _ItemCategory | None, int]]:
    for name in _LIST_FIELDS:
        for index, item in enumerate(getattr(output, name)):
            texts = (
                [item.item, item.how_to_reuse]
                if name == "reusable_points"
                else [item.statement]
            )
            yield f"$.{name}[{index}]", texts, item.evidence, name, index + 1
    for reason_name in ("research_value_reason", "reuse_feasibility_reason"):
        reason = getattr(output, reason_name)
        yield f"$.{reason_name}", [reason.statement], reason.evidence, None, 1


def _pointers(
    references: list[EvidenceRef], location: str, context: ReadContext
) -> tuple[ReadV2Issue, ...]:
    known = {item.evidence_id for item in context.evidence}
    allowed = (
        set(context.allowed_evidence.evidence_ids)
        if context.allowed_evidence is not None
        else known
    )
    issues: list[ReadV2Issue] = []
    seen: set[str] = set()
    for index, reference in enumerate(references):
        identifier = reference.evidence_id
        category = None
        if not valid_id(identifier):
            category = ReadV2Category.INVALID_EVIDENCE_ID
        elif identifier in seen:
            category = ReadV2Category.DUPLICATE_EVIDENCE
        elif identifier not in known:
            category = ReadV2Category.UNKNOWN_EVIDENCE
        elif identifier not in allowed:
            category = ReadV2Category.EVIDENCE_NOT_ALLOWED
        if category is not None:
            issues.append(
                ReadV2Issue(f"{location}.evidence[{index}].evidence_id", category)
            )
        seen.add(identifier)
    if context.mode == "reduce" and not any(
        reference.evidence_id in allowed for reference in references
    ):
        issues.append(
            ReadV2Issue(location + ".evidence", ReadV2Category.EVIDENCE_REQUIRED)
        )
    return tuple(issues)


class ReadV2DiagnosticReason(StrEnum):
    NUMBER_NOT_SUPPORTED = "number_not_supported"
    RANGE_NOT_SUPPORTED = "range_not_supported"
    UNIT_NOT_SUPPORTED = "unit_not_supported"
    UNRECOGNIZED_NUMERIC_FORM = "unrecognized_numeric_form"
    RESTRICTED_NUMERIC_SUPPORT = "restricted_numeric_support"
    RESTRICTED_SOURCE_REFERENCE = "restricted_source_reference"
    EVIDENCE_ITEM_DISCARDED = "evidence_item_discarded"


@dataclass(frozen=True, slots=True)
class ReadV2Diagnostic:
    location: str
    reason: ReadV2DiagnosticReason
    ordinal: int


@dataclass(frozen=True, slots=True)
class ReadV2Warning:
    origin: Literal["model", "program"]
    text: str = field(repr=False)
    diagnostic: ReadV2Diagnostic | None = None


def _positions(
    references: list[EvidenceRef],
    location: str,
    issues: tuple[ReadV2Issue, ...],
    context: ReadContext,
) -> tuple[ReadV2Position, ...]:
    bad_locations = {issue.location for issue in issues}
    identifiers = {
        ref.evidence_id
        for index, ref in enumerate(references)
        if f"{location}.evidence[{index}].evidence_id" in bad_locations
    }
    positions: list[ReadV2Position] = []
    for evidence in context.evidence:
        if evidence.evidence_id in identifiers:
            for prov in evidence.provenance:
                position = ReadV2Position(
                    prov.source_id, prov.page_no, prov.bbox, prov.start, prov.end
                )
                if position not in positions:
                    positions.append(position)
    return tuple(positions)


def _program_warning(diagnostic: ReadV2Diagnostic, language: str) -> ReadV2Warning:
    if diagnostic.reason is ReadV2DiagnosticReason.EVIDENCE_ITEM_DISCARDED:
        text = (
            f"{diagnostic.location} 因证据引用无效已丢弃；请核对原 PDF。"
            if language == "zh"
            else (
                f"{diagnostic.location} was discarded for invalid evidence references; "
                "verify the original PDF."
            )
        )
    else:
        text = (
            (
                f"请核对 {diagnostic.location}（{diagnostic.reason.value}）；"
                "受限内容或数值尚未核对。"
            )
            if language == "zh"
            else (
                f"Verify {diagnostic.location} ({diagnostic.reason.value}); "
                "content or numbers remain unverified."
            )
        )
    return ReadV2Warning("program", text, diagnostic)


def _warnings(
    original: ReadAnalysisOutput,
    support: tuple[SourceSlice, ...],
    dropped: dict[str, set[int]],
    discards: tuple[ReadV2Discard, ...],
    language: str,
) -> tuple[ReadV2Warning, ...]:
    diagnostics = [
        ReadV2Diagnostic(
            item.location,
            ReadV2DiagnosticReason.EVIDENCE_ITEM_DISCARDED,
            item.ordinal,
        )
        for item in discards
    ]
    for location, texts, references, name, ordinal in _items(original):
        if name is not None and ordinal - 1 in dropped[name]:
            continue
        identifiers = {ref.evidence_id for ref in references}
        slices = tuple(
            replace(part, unreliable=is_unreliable(part.text, declared=part.unreliable))
            for part in support
            if part.evidence_id in identifiers
        )
        fields = (
            ("item", "how_to_reuse") if name == "reusable_points" else ("statement",)
        )
        for key, text in zip(fields, texts, strict=True):
            path = location + "." + key
            if any(part.kind == "formula" or part.unreliable for part in slices):
                diagnostics.append(
                    ReadV2Diagnostic(
                        path, ReadV2DiagnosticReason.RESTRICTED_SOURCE_REFERENCE, 0
                    )
                )
            for match in match_numbers(text, slices):
                reason = match.reason.value if match.reason is not None else None
                if match.restricted_supported and not match.reliable_supported:
                    reason = ReadV2DiagnosticReason.RESTRICTED_NUMERIC_SUPPORT.value
                if reason is not None:
                    diagnostics.append(
                        ReadV2Diagnostic(
                            path, ReadV2DiagnosticReason(reason), match.ordinal
                        )
                    )
    diagnostics.sort(key=lambda d: (d.location, d.reason, d.ordinal))
    return tuple(_program_warning(d, language) for d in diagnostics)


@dataclass(frozen=True, slots=True)
class ReadV2Result:
    identity: ExtractionIdentity
    mode: Literal["single", "reduce"]
    degrade_policy: str
    attempt_ordinal: int
    evidence_rule_version: str
    numeric_rule_version: str
    content_limitation_rule_version: str
    _analysis_json: bytes = field(repr=False)
    discards: tuple[ReadV2Discard, ...] = ()
    model_warnings: tuple[str, ...] = field(default=(), repr=False)
    diagnostics: tuple[ReadV2Diagnostic, ...] = ()
    warnings: tuple[ReadV2Warning, ...] = ()
    support: tuple[SourceSlice, ...] = field(default=(), repr=False)

    @property
    def analysis(self) -> ReadAnalysisOutput:
        """返回独立处理视图;原始候选由持久消费者另行保存。"""
        return ReadAnalysisOutput.model_validate_json(self._analysis_json)


def validate_read_output_v2(
    raw: bytes,
    context: ReadContext,
    *,
    degrade_policy: str = DEGRADE_POLICY,
    attempt_ordinal: int,
) -> ReadV2Result:
    """按任务层领取序号接收完整候选;不推断末次或创建模型预算。"""
    if type(degrade_policy) is not str or degrade_policy != DEGRADE_POLICY:
        raise ReadV2ContextError(
            (
                ReadV2Issue(
                    "$.degrade_policy",
                    ReadV2Category.INVALID_DEGRADE_POLICY,
                    "降级策略仅支持 final_attempt；请使用任务层记录的策略。",
                ),
            )
        )
    if type(attempt_ordinal) is not int or attempt_ordinal not in (1, 2):
        raise ReadV2ContextError(
            (
                ReadV2Issue(
                    "$.attempt_ordinal",
                    ReadV2Category.INVALID_ATTEMPT_ORDINAL,
                    "本代接收序号必须是严格整数 1 或 2；请使用任务领取记录的序号。",
                ),
            )
        )
    context = validate_read_context_v2(context)
    output = _parse(raw)
    issues = _whole_candidate_issues(output, context)
    if issues:
        raise ReadV2OutputError(issues)
    had_subject_content = bool(output.main_findings or output.reusable_points)
    discards: list[ReadV2Discard] = []
    failures: list[ReadV2Issue] = []
    dropped: dict[str, set[int]] = {name: set() for name in _LIST_FIELDS}
    for location, _, references, name, ordinal in _items(output):
        issues = _pointers(references, location, context)
        if not issues:
            continue
        if attempt_ordinal != 2 or name is None:
            failures.extend(issues)
            continue
        dropped[name].add(ordinal - 1)
        discards.append(
            ReadV2Discard(
                location,
                name,
                ordinal,
                issues[0].category,
                _positions(references, location, issues, context),
            )
        )
    if failures:
        raise ReadV2OutputError(
            tuple(sorted(failures, key=lambda i: (i.location, i.category)))
        )
    original = output
    output = output.model_copy(
        update={
            name: [
                item
                for index, item in enumerate(getattr(output, name))
                if index not in dropped[name]
            ]
            for name in _LIST_FIELDS
        }
    )
    if had_subject_content and not (output.main_findings or output.reusable_points):
        raise ReadV2OutputError(
            (
                ReadV2Issue(
                    "$",
                    ReadV2Category.OUTPUT_WITHOUT_SUPPORT,
                    "主要发现与可复用点因证据无效均已清空；请修正引用并按任务预算重试。",
                ),
            )
        )
    support = context.replay()
    generated = _warnings(
        original, support, dropped, tuple(discards), output.output_language
    )
    model_warnings = tuple(output.degraded_content_warnings)
    output = output.model_copy(
        update={
            "degraded_content_warnings": [
                *model_warnings,
                *(warning.text for warning in generated),
            ]
        }
    )
    return ReadV2Result(
        context.identity,
        context.mode,
        degrade_policy,
        attempt_ordinal,
        EVIDENCE_RULE_VERSION,
        NUMERIC_RULE_VERSION,
        CONTENT_LIMITATION_RULE_VERSION,
        output.model_dump_json().encode(),
        discards=tuple(discards),
        model_warnings=model_warnings,
        diagnostics=tuple(w.diagnostic for w in generated if w.diagnostic is not None),
        warnings=(
            *tuple(ReadV2Warning("model", text) for text in model_warnings),
            *generated,
        ),
        support=support,
    )
