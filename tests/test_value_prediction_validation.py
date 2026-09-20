from __future__ import annotations

import json
from collections.abc import Callable
from copy import deepcopy

import pytest

from paper_radar.screening import (
    INSUFFICIENT_INPUT_MARKERS,
    VALUE_TYPE_DESCRIPTIONS_ZH,
    OutputErrorCategory,
    OutputValidationError,
    ValuePredictionContext,
    ValuePredictionOutput,
    ValueType,
    validate_output,
)


def _valid_payload() -> dict[str, object]:
    return {
        "research_value": 4,
        "research_value_reason_zh": "该方法能改进区域降水诊断。",
        "reuse_feasibility": 3,
        "reuse_feasibility_reason_zh": "需要调整现有 ERA5 数据处理流程。",
        "reuse_feasibility_inferable": True,
        "value_types": ["method"],
        "topic_ids": ["extreme-rainfall"],
        "abstract_brief_zh": "研究提出一种新的极端降水诊断方法。",
        "why_it_may_matter_zh": "可用于改进当前的区域降水分析。",
    }


def _context() -> ValuePredictionContext:
    return ValuePredictionContext(
        enabled_topic_ids=frozenset({"extreme-rainfall"}),
        original_title_is_zh=False,
    )


def test_insufficient_input_markers_are_public_controlled_vocabulary() -> None:
    assert (
        frozenset(
            {
                "当前输入不足",
                "信息不足",
                "摘要未说明",
                "摘要未提供",
                "摘要未披露",
                "仅凭摘要无法判断",
                "无法从摘要判断",
                "insufficient information",
                "not reported in the abstract",
                "not provided in the abstract",
                "not disclosed in the abstract",
                "unclear from the abstract",
            }
        )
        == INSUFFICIENT_INPUT_MARKERS
    )


def test_validate_value_prediction_returns_authoritative_type_without_mutation() -> (
    None
):
    payload = _valid_payload()
    original = deepcopy(payload)

    result = validate_output("value_prediction", payload, context=_context())

    assert isinstance(result, ValuePredictionOutput)
    assert result.research_value == 4
    assert result.display_title_zh is None
    assert payload == original


def test_all_seven_value_types_have_fixed_serialization_and_chinese_descriptions() -> (
    None
):
    expected = {
        "method": "方法",
        "data": "数据",
        "code_tool": "代码/工具",
        "theory_mechanism": "理论/机制",
        "evidence_conclusion": "证据/结论",
        "question_hypothesis": "问题/假设",
        "review_knowledge_map": "综述/知识地图",
    }

    assert {value_type.value for value_type in ValueType} == set(expected)
    assert dict(VALUE_TYPE_DESCRIPTIONS_ZH) == expected
    for serialized_value in expected:
        payload = _valid_payload()
        payload["value_types"] = [serialized_value]
        result = validate_output("value_prediction", payload, context=_context())
        assert result.value_types == [ValueType(serialized_value)]


@pytest.mark.parametrize("field", ["research_value", "reuse_feasibility"])
@pytest.mark.parametrize(
    ("invalid_score", "category"),
    [
        (0, OutputErrorCategory.BUSINESS_RULE),
        (6, OutputErrorCategory.BUSINESS_RULE),
        (True, OutputErrorCategory.INVALID_TYPE),
        (False, OutputErrorCategory.INVALID_TYPE),
        (1.0, OutputErrorCategory.INVALID_TYPE),
        ("1", OutputErrorCategory.INVALID_TYPE),
    ],
)
def test_value_prediction_rejects_invalid_score_types_and_boundaries(
    field: str,
    invalid_score: object,
    category: OutputErrorCategory,
) -> None:
    payload = _valid_payload()
    payload[field] = invalid_score

    with pytest.raises(OutputValidationError) as captured:
        validate_output("value_prediction", payload, context=_context())

    assert len(captured.value.issues) == 1
    assert captured.value.issues[0].location == f"$.{field}"
    assert captured.value.issues[0].category is category


@pytest.mark.parametrize("research_value", [1, 2])
def test_low_research_value_allows_no_value_types(research_value: int) -> None:
    payload = _valid_payload()
    payload["research_value"] = research_value
    payload["value_types"] = []

    result = validate_output("value_prediction", payload, context=_context())

    assert result.value_types == []


@pytest.mark.parametrize("research_value", [3, 4, 5])
def test_research_value_at_least_three_requires_a_value_type(
    research_value: int,
) -> None:
    payload = _valid_payload()
    payload["research_value"] = research_value
    payload["value_types"] = []

    with pytest.raises(OutputValidationError) as captured:
        validate_output("value_prediction", payload, context=_context())

    assert captured.value.issues[0].location == "$.value_types"
    assert captured.value.issues[0].category is OutputErrorCategory.BUSINESS_RULE


