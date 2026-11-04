"""D1:完整原始候选到 v2 接收结果的公共边界。"""

from typing import Any, Literal

import pytest

from paper_radar.reading.acceptance_v2 import (
    ReadV2ContextError,
    ReadV2OutputError,
    validate_read_output_v2,
)
from tests.read_support import candidate, context_for


def test_valid_candidate_records_acceptance_policy_and_versions() -> None:
    result = validate_read_output_v2(candidate(), context_for(), attempt_ordinal=1)
    assert result.analysis.research_value == 3
    assert result.discards == ()
    assert (result.degrade_policy, result.attempt_ordinal) == ("final_attempt", 1)
    assert (
        result.evidence_rule_version,
        result.numeric_rule_version,
        result.content_limitation_rule_version,
    ) == ("read-evidence-v2", "read-numeric-v2", "read-content-limitation-v1")


def test_bad_pointer_requires_correction_before_final_attempt() -> None:
    import pytest

    from paper_radar.reading.acceptance_v2 import ReadV2OutputError

    bad = {"statement": "需要修正的结论。", "evidence": [{"evidence_id": "missing"}]}
    raw = candidate(main_findings=[bad])
    with pytest.raises(ReadV2OutputError) as caught:
        validate_read_output_v2(raw, context_for(), attempt_ordinal=1)
    assert [
        (issue.location, issue.category.value) for issue in caught.value.issues
    ] == [("$.main_findings[0].evidence[0].evidence_id", "unknown_evidence")]


def test_final_attempt_discards_whole_item_and_preserves_other_content() -> None:
    bad = {
        "statement": "需要修正的结论。",
        "evidence": [{"evidence_id": "e1"}, {"evidence_id": "missing"}],
    }
    good = {"statement": "保留的结论。", "evidence": [{"evidence_id": "e1"}]}
    result = validate_read_output_v2(
        candidate(main_findings=[bad, good]), context_for(), attempt_ordinal=2
    )
    assert [item.statement for item in result.analysis.main_findings] == [
        "保留的结论。"
    ]
    assert [
        (
            item.location,
            item.item_category,
            item.ordinal,
            item.reason.value,
            item.positions,
        )
        for item in result.discards
    ] == [("$.main_findings[0]", "main_findings", 1, "unknown_evidence", ())]


@pytest.mark.parametrize("field", ["research_value_reason", "reuse_feasibility_reason"])
@pytest.mark.parametrize("attempt", [1, 2])
def test_score_reason_bad_pointer_always_rejects(field: str, attempt: int) -> None:
    with pytest.raises(ReadV2OutputError) as caught:
        validate_read_output_v2(
            candidate(
                **{
                    field: {
                        "statement": "评分依据。",
                        "evidence": [{"evidence_id": "x"}],
                    }
                }
            ),
            context_for(),
            attempt_ordinal=attempt,
        )
    assert [(i.location, i.category.value) for i in caught.value.issues] == [
        (f"$.{field}.evidence[0].evidence_id", "unknown_evidence")
    ]


@pytest.mark.parametrize(
    ("change", "category", "location"),
    [
        (
            {"one_sentence_conclusion": "..."},
            "invalid_text",
            "$.one_sentence_conclusion",
        ),
        ({"output_language": "en"}, "language_mismatch", "$.output_language"),
        ({"value_types": []}, "value_types_required", "$.value_types"),
        (
            {"value_types": ["method", "method"]},
            "duplicate_value_type",
            "$.value_types[1]",
        ),
        ({"research_value": 6}, "invalid_score", "$.research_value"),
        ({"reuse_feasibility": True}, "invalid_type", "$.reuse_feasibility"),
    ],
)
def test_whole_candidate_errors_precede_pointer_degradation(
    change: dict[str, object],
    category: str,
    location: str,
) -> None:
    with pytest.raises(ReadV2OutputError) as caught:
        validate_read_output_v2(
            candidate(
                main_findings=[
                    {"statement": "待丢弃结论。", "evidence": [{"evidence_id": "bad"}]}
                ],
                **change,
            ),
            context_for(),
            attempt_ordinal=2,
        )
    assert [(i.location, i.category.value) for i in caught.value.issues] == [
        (location, category)
    ]


