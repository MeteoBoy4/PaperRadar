"""Read 原始候选的单一公共纯接收入口。"""

import unicodedata
from collections.abc import Iterator

from paper_radar.reading.context import EVIDENCE_RULE_VERSION, ReadContext, valid_id
from paper_radar.reading.errors import (
    ReadContextError,
    ReadErrorCategory,
    ReadIssue,
    ReadOutputError,
)
from paper_radar.reading.numbers import (
    NUMERIC_RULE_VERSION,
    NumericReason,
    match_numbers,
)
from paper_radar.reading.parsing import parse_candidate
from paper_radar.reading.result import ReadDiagnostic, ReadValidationResult, ReadWarning
from paper_radar.reading.schema import EvidenceRef, ReadAnalysisOutput
from paper_radar.screening.text import is_meaningful_text


def protected_contents(
    output: ReadAnalysisOutput,
) -> Iterator[tuple[str, str, list[EvidenceRef]]]:
    """各受保护文本独立使用其自身引用;不合并可复用点两段文字。"""
    for field in ("main_findings", "key_limitations"):
        for index, item in enumerate(getattr(output, field)):
            yield f"$.{field}[{index}].statement", item.statement, item.evidence
    for field in ("research_value_reason", "reuse_feasibility_reason"):
        item = getattr(output, field)
        yield f"$.{field}.statement", item.statement, item.evidence
    for index, point in enumerate(output.reusable_points):
        for field in ("item", "how_to_reuse"):
            yield (
                f"$.reusable_points[{index}].{field}",
                getattr(point, field),
                point.evidence,
            )


def _meaningful(value: str) -> bool:
    return is_meaningful_text(value) and any(
        not c.isspace() and not unicodedata.category(c).startswith("P") for c in value
    )


def _business_issues(
    output: ReadAnalysisOutput, context: ReadContext
) -> list[ReadIssue]:
    issues: list[ReadIssue] = []
    for name in (
        "one_sentence_conclusion",
        "research_question",
        "methods_summary",
        "data_summary",
        "why_it_matters",
        "next_action",
    ):
        if not _meaningful(getattr(output, name)):
            issues.append(ReadIssue("$." + name, ReadErrorCategory.INVALID_TEXT))
    for name in ("required_adaptations", "open_questions", "degraded_content_warnings"):
        for index, value in enumerate(getattr(output, name)):
            if not _meaningful(value):
                issues.append(
                    ReadIssue(f"$.{name}[{index}]", ReadErrorCategory.INVALID_TEXT)
                )
    if output.output_language != context.expected_language:
        issues.append(
            ReadIssue("$.output_language", ReadErrorCategory.LANGUAGE_MISMATCH)
        )
    if output.research_value >= 3 and not output.value_types:
        issues.append(
            ReadIssue("$.value_types", ReadErrorCategory.VALUE_TYPES_REQUIRED)
        )
    for index, value in enumerate(output.value_types):
        if value in output.value_types[:index]:
            issues.append(
                ReadIssue(
                    f"$.value_types[{index}]", ReadErrorCategory.DUPLICATE_VALUE_TYPE
                )
            )
    known = {item.evidence_id for item in context.evidence}
    checked: set[str] = set()
    for location, text, references in protected_contents(output):
        if not _meaningful(text):
            issues.append(ReadIssue(location, ReadErrorCategory.INVALID_TEXT))
        reference_location = location.rsplit(".", 1)[0] + ".evidence"
        if reference_location in checked:
            continue
        checked.add(reference_location)
        seen: set[str] = set()
        for index, reference in enumerate(references):
            position = f"{reference_location}[{index}].evidence_id"
            identifier = reference.evidence_id
            if not valid_id(identifier):
                issues.append(
                    ReadIssue(position, ReadErrorCategory.INVALID_EVIDENCE_ID)
                )
            elif identifier in seen:
                issues.append(ReadIssue(position, ReadErrorCategory.DUPLICATE_EVIDENCE))
            elif identifier not in known:
                issues.append(ReadIssue(position, ReadErrorCategory.UNKNOWN_EVIDENCE))
            seen.add(identifier)
    return issues