@pytest.mark.parametrize("value_type", ["other", "unknown"])
def test_unknown_value_type_is_rejected(value_type: str) -> None:
    payload = _valid_payload()
    payload["value_types"] = [value_type]

    with pytest.raises(OutputValidationError) as captured:
        validate_output("value_prediction", payload, context=_context())

    assert captured.value.issues[0].location == "$.value_types[0]"
    assert captured.value.issues[0].category is OutputErrorCategory.INVALID_ENUM


def test_duplicate_value_type_is_rejected() -> None:
    payload = _valid_payload()
    payload["value_types"] = ["method", "method"]

    with pytest.raises(OutputValidationError) as captured:
        validate_output("value_prediction", payload, context=_context())

    assert captured.value.issues[0].location == "$.value_types[1]"
    assert captured.value.issues[0].category is OutputErrorCategory.BUSINESS_RULE


def test_value_prediction_accepts_zero_or_enabled_topic_matches() -> None:
    payload = _valid_payload()
    payload["topic_ids"] = []
    no_match = validate_output("value_prediction", payload, context=_context())

    payload["topic_ids"] = ["extreme-rainfall"]
    enabled_match = validate_output("value_prediction", payload, context=_context())

    assert no_match.topic_ids == []
    assert enabled_match.topic_ids == ["extreme-rainfall"]


@pytest.mark.parametrize("topic_id", ["unknown-topic", "disabled-topic"])
def test_value_prediction_rejects_topic_that_is_not_enabled(topic_id: str) -> None:
    payload = _valid_payload()
    payload["topic_ids"] = [topic_id]

    with pytest.raises(OutputValidationError) as captured:
        validate_output("value_prediction", payload, context=_context())

    assert captured.value.issues[0].location == "$.topic_ids[0]"
    assert captured.value.issues[0].category is OutputErrorCategory.BUSINESS_RULE


def test_value_prediction_rejects_duplicate_topic_id() -> None:
    payload = _valid_payload()
    payload["topic_ids"] = ["extreme-rainfall", "extreme-rainfall"]

    with pytest.raises(OutputValidationError) as captured:
        validate_output("value_prediction", payload, context=_context())

    assert captured.value.issues[0].location == "$.topic_ids[1]"
    assert captured.value.issues[0].category is OutputErrorCategory.BUSINESS_RULE


def test_value_prediction_accepts_exact_context_mapping_without_mutation() -> None:
    context = {
        "enabled_topic_ids": frozenset({"extreme-rainfall"}),
        "original_title_is_zh": False,
    }
    original = deepcopy(context)

    result = validate_output("value_prediction", _valid_payload(), context=context)

    assert result.topic_ids == ["extreme-rainfall"]
    assert context == original


@pytest.mark.parametrize(
    ("context", "category", "location"),
    [
        (None, OutputErrorCategory.MISSING_CONTEXT, "$.context"),
        ({}, OutputErrorCategory.MISSING_CONTEXT, "$.context.enabled_topic_ids"),
        (
            {"enabled_topic_ids": frozenset()},
            OutputErrorCategory.MISSING_CONTEXT,
            "$.context.original_title_is_zh",
        ),
        ([], OutputErrorCategory.CONTEXT_MISMATCH, "$.context"),
        (
            {
                "enabled_topic_ids": frozenset(),
                "original_title_is_zh": "false",
            },
            OutputErrorCategory.CONTEXT_MISMATCH,
            "$.context.original_title_is_zh",
        ),
    ],
)
def test_value_prediction_requires_complete_controlled_context(
    context: object,
    category: OutputErrorCategory,
    location: str,
) -> None:
    with pytest.raises(OutputValidationError) as captured:
        validate_output("value_prediction", _valid_payload(), context=context)

    assert captured.value.issues[0].location == location
    assert captured.value.issues[0].category is category


@pytest.mark.parametrize(
    "field",
    [
        "research_value_reason_zh",
        "reuse_feasibility_reason_zh",
        "abstract_brief_zh",
        "why_it_may_matter_zh",
    ],
)
@pytest.mark.parametrize("invalid_text", ["", " \t\n ", "待补充"])
def test_value_prediction_rejects_blank_or_placeholder_required_text(
    field: str,
    invalid_text: str,
) -> None:
    payload = _valid_payload()
    payload[field] = invalid_text

    with pytest.raises(OutputValidationError) as captured:
        validate_output("value_prediction", payload, context=_context())

    assert captured.value.issues[0].location == f"$.{field}"
    assert captured.value.issues[0].category is OutputErrorCategory.INVALID_TEXT


