"""受限源在公共 Read 接收入口按字段裁决,合成定位不代表真实 PDF。"""

import json
from typing import Any, Literal

import pytest

from paper_radar.reading import (
    Evidence,
    Provenance,
    ReadContext,
    ReadContextError,
    ReadOutputError,
    SourceBlock,
    validate_read_output,
)
from tests.read_support import candidate, context_for

PROTECTED_FIELDS = (
    ("main_findings", "$.main_findings[0].statement"),
    ("research_value_reason", "$.research_value_reason.statement"),
    ("reuse_feasibility_reason", "$.reuse_feasibility_reason.statement"),
    ("item", "$.reusable_points[0].item"),
    ("how_to_reuse", "$.reusable_points[0].how_to_reuse"),
)


def restricted_context(
    source: str = "Table 3 compares vegetation schemes.",
    *,
    kind: Literal["text", "table", "formula"] = "table",
    unreliable: bool = False,
    reliable: str = "可靠的正文说明。",
) -> ReadContext:
    base = context_for(reliable)
    context: ReadContext = context_for(
        source_blocks=[
            *base.source_blocks,
            SourceBlock(base.identity, "restricted", source, kind, unreliable),
        ],
        evidence=[
            *base.evidence,
            Evidence(
                base.identity,
                "restricted",
                [Provenance("restricted", 3, (0, 0, 1, 1), 0, len(source))],
            ),
        ],
    )
    return context


def protected_candidate(
    field: str, statement: str, identifiers: tuple[str, ...] = ("restricted",)
) -> bytes:
    references = [{"evidence_id": identifier} for identifier in identifiers]
    changes: dict[str, Any]
    if field in ("main_findings", "key_limitations"):
        changes = {field: [{"statement": statement, "evidence": references}]}
    elif field in ("research_value_reason", "reuse_feasibility_reason"):
        changes = {field: {"statement": statement, "evidence": references}}
    else:
        point = {
            "item": "采用公开的方法。",
            "how_to_reuse": "比较可用方案。",
            "evidence": references,
        }
        point[field] = statement
        changes = {"reusable_points": [point]}
    return candidate(**changes)


@pytest.mark.parametrize(
    "field", [*(item[0] for item in PROTECTED_FIELDS), "key_limitations"]
)
def test_table_structure_can_support_protected_content_without_warning(
    field: str,
) -> None:
    raw = protected_candidate(field, "Table 3 按流域比较五种植被方案。")
    result = validate_read_output(raw, restricted_context())
    assert result.diagnostics == ()
    assert result.analysis.model_dump(mode="json") == json.loads(raw)
    assert result.support[-1].kind == "table"


@pytest.mark.parametrize(("field", "location"), PROTECTED_FIELDS)
def test_table_only_number_cannot_support_a_protected_judgement(
    field: str, location: str
) -> None:
    raw = protected_candidate(field, "增加了30%。")
    original = bytes(raw)
    with pytest.raises(ReadOutputError) as error:
        validate_read_output(raw, restricted_context("increased by 30%"))
    assert [(issue.location, issue.category.value) for issue in error.value.issues] == [
        (location, "restricted_numeric_support")
    ]
    assert raw == original


def test_table_only_number_in_a_limitation_degrades_and_preserves_analysis() -> None:
    raw = protected_candidate("key_limitations", "增加了30%。")
    result = validate_read_output(raw, restricted_context("increased by 30%"))
    assert [(d.location, d.reason.value, d.ordinal) for d in result.diagnostics] == [
        ("$.key_limitations[0].statement", "restricted_numeric_support", 0)
    ]
    assert result.analysis.key_limitations[0].statement == "增加了30%。"
    assert result.analysis.research_value == 3
    assert result.warnings[0].origin == "program"


@pytest.mark.parametrize(("kind", "unreliable"), [("formula", False), ("text", True)])
@pytest.mark.parametrize(("field", "location"), PROTECTED_FIELDS)
def test_formula_or_unreliable_reference_is_rejected_except_in_limitations(
    kind: Literal["text", "table", "formula"],
    unreliable: bool,
    field: str,
    location: str,
) -> None:
    context = restricted_context("受限所在可回查。", kind=kind, unreliable=unreliable)
    raw = protected_candidate(field, "该处说明了适用的方法。")
    with pytest.raises(ReadOutputError) as error:
        validate_read_output(raw, context)
    positions = (
        ["$.reusable_points[0].how_to_reuse", "$.reusable_points[0].item"]
        if field in ("item", "how_to_reuse")
        else [location]
    )
    assert [(issue.location, issue.category.value) for issue in error.value.issues] == [
        (position, "restricted_source_reference") for position in positions
    ]
    limitation = protected_candidate("key_limitations", "该处源字符尚未复核。")
    result = validate_read_output(limitation, context)
    assert result.diagnostics == ()
    assert result.analysis.key_limitations[0].statement == "该处源字符尚未复核。"