def validate_read_output(raw: bytes, context: ReadContext) -> ReadValidationResult:
    if type(context) is not ReadContext:
        raise ReadContextError((ReadIssue("$", ReadErrorCategory.INVALID_CONTEXT),))
    output = parse_candidate(raw)
    issues = _business_issues(output, context)
    if issues:
        raise ReadOutputError(
            tuple(sorted(issues, key=lambda i: (i.location, i.category)))
        )
    support = context.replay()
    generated: list[ReadWarning] = []
    for location, text, references in protected_contents(output):
        identifiers = {reference.evidence_id for reference in references}
        slices = tuple(item for item in support if item.evidence_id in identifiers)
        limitation = location.startswith("$.key_limitations[")
        if not limitation and any(
            item.kind == "formula" or item.unreliable for item in slices
        ):
            issues.append(
                ReadIssue(
                    location,
                    ReadErrorCategory.RESTRICTED_SOURCE_REFERENCE,
                    "公式区域或不可靠源字符不能支持此类内容；请改引可靠正文或移入关键局限。",
                )
            )
        for match in match_numbers(text, slices):
            reason = match.reason
            if match.restricted_supported and not match.reliable_supported:
                if limitation:
                    reason = NumericReason.RESTRICTED_NUMERIC_SUPPORT
                else:
                    issues.append(
                        ReadIssue(
                            location,
                            ReadErrorCategory.RESTRICTED_NUMERIC_SUPPORT,
                            "该数值仅由受限片段支持；请改引可靠正文、去掉精确值或移入关键局限。",
                        )
                    )
            if reason is not None:
                diagnostic = ReadDiagnostic(location, reason, match.ordinal)
                source_guidance = (
                    "仅在受限片段中匹配；请核对原 PDF。"
                    if reason is NumericReason.RESTRICTED_NUMERIC_SUPPORT
                    else "所引片段未提供可匹配支持。"
                )
                source_guidance_en = (
                    "matched only in restricted spans; verify the original PDF."
                    if reason is NumericReason.RESTRICTED_NUMERIC_SUPPORT
                    else "cited spans do not provide matching support."
                )
                warning = (
                    (
                        f"请核对 {location} 的数值“{match.literal.text}”"
                        f"（{reason.value}）；{source_guidance}"
                    )
                    if context.expected_language == "zh"
                    else (
                        f"Please verify the number '{match.literal.text}' "
                        f"at {location} "
                        f"({reason.value}); {source_guidance_en}"
                    )
                )
                generated.append(ReadWarning("program", warning, diagnostic))
    generated.sort(
        key=lambda warning: (
            (
                warning.diagnostic.location,
                warning.diagnostic.reason,
                warning.diagnostic.ordinal,
            )
            if warning.diagnostic is not None
            else ("", "", 0)
        )
    )
    diagnostics = tuple(
        warning.diagnostic for warning in generated if warning.diagnostic is not None
    )
    if issues:
        raise ReadOutputError(
            tuple(
                sorted(
                    issues,
                    key=lambda issue: (
                        issue.category
                        is not ReadErrorCategory.RESTRICTED_SOURCE_REFERENCE,
                        issue.location,
                    ),
                )
            ),
            diagnostics=diagnostics,
        )
    model_warnings = tuple(output.degraded_content_warnings)
    processed = output.model_copy(
        update={
            "degraded_content_warnings": [
                *model_warnings,
                *(warning.text for warning in generated),
            ]
        }
    )
    return ReadValidationResult(
        context.identity,
        context.mode,
        EVIDENCE_RULE_VERSION,
        NUMERIC_RULE_VERSION,
        processed.model_dump_json().encode(),
        model_warnings,
        diagnostics,
        (*tuple(ReadWarning("model", text) for text in model_warnings), *generated),
        support,
    )