def test_value_prediction_preserves_required_original_terms_exactly() -> None:
    reason = "需保留原文术语 cloud-resolving model（CRM）才能准确说明限制。"
    payload = _valid_payload()
    payload["research_value_reason_zh"] = reason

    result = validate_output("value_prediction", payload, context=_context())

    assert result.research_value_reason_zh == reason


@pytest.mark.parametrize("omit_field", [True, False])
def test_chinese_original_title_allows_only_null_display_title(
    omit_field: bool,
) -> None:
    payload = _valid_payload()
    if not omit_field:
        payload["display_title_zh"] = None
    context = ValuePredictionContext(
        enabled_topic_ids=frozenset({"extreme-rainfall"}),
        original_title_is_zh=True,
    )

    result = validate_output("value_prediction", payload, context=context)

    assert result.display_title_zh is None


def test_chinese_original_title_rejects_non_null_display_title() -> None:
    payload = _valid_payload()
    payload["display_title_zh"] = "极端降水诊断的新方法"
    context = ValuePredictionContext(
        enabled_topic_ids=frozenset({"extreme-rainfall"}),
        original_title_is_zh=True,
    )

    with pytest.raises(OutputValidationError) as captured:
        validate_output("value_prediction", payload, context=context)

    assert captured.value.issues[0].location == "$.display_title_zh"
    assert captured.value.issues[0].category is OutputErrorCategory.CONTEXT_MISMATCH


@pytest.mark.parametrize("display_title", ["", "  ", "暂无"])
def test_non_chinese_original_rejects_empty_or_placeholder_display_title(
    display_title: str,
) -> None:
    payload = _valid_payload()
    payload["display_title_zh"] = display_title

    with pytest.raises(OutputValidationError) as captured:
        validate_output("value_prediction", payload, context=_context())

    assert captured.value.issues[0].location == "$.display_title_zh"
    assert captured.value.issues[0].category is OutputErrorCategory.INVALID_TEXT


@pytest.mark.parametrize("display_title", [None, "极端降水诊断的新方法"])
def test_non_chinese_original_accepts_null_or_meaningful_display_title(
    display_title: str | None,
) -> None:
    payload = _valid_payload()
    payload["display_title_zh"] = display_title

    result = validate_output("value_prediction", payload, context=_context())

    assert result.display_title_zh == display_title


@pytest.mark.parametrize(
    "reason",
    [
        "当前输入不足以判断代码获取和改造成本，只能给出初步评分。",
        "摘要未说明 GPU memory 与训练时长，因此复用条件仍不明确。",
        "The abstract provides insufficient information，无法充分判断复用条件。",
    ],
)
def test_non_inferable_reuse_keeps_initial_score_with_insufficient_input_reason(
    reason: str,
) -> None:
    payload = _valid_payload()
    payload["reuse_feasibility"] = 2
    payload["reuse_feasibility_inferable"] = False
    payload["reuse_feasibility_reason_zh"] = reason

    result = validate_output("value_prediction", payload, context=_context())

    assert result.reuse_feasibility == 2
    assert result.reuse_feasibility_reason_zh == reason


@pytest.mark.parametrize(
    "reason",
    [
        "采用相同数据格式后预计可以复用。",
        "需要调整 ERA5 preprocessing pipeline。",
    ],
)
def test_non_inferable_reuse_requires_explicit_insufficient_input_reason(
    reason: str,
) -> None:
    payload = _valid_payload()
    payload["reuse_feasibility_inferable"] = False
    payload["reuse_feasibility_reason_zh"] = reason

    with pytest.raises(OutputValidationError) as captured:
        validate_output("value_prediction", payload, context=_context())

    assert captured.value.issues[0].location == "$.reuse_feasibility_reason_zh"
    assert captured.value.issues[0].category is OutputErrorCategory.BUSINESS_RULE


def test_value_prediction_schema_has_only_display_title_as_optional_default() -> None:
    assert set(ValuePredictionOutput.model_fields) == {
        "research_value",
        "research_value_reason_zh",
        "reuse_feasibility",
        "reuse_feasibility_reason_zh",
        "reuse_feasibility_inferable",
        "value_types",
        "topic_ids",
        "display_title_zh",
        "abstract_brief_zh",
        "why_it_may_matter_zh",
    }
    optional_fields = {
        name
        for name, field in ValuePredictionOutput.model_fields.items()
        if not field.is_required()
    }
    assert optional_fields == {"display_title_zh"}
    assert ValuePredictionOutput.model_fields["display_title_zh"].default is None