@pytest.mark.parametrize(
    ("field", "value", "category", "suffix"),
    [
        ("statement", "...", "invalid_text", ".statement"),
        ("evidence", [], "evidence_required", ".evidence"),
        (
            "evidence",
            [{"evidence_id": ""}],
            "invalid_evidence_id",
            ".evidence[0].evidence_id",
        ),
    ],
)
def test_drop_cannot_hide_bad_text_or_schema(
    field: str,
    value: object,
    category: str,
    suffix: str,
) -> None:
    item: dict[str, object] = {
        "statement": "待丢弃结论。",
        "evidence": [{"evidence_id": "bad"}],
    }
    item[field] = value
    with pytest.raises(ReadV2OutputError) as caught:
        validate_read_output_v2(
            candidate(main_findings=[item]), context_for(), attempt_ordinal=2
        )
    assert [(i.location, i.category.value) for i in caught.value.issues] == [
        ("$.main_findings[0]" + suffix, category)
    ]


def test_all_subject_content_removed_rejects_without_support() -> None:
    with pytest.raises(ReadV2OutputError) as caught:
        validate_read_output_v2(
            candidate(
                main_findings=[
                    {
                        "statement": "唯一结论。",
                        "evidence": [{"evidence_id": "bad"}],
                    }
                ]
            ),
            context_for(),
            attempt_ordinal=2,
        )
    assert [(i.location, i.category.value) for i in caught.value.issues] == [
        ("$", "output_without_support")
    ]


def test_only_limitations_removed_does_not_trigger_floor() -> None:
    result = validate_read_output_v2(
        candidate(
            key_limitations=[
                {
                    "statement": "局限。",
                    "evidence": [{"evidence_id": "bad"}],
                }
            ]
        ),
        context_for(),
        attempt_ordinal=2,
    )
    assert result.analysis.main_findings == []
    assert result.analysis.reusable_points == []
    assert result.analysis.key_limitations == []
    assert len(result.discards) == 1


@pytest.mark.parametrize(
    ("policy", "attempt", "category", "location"),
    [
        ("unknown", 1, "invalid_degrade_policy", "$.degrade_policy"),
        ("final_attempt", 0, "invalid_attempt_ordinal", "$.attempt_ordinal"),
        ("final_attempt", 3, "invalid_attempt_ordinal", "$.attempt_ordinal"),
        ("final_attempt", True, "invalid_attempt_ordinal", "$.attempt_ordinal"),
        ("final_attempt", "2", "invalid_attempt_ordinal", "$.attempt_ordinal"),
    ],
)
def test_task_owned_policy_and_ordinal_are_closed(
    policy: str,
    attempt: Any,
    category: str,
    location: str,
) -> None:
    with pytest.raises(ReadV2ContextError) as caught:
        validate_read_output_v2(
            candidate(), context_for(), degrade_policy=policy, attempt_ordinal=attempt
        )
    assert [(i.location, i.category.value) for i in caught.value.issues] == [
        (location, category)
    ]


@pytest.mark.parametrize(
    ("kind", "unreliable", "text", "expected"),
    [
        ("formula", False, "该结论得到支持。", ["restricted_source_reference"]),
        ("text", True, "该结论得到支持。", ["restricted_source_reference"]),
        ("table", False, "得到 12 km。", ["restricted_numeric_support"]),
        ("text", False, "得到 99 km。", ["number_not_supported"]),
    ],
)
def test_restricted_sources_and_numeric_limitations_only_warn(
    kind: Literal["text", "table", "formula"],
    unreliable: bool,
    text: str,
    expected: list[str],
) -> None:
    from paper_radar.reading import SourceBlock

    base = context_for("得到 12 km。")
    context = context_for(
        "得到 12 km。",
        source_blocks=[
            SourceBlock(
                base.identity, "s1", "得到 12 km。", kind=kind, unreliable=unreliable
            ),
        ],
    )
    result = validate_read_output_v2(
        candidate(
            main_findings=[
                {
                    "statement": text,
                    "evidence": [{"evidence_id": "e1"}],
                }
            ]
        ),
        context,
        attempt_ordinal=1,
    )
    finding = [
        d.reason.value
        for d in result.diagnostics
        if d.location.startswith("$.main_findings")
    ]
    assert finding == expected
    assert result.analysis.main_findings[0].statement == text
    assert result.analysis.degraded_content_warnings