def test_rejection_collects_prioritized_violations_and_safe_degradations() -> None:
    refs = [{"evidence_id": "restricted"}]
    raw = candidate(
        main_findings=[{"statement": "变化为30% 与 20%。", "evidence": refs}],
        research_value_reason={"statement": "变化为30%。", "evidence": refs},
    )
    with pytest.raises(ReadOutputError) as error:
        validate_read_output(raw, restricted_context("30%", kind="formula"))
    assert [(issue.location, issue.category.value) for issue in error.value.issues] == [
        ("$.main_findings[0].statement", "restricted_source_reference"),
        ("$.research_value_reason.statement", "restricted_source_reference"),
        ("$.main_findings[0].statement", "restricted_numeric_support"),
        ("$.research_value_reason.statement", "restricted_numeric_support"),
    ]
    assert [
        (d.location, d.reason.value, d.ordinal) for d in error.value.diagnostics
    ] == [("$.main_findings[0].statement", "number_not_supported", 1)]
    assert "30" not in repr(error.value)
    assert "20" not in repr(error.value.diagnostics)


@pytest.mark.parametrize("statement", ["stable 3", "intersection 3"])
def test_words_ending_with_reference_prefixes_do_not_hide_numbers(
    statement: str,
) -> None:
    raw = protected_candidate("main_findings", statement, ("e1",))
    result = validate_read_output(raw, context_for())
    assert [(d.location, d.reason.value, d.ordinal) for d in result.diagnostics] == [
        ("$.main_findings[0].statement", "number_not_supported", 0)
    ]


@pytest.mark.parametrize("statement", ["Table 3", "Section 3"])
def test_complete_reference_prefixes_still_exclude_their_labels(statement: str) -> None:
    raw = protected_candidate("main_findings", statement, ("e1",))
    assert validate_read_output(raw, context_for()).diagnostics == ()


@pytest.mark.parametrize(
    ("field", "_location"),
    (*PROTECTED_FIELDS, ("key_limitations", "$.key_limitations[0].statement")),
)
def test_reliable_support_also_matching_the_table_number_is_accepted(
    field: str, _location: str
) -> None:
    context = restricted_context("30%", reliable="increased by 30%")
    raw = protected_candidate(field, "增加了30%。", ("e1", "restricted"))
    result = validate_read_output(raw, context)
    assert result.diagnostics == ()
    assert result.analysis.model_dump(mode="json") == json.loads(raw)


@pytest.mark.parametrize(
    ("kind", "unreliable"), [("table", False), ("formula", False), ("text", True)]
)
def test_limitation_only_restricted_number_degrades_for_every_restricted_kind(
    kind: Literal["text", "table", "formula"], unreliable: bool
) -> None:
    context = restricted_context("30%", kind=kind, unreliable=unreliable)
    raw = protected_candidate("key_limitations", "该数值为30%。")
    result = validate_read_output(raw, context)
    assert [(d.location, d.reason.value, d.ordinal) for d in result.diagnostics] == [
        ("$.key_limitations[0].statement", "restricted_numeric_support", 0)
    ]
    assert result.analysis.key_limitations[0].statement == "该数值为30%。"
    assert result == validate_read_output(raw, context)


@pytest.mark.parametrize(
    "field", [*(item[0] for item in PROTECTED_FIELDS), "key_limitations"]
)
def test_number_missing_from_all_table_slices_only_degrades(field: str) -> None:
    raw = protected_candidate(field, "变化为30%。")
    result = validate_read_output(raw, restricted_context("table structure"))
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].reason.value == "number_not_supported"
    assert result.analysis.research_value == 3
    assert result.analysis.reuse_feasibility == 3


def test_different_numbers_can_depend_on_different_source_classes() -> None:
    context = restricted_context("20%", reliable="30%")
    raw = protected_candidate("main_findings", "30% 与 20%", ("e1", "restricted"))
    with pytest.raises(ReadOutputError) as error:
        validate_read_output(raw, context)
    assert [(issue.location, issue.category.value) for issue in error.value.issues] == [
        ("$.main_findings[0].statement", "restricted_numeric_support")
    ]
    assert error.value.diagnostics == ()


