from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy

import pytest

from paper_radar.screening import (
    OutputErrorCategory,
    OutputValidationError,
    ReuseAssessmentContext,
    ReuseAssessmentOutput,
    validate_output,
)


def _valid_payload() -> dict[str, object]:
    return {
        "reuse_feasibility": 4,
        "reuse_feasibility_reason_zh": "所引摘录表明数据与方法可以复用。",
        "required_adaptations": ["将输入资料转换为本地网格。"],
        "excerpt_kind": "both",
        "excerpt_ids": ["availability-1", "methods-1"],
    }


def _context_mapping() -> dict[str, object]:
    return {
        "excerpt_kinds": {
            "availability-1": "availability",
            "availability-2": "availability",
            "methods-1": "methods",
            "methods-2": "methods",
        }
    }


def test_validate_availability_reuse_assessment_returns_authoritative_type() -> None:
    payload = {
        "reuse_feasibility": 4,
        "reuse_feasibility_reason_zh": "开放数据与代码可直接接入现有流程。",
        "required_adaptations": [],
        "excerpt_kind": "availability",
        "excerpt_ids": ["availability-1"],
    }
    context = ReuseAssessmentContext(excerpt_kinds={"availability-1": "availability"})
    original_payload = deepcopy(payload)

    result = validate_output("reuse_assessment", payload, context=context)

    assert result == ReuseAssessmentOutput(
        reuse_feasibility=4,
        reuse_feasibility_reason_zh="开放数据与代码可直接接入现有流程。",
        required_adaptations=[],
        excerpt_kind="availability",
        excerpt_ids=["availability-1"],
    )
    assert payload == original_payload


def test_reuse_assessment_requires_at_least_one_excerpt_id() -> None:
    payload = {
        "reuse_feasibility": 4,
        "reuse_feasibility_reason_zh": "开放数据与代码可直接接入现有流程。",
        "required_adaptations": [],
        "excerpt_kind": "availability",
        "excerpt_ids": [],
    }
    context = ReuseAssessmentContext(excerpt_kinds={"availability-1": "availability"})

    with pytest.raises(OutputValidationError) as captured:
        validate_output("reuse_assessment", payload, context=context)

    assert captured.value.issues[0].location == "$.excerpt_ids"
    assert captured.value.issues[0].category is OutputErrorCategory.BUSINESS_RULE


def test_reuse_assessment_rejects_duplicate_excerpt_id() -> None:
    payload = {
        "reuse_feasibility": 4,
        "reuse_feasibility_reason_zh": "开放数据与代码可直接接入现有流程。",
        "required_adaptations": [],
        "excerpt_kind": "availability",
        "excerpt_ids": ["availability-1", "availability-1"],
    }
    context = ReuseAssessmentContext(excerpt_kinds={"availability-1": "availability"})

    with pytest.raises(OutputValidationError) as captured:
        validate_output("reuse_assessment", payload, context=context)

    assert captured.value.issues[0].location == "$.excerpt_ids[1]"
    assert captured.value.issues[0].category is OutputErrorCategory.BUSINESS_RULE


def test_reuse_assessment_rejects_excerpt_id_outside_current_context() -> None:
    payload = {
        "reuse_feasibility": 4,
        "reuse_feasibility_reason_zh": "开放数据与代码可直接接入现有流程。",
        "required_adaptations": [],
        "excerpt_kind": "availability",
        "excerpt_ids": ["secret-unknown-excerpt"],
    }
    context = ReuseAssessmentContext(excerpt_kinds={"availability-1": "availability"})

    with pytest.raises(OutputValidationError) as captured:
        validate_output("reuse_assessment", payload, context=context)

    assert captured.value.issues[0].location == "$.excerpt_ids[0]"
    assert captured.value.issues[0].category is OutputErrorCategory.BUSINESS_RULE
    assert "secret-unknown-excerpt" not in str(captured.value)


@pytest.mark.parametrize(
    ("excerpt_kind", "excerpt_ids"),
    [
        ("availability", ["methods-1"]),
        ("methods", ["availability-1"]),
        ("both", ["availability-1"]),
        ("both", ["methods-1"]),
        ("availability", ["availability-1", "methods-1"]),
        ("methods", ["availability-1", "methods-1"]),
    ],
)
def test_reuse_assessment_excerpt_kind_must_match_referenced_kinds(
    excerpt_kind: str,
    excerpt_ids: list[str],
) -> None:
    payload = {
        "reuse_feasibility": 4,
        "reuse_feasibility_reason_zh": "所引摘录支持该复用判断。",
        "required_adaptations": [],
        "excerpt_kind": excerpt_kind,
        "excerpt_ids": excerpt_ids,
    }
    context = ReuseAssessmentContext(
        excerpt_kinds={
            "availability-1": "availability",
            "methods-1": "methods",
        }
    )

    with pytest.raises(OutputValidationError) as captured:
        validate_output("reuse_assessment", payload, context=context)

    assert captured.value.issues[-1].location == "$.excerpt_kind"
    assert captured.value.issues[-1].category is OutputErrorCategory.BUSINESS_RULE


