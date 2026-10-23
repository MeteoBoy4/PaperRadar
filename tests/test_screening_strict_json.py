from __future__ import annotations

import json

import pytest

from paper_radar.screening import (
    ExcerptKind,
    OutputErrorCategory,
    OutputValidationError,
    ReuseAssessmentContext,
    ValuePredictionContext,
    validate_output,
    validate_screening_reason,
)


def test_duplicate_boundary_key_is_invalid_json() -> None:
    with pytest.raises(OutputValidationError) as captured:
        validate_output(
            "boundary",
            '{"boundary":"in_scope","boundary":"out_of_scope",'
            '"reason_zh":"该论文讨论目标研究问题。"}',
        )

    assert [(issue.category, issue.location) for issue in captured.value.issues] == [
        (OutputErrorCategory.INVALID_JSON, "$")
    ]


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_json_numbers_are_syntax_errors(constant: str) -> None:
    with pytest.raises(OutputValidationError) as captured:
        validate_output(
            "boundary",
            '{"boundary":"in_scope","reason_zh":' + constant + "}",
        )

    assert [(issue.category, issue.location) for issue in captured.value.issues] == [
        (OutputErrorCategory.INVALID_JSON, "$")
    ]


@pytest.mark.parametrize(
    "payload",
    [
        b'\xef\xbb\xbf{"boundary":"in_scope","reason_zh":"valid reason"}',
        '{"boundary":"in_scope","reason_zh":"valid reason"}'.encode("utf-16"),
        b'{"boundary":"in_scope","reason_zh":"\xff"}',
    ],
)
def test_raw_json_rejects_bom_and_non_utf8(payload: bytes) -> None:
    with pytest.raises(OutputValidationError) as captured:
        validate_output("boundary", payload)

    assert [(issue.category, issue.location) for issue in captured.value.issues] == [
        (OutputErrorCategory.INVALID_JSON, "$")
    ]


def _validate(kind: str, payload: object) -> object:
    if kind == "reason":
        return validate_screening_reason(payload)
    contexts: dict[str, object] = {
        "boundary": None,
        "value_prediction": ValuePredictionContext(
            enabled_topic_ids=frozenset({"rainfall"}), original_title_is_zh=False
        ),
        "reuse_assessment": ReuseAssessmentContext(
            excerpt_kinds={"methods-1": ExcerptKind.METHODS}
        ),
    }
    return validate_output(kind, payload, contexts[kind])


def _raw(kind: str) -> str:
    return json.dumps(
        {
            "boundary": {"boundary": "in_scope", "reason_zh": "研究讨论区域降水。"},
            "value_prediction": {
                "research_value": 4,
                "research_value_reason_zh": "可改进区域降水研究。",
                "reuse_feasibility": 3,
                "reuse_feasibility_reason_zh": "需要调整输入网格。",
                "reuse_feasibility_inferable": True,
                "value_types": ["method"],
                "topic_ids": ["rainfall"],
                "abstract_brief_zh": "研究提出降水分析方法。",
                "why_it_may_matter_zh": "可用于目标区域研究。",
            },
            "reuse_assessment": {
                "reuse_feasibility": 4,
                "reuse_feasibility_reason_zh": "方法可在调整网格后复用。",
                "required_adaptations": [],
                "excerpt_kind": "methods",
                "excerpt_ids": ["methods-1"],
            },
            "reason": {
                "result": "pending",
                "source": "fixed_calibration_member_projection",
                "reason": "model_failure",
            },
        }[kind],
        ensure_ascii=False,
    )


def _representation(raw: str, representation: str) -> str | bytes | bytearray:
    if representation == "str":
        return raw
    encoded = raw.encode("utf-8")
    return encoded if representation == "bytes" else bytearray(encoded)


@pytest.mark.parametrize(
    "kind", ["boundary", "value_prediction", "reuse_assessment", "reason"]
)
@pytest.mark.parametrize("representation", ["str", "bytes", "bytearray"])
@pytest.mark.parametrize(
    "invalid_member",
    [
        '"secret-response-marker":1,"secret-response-marker":2',
        '"secret-response-marker":[{"inner":1,"inner":2}]',
        '"secret-response-marker":{"inner":NaN}',
        '"secret-response-marker":Infinity',
        '"secret-response-marker":-Infinity',
    ],
)
def test_all_public_entries_reject_invalid_json_before_schema_errors(
    kind: str,
    representation: str,
    invalid_member: str,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    raw = _raw(kind)[:-1] + "," + invalid_member + "}"
    with pytest.raises(OutputValidationError) as captured:
        _validate(kind, _representation(raw, representation))

    assert [(issue.category, issue.location) for issue in captured.value.issues] == [
        (OutputErrorCategory.INVALID_JSON, "$")
    ]
    assert captured.value.__cause__ is None
    assert captured.value.__context__ is None
    streams = capsys.readouterr()
    assert "secret-response-marker" not in (
        str(captured.value)
        + repr(captured.value)
        + streams.out
        + streams.err
        + caplog.text
    )


@pytest.mark.parametrize(
    "kind", ["boundary", "value_prediction", "reuse_assessment", "reason"]
)
@pytest.mark.parametrize("representation", ["str", "bytes", "bytearray"])
def test_raw_json_whitespace_preserves_authoritative_result(
    kind: str, representation: str
) -> None:
    raw = _raw(kind)
    structured = json.loads(raw)
    assert _validate(
        kind, _representation(" \t\r\n" + raw + "\n ", representation)
    ) == (_validate(kind, structured))


@pytest.mark.parametrize(
    ("payload", "category", "location"),
    [
        (
            '{"boundary":true,"reason_zh":"研究讨论降水。"}',
            OutputErrorCategory.INVALID_TYPE,
            "$.boundary",
        ),
        (
            '{"boundary":"in_scope","reason_zh":"TODO"}',
            OutputErrorCategory.INVALID_TEXT,
            "$.reason_zh",
        ),
        (
            '{"boundary":"in_scope","reason_zh":"研究讨论降水。","secret":1}',
            OutputErrorCategory.EXTRA_FIELD,
            "$.<额外字段>",
        ),
        (
            '{"boundary":"wrong","boundary":"uncertain","reason_zh":"TODO"}',
            OutputErrorCategory.INVALID_JSON,
            "$",
        ),
        (
            '{"boundary":"in_scope","\\u0062oundary":"uncertain","reason_zh":"研究讨论降水。"}',
            OutputErrorCategory.INVALID_JSON,
            "$",
        ),
        (
            '\ufeff{"boundary":"in_scope","reason_zh":"研究讨论降水。"}',
            OutputErrorCategory.INVALID_JSON,
            "$",
        ),
    ],
)
def test_strict_parser_keeps_field_and_business_validation(
    payload: str, category: OutputErrorCategory, location: str
) -> None:
    with pytest.raises(OutputValidationError) as captured:
        validate_output("boundary", payload)
    assert captured.value.issues[0].category is category
    assert captured.value.issues[0].location == location