def test_mixed_provenance_keeps_per_slice_numeric_support() -> None:
    base = restricted_context("30%", reliable="30%")
    combined = Evidence(
        base.identity,
        "mixed",
        [*base.evidence[0].provenance, *base.evidence[1].provenance],
    )
    context = context_for(
        source_blocks=base.source_blocks,
        evidence=[*base.evidence, combined],
    )
    result = validate_read_output(
        protected_candidate("main_findings", "30%", ("mixed",)), context
    )
    assert result.diagnostics == ()
    assert [(s.kind, s.text) for s in result.support if s.evidence_id == "mixed"] == [
        ("text", "30%"),
        ("table", "30%"),
    ]


@pytest.mark.parametrize(("kind", "unreliable"), [("formula", False), ("text", True)])
def test_any_formula_or_unreliable_provenance_rejects_even_with_reliable_numbers(
    kind: Literal["text", "table", "formula"], unreliable: bool
) -> None:
    base = restricted_context(
        "受限所在。", kind=kind, unreliable=unreliable, reliable="30%"
    )
    mixed = Evidence(
        base.identity,
        "mixed",
        [*base.evidence[0].provenance, *base.evidence[1].provenance],
    )
    context = context_for(
        source_blocks=base.source_blocks, evidence=[*base.evidence, mixed]
    )
    raw = protected_candidate("main_findings", "30%", ("mixed",))
    with pytest.raises(ReadOutputError) as error:
        validate_read_output(raw, context)
    assert [issue.category.value for issue in error.value.issues] == [
        "restricted_source_reference"
    ]


@pytest.mark.parametrize(
    "identifier",
    [
        "formula_candidate",
        "formula_placeholder",
        "image_placeholder",
        "generated_display",
    ],
)
def test_candidates_and_placeholders_are_not_provenance_targets(
    identifier: str,
) -> None:
    base = context_for()
    with pytest.raises(ReadContextError) as error:
        context_for(
            evidence=[
                Evidence(
                    base.identity,
                    "candidate",
                    [Provenance(identifier, 3, (0, 0, 1, 1), 0, 1)],
                )
            ]
        )
    assert [(issue.location, issue.category.value) for issue in error.value.issues] == [
        ("$.evidence[0].provenance[0].source_id", "unknown_source")
    ]


@pytest.mark.parametrize(
    ("kind", "unreliable"), [("table", False), ("formula", False), ("text", True)]
)
def test_unused_restricted_evidence_does_not_reject_other_claims(
    kind: Literal["text", "table", "formula"], unreliable: bool
) -> None:
    result = validate_read_output(
        candidate(), restricted_context(kind=kind, unreliable=unreliable)
    )
    assert result.diagnostics == ()


def test_table_label_exclusion_does_not_exempt_other_table_numbers() -> None:
    raw = protected_candidate("main_findings", "Table 3 比较12个流域。")
    with pytest.raises(ReadOutputError) as error:
        validate_read_output(raw, restricted_context("12 basins"))
    assert [issue.category.value for issue in error.value.issues] == [
        "restricted_numeric_support"
    ]
    result = validate_read_output(raw, restricted_context("Table 3 比较五个流域。"))
    assert [(d.reason.value, d.ordinal) for d in result.diagnostics] == [
        ("number_not_supported", 0)
    ]


def test_range_endpoints_cannot_be_joined_across_reliable_and_table_slices() -> None:
    context = restricted_context("5 km", reliable="3")
    raw = protected_candidate("main_findings", "3–5 km", ("e1", "restricted"))
    result = validate_read_output(raw, context)
    assert [(d.location, d.reason.value, d.ordinal) for d in result.diagnostics] == [
        ("$.main_findings[0].statement", "range_not_supported", 0)
    ]


def test_restricted_warning_uses_requested_language_and_keeps_model_origin() -> None:
    base = restricted_context("30%")
    context = context_for(
        source_blocks=base.source_blocks,
        evidence=base.evidence,
        expected_language="en",
    )
    warning = (
        "Please verify the number '30%' at $.key_limitations[0].statement "
        "(restricted_numeric_support); matched only in restricted spans; "
        "verify the original PDF."
    )
    raw = candidate(
        output_language="en",
        key_limitations=[
            {
                "statement": "The value is 30%.",
                "evidence": [{"evidence_id": "restricted"}],
            }
        ],
        degraded_content_warnings=[warning],
    )
    result = validate_read_output(raw, context)
    assert [(item.origin, item.text) for item in result.warnings] == [
        ("model", warning),
        ("program", warning),
    ]
    assert result.model_warnings == (warning,)
    assert len(result.diagnostics) == 1
    assert "30%" not in repr(result)