@pytest.mark.parametrize("reason", ["", " \t\n ", "待补充"])
def test_reuse_assessment_rejects_blank_or_placeholder_reason(reason: str) -> None:
    payload = {
        "reuse_feasibility": 4,
        "reuse_feasibility_reason_zh": reason,
        "required_adaptations": [],
        "excerpt_kind": "methods",
        "excerpt_ids": ["methods-1"],
    }
    context = ReuseAssessmentContext(excerpt_kinds={"methods-1": "methods"})

    with pytest.raises(OutputValidationError) as captured:
        validate_output("reuse_assessment", payload, context=context)

    assert captured.value.issues[0].location == "$.reuse_feasibility_reason_zh"
    assert captured.value.issues[0].category is OutputErrorCategory.INVALID_TEXT


@pytest.mark.parametrize("adaptation", ["", "  ", "暂无"])
def test_reuse_assessment_rejects_invalid_required_adaptation(
    adaptation: str,
) -> None:
    payload = {
        "reuse_feasibility": 3,
        "reuse_feasibility_reason_zh": "方法可复用，但需要适配本地资料。",
        "required_adaptations": [adaptation],
        "excerpt_kind": "methods",
        "excerpt_ids": ["methods-1"],
    }
    context = ReuseAssessmentContext(excerpt_kinds={"methods-1": "methods"})

    with pytest.raises(OutputValidationError) as captured:
        validate_output("reuse_assessment", payload, context=context)

    assert captured.value.issues[0].location == "$.required_adaptations[0]"
    assert captured.value.issues[0].category is OutputErrorCategory.INVALID_TEXT


@pytest.mark.parametrize(
    ("excerpt_kind", "excerpt_ids"),
    [
        ("availability", ["availability-1"]),
        ("methods", ["methods-1"]),
        ("both", ["availability-1", "methods-1"]),
        ("availability", ["availability-2"]),
        ("methods", ["methods-2"]),
    ],
)
def test_reuse_assessment_accepts_single_kinds_both_and_context_subsets(
    excerpt_kind: str,
    excerpt_ids: list[str],
) -> None:
    payload = _valid_payload()
    payload["excerpt_kind"] = excerpt_kind
    payload["excerpt_ids"] = excerpt_ids

    result = validate_output(
        "reuse_assessment",
        payload,
        context=_context_mapping(),
    )

    assert result.excerpt_ids == excerpt_ids


def test_reuse_assessment_allows_empty_and_duplicate_adaptations() -> None:
    payload = _valid_payload()
    payload["required_adaptations"] = []
    empty_result = validate_output(
        "reuse_assessment", payload, context=_context_mapping()
    )

    payload["required_adaptations"] = ["转换网格。", "转换网格。"]
    duplicate_result = validate_output(
        "reuse_assessment", payload, context=_context_mapping()
    )

    assert empty_result.required_adaptations == []
    assert duplicate_result.required_adaptations == ["转换网格。", "转换网格。"]


def test_methods_context_represents_selector_methods_or_data_excerpts() -> None:
    payload = _valid_payload()
    payload["excerpt_kind"] = "methods"
    payload["excerpt_ids"] = ["selector-data-1"]

    result = validate_output(
        "reuse_assessment",
        payload,
        context={"excerpt_kinds": {"selector-data-1": "methods"}},
    )

    assert result.excerpt_kind == "methods"


def test_reuse_assessment_schema_has_exactly_five_required_fields() -> None:
    assert set(ReuseAssessmentOutput.model_fields) == {
        "reuse_feasibility",
        "reuse_feasibility_reason_zh",
        "required_adaptations",
        "excerpt_kind",
        "excerpt_ids",
    }
    assert all(
        field.is_required() for field in ReuseAssessmentOutput.model_fields.values()
    )