def test_retained_content_warnings_and_literal_model_warnings() -> None:
    raw = candidate(
        main_findings=[
            {
                "statement": "待丢弃的 999 km。",
                "evidence": [{"evidence_id": "bad-secret"}],
            },
            {"statement": "保留的结论。", "evidence": [{"evidence_id": "e1"}]},
        ],
        degraded_content_warnings=["模型自报的警告。", "模型自报的警告。"],
    )
    result = validate_read_output_v2(raw, context_for(), attempt_ordinal=2)
    assert not any(d.reason.value.endswith("not_supported") for d in result.diagnostics)
    assert result.model_warnings == ("模型自报的警告。", "模型自报的警告。")
    assert [w.origin for w in result.warnings] == ["model", "model", "program"]
    for value in (
        repr(result),
        repr(result.discards),
        repr(result.diagnostics),
        repr(result.warnings),
    ):
        assert "bad-secret" not in value
        assert "999" not in value
        assert "模型自报" not in value
    result.analysis.main_findings.clear()
    assert len(result.analysis.main_findings) == 1


@pytest.mark.parametrize(
    ("references", "reason", "position_count"),
    [
        ([" e1"], "invalid_evidence_id", 0),
        (["e1\x00"], "invalid_evidence_id", 0),
        (["e1", "e1"], "duplicate_evidence", 1),
        (["formula-candidate"], "unknown_evidence", 0),
        (["image-placeholder"], "unknown_evidence", 0),
    ],
)
def test_each_bad_reference_discards_entire_reusable_point(
    references: list[str],
    reason: str,
    position_count: int,
) -> None:
    result = validate_read_output_v2(
        candidate(
            main_findings=[
                {"statement": "保留结论。", "evidence": [{"evidence_id": "e1"}]}
            ],
            reusable_points=[
                {
                    "item": "复用方法。",
                    "how_to_reuse": "应用于比较。",
                    "evidence": [{"evidence_id": ref} for ref in references],
                }
            ],
        ),
        context_for(),
        attempt_ordinal=2,
    )
    assert result.analysis.reusable_points == []
    assert (
        result.discards[0].item_category,
        result.discards[0].ordinal,
        result.discards[0].reason.value,
    ) == (
        "reusable_points",
        1,
        reason,
    )
    assert len(result.discards[0].positions) == position_count


def test_shared_bad_reference_drops_each_item_without_touching_good_references() -> (
    None
):
    bad = {"statement": "坏引用。", "evidence": [{"evidence_id": "bad"}]}
    good = {"statement": "合法引用。", "evidence": [{"evidence_id": "e1"}]}
    result = validate_read_output_v2(
        candidate(main_findings=[bad, good, bad], key_limitations=[bad]),
        context_for(),
        attempt_ordinal=2,
    )
    assert len(result.analysis.main_findings) == 1
    assert result.analysis.key_limitations == []
    assert [(d.item_category, d.ordinal) for d in result.discards] == [
        ("main_findings", 1),
        ("main_findings", 3),
        ("key_limitations", 1),
    ]


def test_retained_warning_path_keeps_original_candidate_index() -> None:
    result = validate_read_output_v2(
        candidate(
            main_findings=[
                {"statement": "丢弃。", "evidence": [{"evidence_id": "bad"}]},
                {"statement": "得到 12 km。", "evidence": [{"evidence_id": "e1"}]},
            ]
        ),
        context_for(),
        attempt_ordinal=2,
    )
    assert [(d.location, d.reason.value) for d in result.diagnostics] == [
        ("$.main_findings[0]", "evidence_item_discarded"),
        ("$.main_findings[1].statement", "number_not_supported"),
    ]


