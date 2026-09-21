from __future__ import annotations

from collections.abc import Callable
from itertools import product
from typing import Any

import pytest
from pydantic import ValidationError

from paper_radar.screening import (
    DECISION_REASON_DESCRIPTIONS_ZH,
    SCREENING_RESULT_DESCRIPTIONS_ZH,
    SCREENING_SOURCE_DESCRIPTIONS_ZH,
    DecisionReason,
    OutputErrorCategory,
    OutputValidationError,
    ScreeningDecision,
    ScreeningFailureProjection,
    ScreeningResult,
    ScreeningSource,
    ScreeningSuggestion,
    screening_reason_json_schema,
    validate_screening_reason,
)

RESULT_VALUES = ("accepted", "pending", "denied")
SOURCE_VALUES = (
    "suggestion_rule",
    "blind_calibration",
    "regular_review",
    "direct_manual_decision",
    "metadata_abandonment",
    "manual_read_request",
    "fixed_calibration_member_projection",
    "failure_queue_projection",
)
REASON_VALUES = (
    "high_research_value",
    "research_and_reuse",
    "out_of_scope",
    "boundary_uncertain",
    "value_reuse_conflict",
    "reuse_unknown",
    "reuse_escalation_unavailable",
    "low_value",
    "low_reuse_feasibility",
    "user_judgment",
    "unclear_from_available_input",
    "defer_judgment",
    "outside_current_focus",
    "insufficient_metadata",
    "manual_read_request",
    "model_failure",
)


ALLOWED_COMBINATIONS = (
    ("accepted", "suggestion_rule", "high_research_value", ScreeningSuggestion),
    ("accepted", "suggestion_rule", "research_and_reuse", ScreeningSuggestion),
    ("denied", "suggestion_rule", "out_of_scope", ScreeningSuggestion),
    ("pending", "suggestion_rule", "boundary_uncertain", ScreeningSuggestion),
    ("pending", "suggestion_rule", "value_reuse_conflict", ScreeningSuggestion),
    ("pending", "suggestion_rule", "reuse_unknown", ScreeningSuggestion),
    (
        "pending",
        "suggestion_rule",
        "reuse_escalation_unavailable",
        ScreeningSuggestion,
    ),
    ("denied", "suggestion_rule", "low_value", ScreeningSuggestion),
    ("denied", "suggestion_rule", "low_reuse_feasibility", ScreeningSuggestion),
    ("denied", "blind_calibration", "out_of_scope", ScreeningDecision),
    ("denied", "blind_calibration", "low_value", ScreeningDecision),
    (
        "denied",
        "blind_calibration",
        "low_reuse_feasibility",
        ScreeningDecision,
    ),
    ("accepted", "blind_calibration", "user_judgment", ScreeningDecision),
    (
        "pending",
        "blind_calibration",
        "unclear_from_available_input",
        ScreeningDecision,
    ),
    ("pending", "blind_calibration", "defer_judgment", ScreeningDecision),
    ("pending", "blind_calibration", "outside_current_focus", ScreeningDecision),
    ("denied", "regular_review", "out_of_scope", ScreeningDecision),
    ("denied", "regular_review", "low_value", ScreeningDecision),
    ("denied", "regular_review", "low_reuse_feasibility", ScreeningDecision),
    ("accepted", "regular_review", "user_judgment", ScreeningDecision),
    (
        "pending",
        "regular_review",
        "unclear_from_available_input",
        ScreeningDecision,
    ),
    ("pending", "regular_review", "defer_judgment", ScreeningDecision),
    ("pending", "regular_review", "outside_current_focus", ScreeningDecision),
    ("denied", "direct_manual_decision", "out_of_scope", ScreeningDecision),
    ("denied", "direct_manual_decision", "low_value", ScreeningDecision),
    (
        "denied",
        "direct_manual_decision",
        "low_reuse_feasibility",
        ScreeningDecision,
    ),
    ("accepted", "direct_manual_decision", "user_judgment", ScreeningDecision),
    (
        "pending",
        "direct_manual_decision",
        "unclear_from_available_input",
        ScreeningDecision,
    ),
    (
        "pending",
        "direct_manual_decision",
        "defer_judgment",
        ScreeningDecision,
    ),
    (
        "pending",
        "direct_manual_decision",
        "outside_current_focus",
        ScreeningDecision,
    ),
    (
        "denied",
        "metadata_abandonment",
        "insufficient_metadata",
        ScreeningDecision,
    ),
    (
        "accepted",
        "manual_read_request",
        "manual_read_request",
        ScreeningDecision,
    ),
    (
        "pending",
        "fixed_calibration_member_projection",
        "model_failure",
        ScreeningFailureProjection,
    ),
    (
        "pending",
        "failure_queue_projection",
        "model_failure",
        ScreeningFailureProjection,
    ),
)