@pytest.mark.parametrize(
    ("mutate", "category", "location"),
    [
        (
            lambda payload: payload.pop("excerpt_kind"),
            OutputErrorCategory.MISSING_FIELD,
            "$.excerpt_kind",
        ),
        (
            lambda payload: payload.update({"accepted": True}),
            OutputErrorCategory.EXTRA_FIELD,
            "$.<额外字段>",
        ),
        (
            lambda payload: payload.update({"required_adaptations": "转换网格"}),
            OutputErrorCategory.INVALID_TYPE,
            "$.required_adaptations",
        ),
        (
            lambda payload: payload.update({"excerpt_kind": "data"}),
            OutputErrorCategory.INVALID_ENUM,
            "$.excerpt_kind",
        ),
    ],
)
def test_reuse_assessment_rejects_invalid_structure(
    mutate: Callable[[dict[str, object]], object],
    category: OutputErrorCategory,
    location: str,
) -> None:
    payload = _valid_payload()
    mutate(payload)

    with pytest.raises(OutputValidationError) as captured:
        validate_output("reuse_assessment", payload, context=_context_mapping())

    assert captured.value.issues[0].category is category
    assert captured.value.issues[0].location == location


def test_reuse_assessment_rejects_truncated_json() -> None:
    with pytest.raises(OutputValidationError) as captured:
        validate_output(
            "reuse_assessment",
            '{"reuse_feasibility":4,"reuse_feasibility_reason_zh":',
            context=_context_mapping(),
        )

    assert captured.value.issues[0].category is OutputErrorCategory.INVALID_JSON
    assert captured.value.issues[0].location == "$"


@pytest.mark.parametrize(
    "invalid_score",
    [0, 6, True, False, 1.0, "1"],
)
def test_reuse_assessment_requires_a_strict_one_to_five_integer(
    invalid_score: object,
) -> None:
    payload = _valid_payload()
    payload["reuse_feasibility"] = invalid_score

    with pytest.raises(OutputValidationError) as captured:
        validate_output("reuse_assessment", payload, context=_context_mapping())

    expected_category = (
        OutputErrorCategory.BUSINESS_RULE
        if invalid_score in (0, 6) and type(invalid_score) is int
        else OutputErrorCategory.INVALID_TYPE
    )
    assert captured.value.issues[0].category is expected_category
    assert captured.value.issues[0].location == "$.reuse_feasibility"


@pytest.mark.parametrize(
    ("context", "category", "location"),
    [
        (None, OutputErrorCategory.MISSING_CONTEXT, "$.context"),
        ({}, OutputErrorCategory.MISSING_CONTEXT, "$.context.excerpt_kinds"),
        ([], OutputErrorCategory.CONTEXT_MISMATCH, "$.context"),
        (
            {"excerpt_kinds": {"data-1": "data"}},
            OutputErrorCategory.CONTEXT_MISMATCH,
            "$.context.excerpt_kinds.<额外字段>",
        ),
        (
            {"excerpt_kinds": {}, "secret-extra-context": "secret-value"},
            OutputErrorCategory.CONTEXT_MISMATCH,
            "$.context.<额外字段>",
        ),
    ],
)
def test_reuse_assessment_requires_complete_controlled_context(
    context: object,
    category: OutputErrorCategory,
    location: str,
) -> None:
    with pytest.raises(OutputValidationError) as captured:
        validate_output("reuse_assessment", _valid_payload(), context=context)

    assert captured.value.issues[0].category is category
    assert captured.value.issues[0].location == location


def test_reuse_assessment_context_mapping_is_not_mutated() -> None:
    context = _context_mapping()
    original = deepcopy(context)

    validate_output("reuse_assessment", _valid_payload(), context=context)

    assert context == original


def test_reuse_assessment_failures_do_not_leak_response_or_excerpt_context(
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    markers = (
        "secret-response-marker",
        "secret-excerpt-id",
        "secret-excerpt-text",
    )
    payload = _valid_payload()
    payload[markers[0]] = markers[2]
    payload["excerpt_ids"] = [markers[1]]
    context = {
        "excerpt_kinds": {"availability-1": "availability"},
        markers[2]: markers[0],
    }

    rendered_errors: list[str] = []
    failing_calls: tuple[Callable[[], object], ...] = (
        lambda: validate_output(
            "reuse_assessment", payload, context=_context_mapping()
        ),
        lambda: validate_output("reuse_assessment", _valid_payload(), context=context),
    )
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
    assert "validation error for ReuseAssessmentOutput" not in public_surface
    assert "pydantic_core" not in public_surface
    assert "Traceback" not in public_surface