def test_reduce_not_allowed_discards_with_resolvable_safe_positions() -> None:
    from paper_radar.reading import AllowedEvidence, Evidence, Provenance

    base = context_for()
    context = context_for(
        mode="reduce",
        evidence=[
            *base.evidence,
            Evidence(
                base.identity, "e2", [Provenance("s1", 3, (0, 0, 600, 800), 0, 2)]
            ),
        ],
        allowed_evidence=AllowedEvidence(base.identity, ["e1"]),
    )
    result = validate_read_output_v2(
        candidate(
            key_limitations=[
                {
                    "statement": "越界局限。",
                    "evidence": [{"evidence_id": "e2"}],
                }
            ]
        ),
        context,
        attempt_ordinal=2,
    )
    discard = result.discards[0]
    assert (
        discard.reason.value,
        discard.positions[0].source_id,
        discard.positions[0].page_no,
        discard.positions[0].bbox,
        discard.positions[0].start,
        discard.positions[0].end,
    ) == (
        "evidence_not_allowed",
        "s1",
        3,
        (0, 0, 600, 800),
        0,
        2,
    )
    assert "e2" not in repr(discard)
    with pytest.raises(ReadV2OutputError) as caught:
        validate_read_output_v2(
            candidate(
                key_limitations=[
                    {
                        "statement": "越界局限。",
                        "evidence": [{"evidence_id": "e2"}],
                    }
                ]
            ),
            context,
            attempt_ordinal=1,
        )
    assert {i.category.value for i in caught.value.issues} == {
        "evidence_not_allowed",
        "evidence_required",
    }


@pytest.mark.parametrize("field", ["main_findings", "reusable_points"])
def test_floor_requires_either_main_findings_or_reusable_points_to_survive(
    field: str,
) -> None:
    item = {"statement": "丢弃。", "evidence": [{"evidence_id": "bad"}]}
    reusable = {
        "item": "丢弃。",
        "how_to_reuse": "丢弃。",
        "evidence": [{"evidence_id": "bad"}],
    }
    with pytest.raises(ReadV2OutputError) as caught:
        validate_read_output_v2(
            candidate(**{field: [reusable if field == "reusable_points" else item]}),
            context_for(),
            attempt_ordinal=2,
        )
    assert caught.value.issues[0].category.value == "output_without_support"


def test_fresh_generation_starts_at_one_and_cannot_inherit_discard_permission() -> None:
    raw = candidate(
        key_limitations=[{"statement": "局限。", "evidence": [{"evidence_id": "bad"}]}]
    )
    assert (
        len(validate_read_output_v2(raw, context_for(), attempt_ordinal=2).discards)
        == 1
    )
    with pytest.raises(ReadV2OutputError) as caught:
        validate_read_output_v2(raw, context_for(), attempt_ordinal=1)
    assert caught.value.issues[0].category.value == "unknown_evidence"


def test_executor_cannot_supply_or_override_attempt_ordinal_in_candidate() -> None:
    with pytest.raises(ReadV2OutputError) as caught:
        validate_read_output_v2(
            candidate(attempt_ordinal=2), context_for(), attempt_ordinal=1
        )
    assert [(i.location, i.category.value) for i in caught.value.issues] == [
        ("$.<额外字段>", "extra_field")
    ]


def test_unknown_source_is_context_failure_before_candidate_inspection() -> None:
    from paper_radar.reading import Evidence, Provenance

    context = context_for()
    # 模拟调用方破坏冻结上下文;合法构造本已提前拒绝该缺口。
    object.__setattr__(
        context,
        "evidence",
        (
            Evidence(
                context.identity,
                "e1",
                [
                    Provenance("absent-source-secret", 3, (0, 0, 2, 2), 0, 1),
                ],
            ),
        ),
    )
    with pytest.raises(ReadV2ContextError) as caught:
        validate_read_output_v2(b"not json", context, attempt_ordinal=2)
    assert [(i.location, i.category.value) for i in caught.value.issues] == [
        ("$.evidence[0].provenance[0].source_id", "unknown_source"),
    ]
    assert "absent-source-secret" not in str(caught.value)
    assert caught.value.__context__ is None


def test_unreliable_character_rule_matches_normalization_for_numeric_support() -> None:
    result = validate_read_output_v2(
        candidate(
            main_findings=[
                {
                    "statement": "得到 12 km。",
                    "evidence": [{"evidence_id": "e1"}],
                }
            ]
        ),
        context_for("得到 \ue000 12 km。"),
        attempt_ordinal=1,
    )
    assert {
        d.reason.value
        for d in result.diagnostics
        if d.location.startswith("$.main_findings")
    } == {
        "restricted_source_reference",
        "restricted_numeric_support",
    }
