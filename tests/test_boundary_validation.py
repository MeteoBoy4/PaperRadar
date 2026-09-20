from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from types import MappingProxyType

import pytest

from paper_radar.screening import (
    BoundaryOutput,
    OutputErrorCategory,
    OutputKind,
    OutputValidationError,
    validate_output,
)


def test_validate_boundary_structure_returns_authoritative_type_without_mutation() -> (
    None
):
    payload = {
        "boundary": "in_scope",
        "reason_zh": "该研究直接讨论目标区域的极端降水机制。",
    }
    original = deepcopy(payload)

    result = validate_output("boundary", payload)

    assert result == BoundaryOutput(
        boundary="in_scope",
        reason_zh="该研究直接讨论目标区域的极端降水机制。",
    )
    assert payload == original


@pytest.mark.parametrize("boundary", ["in_scope", "out_of_scope", "uncertain"])
def test_validate_boundary_json_accepts_every_controlled_value(boundary: str) -> None:
    reason = "该文使用 ERA5 资料，但研究问题仍属于用户界定的范围。"
    payload = f'{{"boundary":"{boundary}","reason_zh":"{reason}"}}'

    result = validate_output("boundary", payload)

    assert result.boundary == boundary
    assert result.reason_zh == reason


@pytest.mark.parametrize(
    ("payload", "category", "location"),
    [
        (
            {"reason_zh": "研究对象属于当前研究范围。"},
            OutputErrorCategory.MISSING_FIELD,
            "$.boundary",
        ),
        (
            {
                "boundary": "in_scope",
                "reason_zh": "研究对象属于当前研究范围。",
                "unexpected": "sensitive-extra-value",
            },
            OutputErrorCategory.EXTRA_FIELD,
            "$.<额外字段>",
        ),
        (
            {"boundary": 1, "reason_zh": "研究对象属于当前研究范围。"},
            OutputErrorCategory.INVALID_TYPE,
            "$.boundary",
        ),
        (
            {"boundary": "sideways", "reason_zh": "研究对象属于当前研究范围。"},
            OutputErrorCategory.INVALID_ENUM,
            "$.boundary",
        ),
        (
            {"boundary": "in_scope", "reason_zh": ["不是字符串"]},
            OutputErrorCategory.INVALID_TYPE,
            "$.reason_zh",
        ),
        (
            '{"boundary":"in_scope","reason_zh":',
            OutputErrorCategory.INVALID_JSON,
            "$",
        ),
    ],
)
def test_invalid_boundary_structure_has_controlled_error(
    payload: object,
    category: OutputErrorCategory,
    location: str,
) -> None:
    original = deepcopy(payload)

    with pytest.raises(OutputValidationError) as captured:
        validate_output("boundary", payload)

    assert captured.value.issues[0].category is category
    assert captured.value.issues[0].location == location
    assert payload == original


@pytest.mark.parametrize(
    "reason_zh",
    [
        "",
        " \t\n ",
        "无",
        "暂无",
        "未知",
        "待定",
        "待补充",
        "稍后补充",
        "占位",
        "无内容",
        "不详",
        "-",
        "--",
        "...",
        "…",
        "N/A",
        "NA",
        "TBD",
        "TODO",
        "placeholder",
    ],
)
def test_boundary_reason_rejects_blank_and_explicit_placeholder_text(
    reason_zh: str,
) -> None:
    with pytest.raises(OutputValidationError) as captured:
        validate_output(
            "boundary",
            {"boundary": "uncertain", "reason_zh": reason_zh},
        )

    assert len(captured.value.issues) == 1
    assert captured.value.issues[0].category is OutputErrorCategory.INVALID_TEXT
    assert captured.value.issues[0].location == "$.reason_zh"


def test_boundary_reason_preserves_legal_original_terms_exactly() -> None:
    reason = "N/A 是来源字段名；该文仍明确讨论 ENSO 对极端降水的影响。"

    result = validate_output(
        "boundary",
        {"boundary": "in_scope", "reason_zh": reason},
    )

    assert result.reason_zh == reason


@pytest.mark.parametrize("context", [None, {}, MappingProxyType({})])
def test_boundary_accepts_no_context_or_an_empty_mapping(context: object) -> None:
    result = validate_output(
        OutputKind.BOUNDARY,
        {"boundary": "out_of_scope", "reason_zh": "研究对象超出画像边界。"},
        context=context,
    )

    assert result.boundary == "out_of_scope"


def test_boundary_authoritative_schema_contains_only_declared_fields() -> None:
    assert set(BoundaryOutput.model_fields) == {"boundary", "reason_zh"}


@pytest.mark.parametrize(
    ("kind", "context", "category", "location"),
    [
        (
            "read_analysis",
            None,
            OutputErrorCategory.UNKNOWN_KIND,
            "$.kind",
        ),
        (
            "boundary",
            {"topic_ids": ["topic-secret"]},
            OutputErrorCategory.CONTEXT_MISMATCH,
            "$.context",
        ),
        (
            "boundary",
            ["not-a-read-only-mapping"],
            OutputErrorCategory.CONTEXT_MISMATCH,
            "$.context",
        ),
    ],
)
def test_unknown_kind_and_mismatched_context_fail_with_controlled_error(
    kind: object,
    context: object,
    category: OutputErrorCategory,
    location: str,
) -> None:
    with pytest.raises(OutputValidationError) as captured:
        validate_output(
            kind,
            {"boundary": "in_scope", "reason_zh": "研究内容属于画像边界。"},
            context=context,
        )

    assert captured.value.issues[0].category is category
    assert captured.value.issues[0].location == location


def test_public_failures_do_not_leak_input_or_pydantic_details(
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    markers = (
        "sk-secret-api-key",
        "secret-profile-marker",
        "secret-abstract-marker",
        "secret-body-marker",
        "secret-excerpt-marker",
        "secret-response-marker",
        "secret-prompt-marker",
    )
    failing_calls: tuple[Callable[[], object], ...] = (
        lambda: validate_output(
            markers[0],
            {"boundary": "in_scope", "reason_zh": "合法理由"},
            context=None,
        ),
        lambda: validate_output(
            "boundary",
            {
                "boundary": "in_scope",
                "reason_zh": markers[1],
                markers[2]: markers[3],
            },
        ),
        lambda: validate_output(
            "boundary",
            f'{{"boundary":"in_scope","reason_zh":"{markers[4]}"',
        ),
        lambda: validate_output(
            "boundary",
            {"boundary": "uncertain", "reason_zh": "合法理由"},
            context={markers[5]: markers[6]},
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
    assert "validation error for BoundaryOutput" not in public_surface
    assert "pydantic_core" not in public_surface
    assert "Traceback" not in public_surface
