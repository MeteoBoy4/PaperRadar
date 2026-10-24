"""Read 原始候选与只读消费上下文的公共接收。"""

import json
from typing import Any

import pytest

from paper_radar.reading import (
    Evidence,
    ExtractionIdentity,
    PageFact,
    Provenance,
    ReadContext,
    ReadContextError,
    ReadOutputError,
    SourceBlock,
    validate_read_output,
)
from tests.read_support import candidate, context_for


def test_valid_read_preserves_binding_and_replays_only_original_source() -> None:
    identity = ExtractionIdentity("extraction-1", "reading-1", "map-1")
    source = "降水增加了30%，ERA5 与 CMIP6 一致。"
    context = ReadContext(
        identity=identity,
        expected_language="zh",
        pages=[PageFact(identity, 3, 600, 800, "top_left")],
        source_blocks=[SourceBlock(identity, "s1", source)],
        evidence=[
            Evidence(
                identity, "e1", [Provenance("s1", 3, (0, 0, 600, 800), 0, len(source))]
            )
        ],
    )
    raw = candidate(
        main_findings=[
            {"statement": "降水增加了30%。", "evidence": [{"evidence_id": "e1"}]}
        ]
    )
    result = validate_read_output(raw, context)
    assert result.identity == identity
    assert result.mode == "single"
    assert result.analysis.main_findings[0].statement == "降水增加了30%。"
    assert result.support[0].text == source
    assert result.diagnostics == ()
    assert result.warnings == ()


@pytest.mark.parametrize(
    "raw",
    [
        b'{"output_language":"zh","output_language":"en"}',
        b'{"unknown":{"a":1,"a":2}}',
        b'{"a":NaN}',
        b'{"a":Infinity}',
        b'{"a":-Infinity}',
        b'{"a":"\\ud800"}',
        b'{"a":{"\\udfff":0}}',
        b"\xff",
        b"\xef\xbb\xbf{}",
        b"{} trailing",
        b"```json\n{}\n```",
        b"{",
        b"[]",
        b"null",
        b'"text"',
        b"42",
        b'{"a":1e999}',
    ],
)
def test_strict_raw_json_rejection_has_safe_category_and_no_exception_chain(
    raw: bytes,
) -> None:
    with pytest.raises(ReadOutputError) as error:
        validate_read_output(raw, context_for())
    assert [(i.location, i.category.value) for i in error.value.issues] == [
        ("$", "invalid_json")
    ]
    assert error.value.__cause__ is error.value.__context__ is None


@pytest.mark.parametrize("raw", ["{}", bytearray(b"{}"), {}, None])
def test_only_original_bytes_are_a_candidate(raw: Any) -> None:
    with pytest.raises(ReadOutputError) as error:
        validate_read_output(raw, context_for())
    assert error.value.issues[0].category.value == "invalid_type"


def test_missing_context_is_callers_error() -> None:
    with pytest.raises(ReadContextError) as error:
        validate_read_output(candidate(), None)  # type: ignore[arg-type]
    assert error.value.issues[0].category.value == "invalid_context"
    assert not isinstance(error.value, ReadOutputError)


@pytest.mark.parametrize(
    ("change", "location", "category"),
    [
        ({"research_value": True}, "$.research_value", "invalid_type"),
        ({"reuse_feasibility": 3.0}, "$.reuse_feasibility", "invalid_type"),
        ({"research_value": 6}, "$.research_value", "invalid_score"),
        ({"value_types": ["other"]}, "$.value_types[0]", "invalid_enum"),
        (
            {"value_types": ["method", "method"]},
            "$.value_types[1]",
            "duplicate_value_type",
        ),
        ({"value_types": []}, "$.value_types", "value_types_required"),
        ({"output_language": "en"}, "$.output_language", "language_mismatch"),
        ({"next_action": "!!!"}, "$.next_action", "invalid_text"),
        ({"data_summary": "无"}, "$.data_summary", "invalid_text"),
        ({"open_questions": [" "]}, "$.open_questions[0]", "invalid_text"),
        (
            {"degraded_content_warnings": ["TBD"]},
            "$.degraded_content_warnings[0]",
            "invalid_text",
        ),
        (
            {"required_adaptations": ["？？？"]},
            "$.required_adaptations[0]",
            "invalid_text",
        ),
        ({"secret-extra-key": "SENSITIVE"}, "$.<额外字段>", "extra_field"),
    ],
)
def test_structure_and_business_rejections_are_safe(
    change: dict[str, Any], location: str, category: str
) -> None:
    with pytest.raises(ReadOutputError) as error:
        validate_read_output(candidate(**change), context_for())
    assert (error.value.issues[0].location, error.value.issues[0].category.value) == (
        location,
        category,
    )
    assert "SENSITIVE" not in str(error.value)
    assert "secret-extra-key" not in repr(error.value)
    assert error.value.__context__ is None