@pytest.mark.parametrize(
    ("result", "source", "reason", "expected_type"),
    ALLOWED_COMBINATIONS,
)
def test_all_specified_reason_combinations_preserve_their_identity(
    result: str,
    source: str,
    reason: str,
    expected_type: type[object],
) -> None:
    validated = validate_screening_reason(
        {"result": result, "source": source, "reason": reason}
    )

    assert isinstance(validated, expected_type)
    assert validated.model_dump(mode="json") == {
        "result": result,
        "source": source,
        "reason": reason,
    }


def test_every_other_controlled_reason_combination_is_rejected() -> None:
    allowed = {
        (result, source, reason) for result, source, reason, _ in ALLOWED_COMBINATIONS
    }
    expected_results: dict[str, str] = {}
    allowed_sources_by_reason: dict[str, set[str]] = {}
    for allowed_result, allowed_source, allowed_reason, _ in ALLOWED_COMBINATIONS:
        expected_results[allowed_reason] = allowed_result
        allowed_sources_by_reason.setdefault(allowed_reason, set()).add(allowed_source)

    for result, source, reason in product(
        RESULT_VALUES,
        SOURCE_VALUES,
        REASON_VALUES,
    ):
        if (result, source, reason) in allowed:
            continue

        with pytest.raises(OutputValidationError) as captured:
            validate_screening_reason(
                {"result": result, "source": source, "reason": reason}
            )

        expected_locations = []
        if result != expected_results[reason]:
            expected_locations.append("$.result")
        if source not in allowed_sources_by_reason[reason]:
            expected_locations.append("$.source")
        assert [issue.location for issue in captured.value.issues] == expected_locations
        assert all(
            issue.category is OutputErrorCategory.BUSINESS_RULE
            for issue in captured.value.issues
        )