@pytest.mark.parametrize(
    "required_field",
    [
        "research_value",
        "research_value_reason_zh",
        "reuse_feasibility",
        "reuse_feasibility_reason_zh",
        "reuse_feasibility_inferable",
        "value_types",
        "topic_ids",
        "abstract_brief_zh",
        "why_it_may_matter_zh",
    ],
)
def test_value_prediction_rejects_every_missing_required_field(
    required_field: str,
) -> None:
    payload = _valid_payload()
    del payload[required_field]

    with pytest.raises(OutputValidationError) as captured:
        validate_output("value_prediction", payload, context=_context())

    assert captured.value.issues[0].location == f"$.{required_field}"
    assert captured.value.issues[0].category is OutputErrorCategory.MISSING_FIELD


def test_value_prediction_accepts_complete_json_document() -> None:
    payload = json.dumps(_valid_payload(), ensure_ascii=False)

    result = validate_output("value_prediction", payload, context=_context())

    assert result.research_value == 4


@pytest.mark.parametrize("invalid_inferable", [0, 1, 0.0, "true"])
def test_value_prediction_requires_a_real_boolean_inferable_flag(
    invalid_inferable: object,
) -> None:
    payload = _valid_payload()
    payload["reuse_feasibility_inferable"] = invalid_inferable

    with pytest.raises(OutputValidationError) as captured:
        validate_output("value_prediction", payload, context=_context())

    assert captured.value.issues[0].location == "$.reuse_feasibility_inferable"
    assert captured.value.issues[0].category is OutputErrorCategory.INVALID_TYPE


@pytest.mark.parametrize(
    ("payload", "category", "location"),
    [
        (
            {
                key: value
                for key, value in _valid_payload().items()
                if key != "topic_ids"
            },
            OutputErrorCategory.MISSING_FIELD,
            "$.topic_ids",
        ),
        (
            {**_valid_payload(), "final_decision": "accepted"},
            OutputErrorCategory.EXTRA_FIELD,
            "$.<额外字段>",
        ),
        (
            {**_valid_payload(), "reuse_feasibility_inferable": "false"},
            OutputErrorCategory.INVALID_TYPE,
            "$.reuse_feasibility_inferable",
        ),
        (
            {**_valid_payload(), "topic_ids": ("extreme-rainfall",)},
            OutputErrorCategory.INVALID_TYPE,
            "$.topic_ids",
        ),
        (
            json.dumps(_valid_payload(), ensure_ascii=False)[:-1],
            OutputErrorCategory.INVALID_JSON,
            "$",
        ),
    ],
)
def test_value_prediction_rejects_invalid_structure(
    payload: object,
    category: OutputErrorCategory,
    location: str,
) -> None:
    with pytest.raises(OutputValidationError) as captured:
        validate_output("value_prediction", payload, context=_context())

    assert captured.value.issues[0].location == location
    assert captured.value.issues[0].category is category


@pytest.mark.parametrize(
    "forbidden_field",
    [
        "decision",
        "journal_reputation",
        "rank",
        "priority",
        "urgency",
        "tags",
        "topic_weights",
        "confidence",
    ],
)
def test_value_prediction_rejects_every_forbidden_model_output_field(
    forbidden_field: str,
) -> None:
    payload = _valid_payload()
    payload[forbidden_field] = "sensitive-forbidden-value"

    with pytest.raises(OutputValidationError) as captured:
        validate_output("value_prediction", payload, context=_context())

    assert captured.value.issues[0].location == "$.<额外字段>"
    assert captured.value.issues[0].category is OutputErrorCategory.EXTRA_FIELD


def test_value_prediction_failures_do_not_leak_input_or_pydantic_details(
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    markers = (
        "sk-value-secret",
        "secret-value-profile",
        "secret-value-abstract",
        "secret-value-response",
        "secret-value-context",
    )
    payload = _valid_payload()
    payload[markers[1]] = markers[2]
    failing_calls: tuple[Callable[[], object], ...] = (
        lambda: validate_output("value_prediction", payload, context=_context()),
        lambda: validate_output(
            "value_prediction",
            f'{{"research_value":"{markers[3]}"',
            context=_context(),
        ),
        lambda: validate_output(
            "value_prediction",
            _valid_payload(),
            context={markers[4]: markers[0]},
        ),
    )

    rendered_errors: list[str] = []
    for failing_call in failing_calls:
        with pytest.raises(OutputValidationError) as captured:
            failing_call()
        rendered_errors.extend((str(captured.value), repr(captured.value)))
        assert captured.value.__cause__ is None
        assert captured.value.__context__ is None

    captured_streams = capsys.readouterr()
    public_surface = "\n".join(
        [*rendered_errors, captured_streams.out, captured_streams.err, caplog.text]
    )
    for marker in markers:
        assert marker not in public_surface
    assert "validation error for ValuePredictionOutput" not in public_surface
    assert "pydantic_core" not in public_surface
    assert "Traceback" not in public_surface