@pytest.mark.parametrize(
    "field",
    [
        "main_findings",
        "research_value_reason",
        "reuse_feasibility_reason",
        "key_limitations",
        "reusable_points",
    ],
)
@pytest.mark.parametrize(
    ("references", "category"),
    [
        ([], "evidence_required"),
        (["e1", "e1"], "duplicate_evidence"),
        (["other-secret"], "unknown_evidence"),
        ([" e1"], "invalid_evidence_id"),
    ],
)
def test_each_protected_field_has_nonempty_unique_known_references(
    field: str, references: list[str], category: str
) -> None:
    content: dict[str, Any] = {
        "statement": "需要证据的完整陈述。",
        "evidence": [{"evidence_id": value} for value in references],
    }
    if field == "reusable_points":
        content = {
            "item": "一个可复用的方法。",
            "how_to_reuse": "比较公开数据。",
            "evidence": content["evidence"],
        }
    value: Any = (
        [content]
        if field in ("main_findings", "key_limitations", "reusable_points")
        else content
    )
    with pytest.raises(ReadOutputError) as error:
        validate_read_output(candidate(**{field: value}), context_for())
    assert any(
        i.category.value == category and i.location.startswith("$." + field)
        for i in error.value.issues
    )
    assert "other-secret" not in str(error.value)


def test_accepted_bytes_and_model_warnings_remain_exact_and_repeated() -> None:
    raw = (
        b" \n"
        + candidate(
            research_value=2,
            value_types=[],
            degraded_content_warnings=["模型已有警告。", "模型已有警告。"],
            next_action="立即优先检查第999个参数。",
        )
        + b"\t "
    )
    context = context_for()
    result = validate_read_output(raw, context)
    assert result.model_warnings == ("模型已有警告。", "模型已有警告。")
    assert [w.origin for w in result.warnings] == ["model", "model"]
    assert result == validate_read_output(raw, context)
    assert json.loads(raw)["next_action"] == result.analysis.next_action
    assert result.diagnostics == ()


@pytest.mark.parametrize(
    "field",
    [
        "one_sentence_conclusion",
        "research_question",
        "methods_summary",
        "data_summary",
        "why_it_matters",
        "next_action",
    ],
)
def test_each_required_narrative_rejects_pure_punctuation(field: str) -> None:
    with pytest.raises(ReadOutputError) as error:
        validate_read_output(candidate(**{field: "!!!"}), context_for())
    assert (error.value.issues[0].location, error.value.issues[0].category.value) == (
        "$." + field,
        "invalid_text",
    )


@pytest.mark.parametrize("score", [1, 2, 3, 4, 5])
def test_each_independent_score_in_closed_range_is_accepted(score: int) -> None:
    output = validate_read_output(
        candidate(research_value=score, reuse_feasibility=6 - score), context_for()
    ).analysis
    assert (output.research_value, output.reuse_feasibility) == (score, 6 - score)


@pytest.mark.parametrize(
    "value_type",
    [
        "method",
        "data",
        "code_tool",
        "theory_mechanism",
        "evidence_conclusion",
        "question_hypothesis",
        "review_knowledge_map",
    ],
)
def test_each_frozen_value_type_is_accepted_by_the_public_entry(
    value_type: str,
) -> None:
    output = validate_read_output(
        candidate(value_types=[value_type]), context_for()
    ).analysis
    assert output.value_types[0].value == value_type


def test_complete_english_analysis_is_preserved_without_language_guessing() -> None:
    reason = {
        "statement": "The method offers an independent comparison.",
        "evidence": [{"evidence_id": "e1"}],
    }
    raw = candidate(
        output_language="en",
        one_sentence_conclusion="The study compares precipitation estimates.",
        research_question="How can estimates be compared?",
        methods_summary="Use independent observations.",
        data_summary="The study uses public observations.",
        main_findings=[reason],
        research_value_reason=reason,
        reuse_feasibility_reason=reason,
        reusable_points=[
            {
                "item": "An independent evaluation.",
                "how_to_reuse": "Compare the observations.",
                "evidence": [{"evidence_id": "e1"}],
            }
        ],
        key_limitations=[reason],
        why_it_matters="It provides an evaluation method.",
        next_action="Check the hypotheses.",
    )
    result = validate_read_output(
        raw,
        context_for(
            "The method offers an independent comparison.", expected_language="en"
        ),
    )
    assert result.analysis.output_language == "en"
    assert (
        result.analysis.one_sentence_conclusion
        == "The study compares precipitation estimates."
    )
    assert result.diagnostics == ()