def test_reason_contract_has_fixed_serialized_vocabulary_and_chinese_descriptions() -> (
    None
):
    assert tuple(item.value for item in ScreeningResult) == RESULT_VALUES
    assert tuple(item.value for item in ScreeningSource) == SOURCE_VALUES
    assert tuple(item.value for item in DecisionReason) == REASON_VALUES
    assert SCREENING_RESULT_DESCRIPTIONS_ZH == {
        ScreeningResult.ACCEPTED: "值得进入全文精读",
        ScreeningResult.PENDING: "当前证据不足或留待复核",
        ScreeningResult.DENIED: "停止新的自动下游处理",
    }
    assert SCREENING_SOURCE_DESCRIPTIONS_ZH == {
        ScreeningSource.SUGGESTION_RULE: "建议规则",
        ScreeningSource.BLIND_CALIBRATION: "盲评",
        ScreeningSource.REGULAR_REVIEW: "普通复核",
        ScreeningSource.DIRECT_MANUAL_DECISION: "直接人工决定",
        ScreeningSource.METADATA_ABANDONMENT: "元数据人工放弃",
        ScreeningSource.MANUAL_READ_REQUEST: "人工精读请求",
        ScreeningSource.FIXED_CALIBRATION_MEMBER_PROJECTION: ("固定校准成员失败投影"),
        ScreeningSource.FAILURE_QUEUE_PROJECTION: "模型失败队列投影",
    }
    assert DECISION_REASON_DESCRIPTIONS_ZH == {
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


@pytest.mark.parametrize(
    ("payload", "category", "location"),
    [
        (
            {"source": "suggestion_rule", "reason": "high_research_value"},
            OutputErrorCategory.MISSING_FIELD,
            "$.result",
        ),
        (
            {
                "result": "accepted",
                "source": "suggestion_rule",
                "reason": "high_research_value",
                "secret-extra-field": "secret-extra-value",
            },
            OutputErrorCategory.EXTRA_FIELD,
            "$.<额外字段>",
        ),
        (
            {
                "result": True,
                "source": "suggestion_rule",
                "reason": "high_research_value",
            },
            OutputErrorCategory.INVALID_TYPE,
            "$.result",
        ),
        (
            {
                "result": "maybe",
                "source": "suggestion_rule",
                "reason": "high_research_value",
            },
            OutputErrorCategory.INVALID_ENUM,
            "$.result",
        ),
        (
            {
                "result": "accepted",
                "source": "system_guess",
                "reason": "high_research_value",
            },
            OutputErrorCategory.INVALID_ENUM,
            "$.source",
        ),
        (
            {
                "result": "accepted",
                "source": "suggestion_rule",
                "reason": "other",
            },
            OutputErrorCategory.INVALID_ENUM,
            "$.reason",
        ),
        (
            ["accepted", "suggestion_rule", "high_research_value"],
            OutputErrorCategory.INVALID_TYPE,
            "$",
        ),
        (
            '{"result":"accepted","source":"suggestion_rule","reason":',
            OutputErrorCategory.INVALID_JSON,
            "$",
        ),
    ],
)
def test_reason_contract_rejects_missing_extra_unknown_and_wrong_types(
    payload: object,
    category: OutputErrorCategory,
    location: str,
) -> None:
    with pytest.raises(OutputValidationError) as captured:
        validate_screening_reason(payload)

    assert captured.value.issues[0].category is category
    assert captured.value.issues[0].location == location
    assert "secret-extra-field" not in str(captured.value)
    assert "secret-extra-value" not in str(captured.value)


@pytest.mark.parametrize(
    ("result", "source", "reason"),
    [
        ("pending", "suggestion_rule", "model_failure"),
        ("pending", "direct_manual_decision", "model_failure"),
        ("accepted", "fixed_calibration_member_projection", "model_failure"),
        ("denied", "regular_review", "insufficient_metadata"),
        ("accepted", "direct_manual_decision", "manual_read_request"),
    ],
)
def test_special_reasons_cannot_masquerade_as_suggestions_or_decisions(
    result: str,
    source: str,
    reason: str,
) -> None:
    with pytest.raises(OutputValidationError):
        validate_screening_reason(
            {"result": result, "source": source, "reason": reason}
        )


@pytest.mark.parametrize(
    ("payload", "location", "guidance_fragment"),
    [
        (
            {
                "result": "pending",
                "source": "suggestion_rule",
                "reason": "high_research_value",
            },
            "$.result",
            "对应结果",
        ),
        (
            {
                "result": "accepted",
                "source": "direct_manual_decision",
                "reason": "high_research_value",
            },
            "$.source",
            "允许来源",
        ),
    ],
)
def test_invalid_combination_identifies_the_field_and_action(
    payload: dict[str, object],
    location: str,
    guidance_fragment: str,
) -> None:
    with pytest.raises(OutputValidationError) as captured:
        validate_screening_reason(payload)

    assert captured.value.issues[0].location == location
    assert guidance_fragment in captured.value.issues[0].guidance_zh


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (
            ScreeningSuggestion,
            {
                "result": "pending",
                "source": "failure_queue_projection",
                "reason": "model_failure",
            },
        ),
        (
            ScreeningDecision,
            {
                "result": "pending",
                "source": "direct_manual_decision",
                "reason": "model_failure",
            },
        ),
        (
            ScreeningFailureProjection,
            {
                "result": "accepted",
                "source": "fixed_calibration_member_projection",
                "reason": "user_judgment",
            },
        ),
    ],
)
def test_authoritative_identity_types_cannot_be_directly_constructed_as_masquerades(
    model: type[ScreeningSuggestion]
    | type[ScreeningDecision]
    | type[ScreeningFailureProjection],
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(payload)


def _combinations_expressed_by_schema() -> set[tuple[str, str, str]]:
    schema: Any = screening_reason_json_schema()
    combinations: set[tuple[str, str, str]] = set()
    assert set(schema) == {"$defs", "anyOf"}
    for branch in schema["anyOf"]:
        reference = branch["$ref"]
        definition = schema["$defs"][reference.removeprefix("#/$defs/")]
        assert definition["additionalProperties"] is False
        assert set(definition["required"]) == {"result", "source", "reason"}
        properties = definition["properties"]
        combinations.add(
            (
                properties["result"]["const"],
                properties["source"]["const"],
                properties["reason"]["const"],
            )
        )
    return combinations


def _schema_accepts(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    schema: Any = screening_reason_json_schema()
    for branch in schema["anyOf"]:
        reference = branch["$ref"]
        definition = schema["$defs"][reference.removeprefix("#/$defs/")]
        if set(payload) != set(definition["required"]):
            continue
        properties = definition["properties"]
        if all(
            type(payload[field]) is str and payload[field] == properties[field]["const"]
            for field in definition["required"]
        ):
            return True
    return False


def test_generated_schema_accepts_exactly_the_same_positive_and_negative_matrix() -> (
    None
):
    schema_combinations = _combinations_expressed_by_schema()
    expected = {
        (result, source, reason)
        for result, source, reason, _expected_type in ALLOWED_COMBINATIONS
    }

    assert schema_combinations == expected
    for combination in product(RESULT_VALUES, SOURCE_VALUES, REASON_VALUES):
        assert (combination in schema_combinations) is (combination in expected)


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (
            {
                "result": "accepted",
                "source": "suggestion_rule",
                "reason": "high_research_value",
            },
            True,
        ),
        (
            {
                "result": "pending",
                "source": "fixed_calibration_member_projection",
                "reason": "model_failure",
            },
            True,
        ),
        (
            {
                "result": "pending",
                "source": "suggestion_rule",
                "reason": "model_failure",
            },
            False,
        ),
        (
            {"source": "suggestion_rule", "reason": "high_research_value"},
            False,
        ),
        (
            {
                "result": "accepted",
                "source": "suggestion_rule",
                "reason": "high_research_value",
                "extra": "field",
            },
            False,
        ),
        (
            {
                "result": True,
                "source": "suggestion_rule",
                "reason": "high_research_value",
            },
            False,
        ),
        (
            {
                "result": "accepted",
                "source": "unknown",
                "reason": "high_research_value",
            },
            False,
        ),
    ],
)
def test_runtime_and_generated_schema_agree_on_the_same_examples(
    payload: object,
    expected: bool,
) -> None:
    try:
        validate_screening_reason(payload)
    except OutputValidationError:
        runtime_accepts = False
    else:
        runtime_accepts = True

    assert runtime_accepts is expected
    assert _schema_accepts(payload) is expected


def test_reason_validation_errors_do_not_echo_inputs(
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    markers = (
        "secret-result-marker",
        "secret-source-marker",
        "secret-reason-marker",
        "secret-extra-field",
        "secret-extra-value",
    )
    failing_calls: tuple[Callable[[], object], ...] = (
        lambda: validate_screening_reason(
            {
                "result": markers[0],
                "source": "suggestion_rule",
                "reason": "high_research_value",
            }
        ),
        lambda: validate_screening_reason(
            {
                "result": "accepted",
                "source": markers[1],
                "reason": markers[2],
            }
        ),
        lambda: validate_screening_reason(
            {
                "result": "accepted",
                "source": "suggestion_rule",
                "reason": "high_research_value",
                markers[3]: markers[4],
            }
        ),
    )

    rendered_errors: list[str] = []
    for failing_call in failing_calls:
        with pytest.raises(OutputValidationError) as captured:
            failing_call()
        rendered_errors.extend((str(captured.value), repr(captured.value)))
        assert captured.value.__cause__ is None
        assert captured.value.__context__ is None

    streams = capsys.readouterr()
    public_surface = "\n".join(
        [*rendered_errors, streams.out, streams.err, caplog.text]
    )
    for marker in markers:
        assert marker not in public_surface
