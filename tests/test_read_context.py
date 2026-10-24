"""全部给定上下文成员在调用模型前保持闭包与不可变。"""

from dataclasses import replace
from typing import Any

import pytest

from paper_radar.reading import (
    Evidence,
    ExtractionIdentity,
    PageFact,
    Provenance,
    ReadContextError,
    SourceBlock,
    validate_read_output,
)
from tests.read_support import candidate, context_for

IDENTITY = ExtractionIdentity("extraction-1", "reading-1", "map-1")


@pytest.mark.parametrize(
    ("changes", "location", "category"),
    [
        ({"expected_language": None}, "$.expected_language", "invalid_context"),
        ({"expected_language": "fr"}, "$.expected_language", "invalid_context"),
        ({"mode": "reduce"}, "$.allowed_evidence", "missing_allowed_evidence"),
        ({"identity": ("wrong",)}, "$.identity", "invalid_identity"),
        (
            {"pages": [PageFact(IDENTITY, 3, 600, 800, "top_left")] * 2},
            "$.pages[1]",
            "duplicate_id",
        ),
        (
            {"source_blocks": [SourceBlock(IDENTITY, "s1", "正文。")] * 2},
            "$.source_blocks[1]",
            "duplicate_id",
        ),
        (
            {
                "evidence": [
                    Evidence(IDENTITY, "e1", (Provenance("s1", 3, (0, 0, 1, 1), 0, 1),))
                ]
                * 2
            },
            "$.evidence[1]",
            "duplicate_id",
        ),
        (
            {
                "source_blocks": [
                    SourceBlock(
                        ExtractionIdentity("extraction-1", "reading-1", "other-map"),
                        "s1",
                        "正文。",
                    )
                ]
            },
            "$.source_blocks[0].identity",
            "identity_mismatch",
        ),
        (
            {
                "pages": [
                    PageFact(
                        ExtractionIdentity("other", "reading-1", "map-1"),
                        3,
                        600,
                        800,
                        "top_left",
                    )
                ]
            },
            "$.pages[0].identity",
            "identity_mismatch",
        ),
        (
            {
                "source_blocks": [
                    SourceBlock(IDENTITY, "s1", "正文。", "formula_candidate")  # type: ignore[arg-type]
                ]
            },
            "$.source_blocks[0].kind",
            "invalid_source",
        ),
        (
            {"source_blocks": [SourceBlock(IDENTITY, "s1", "正文。", "table")]},
            "$.source_blocks[0].kind",
            "unsupported_source",
        ),
        (
            {"source_blocks": [SourceBlock(IDENTITY, "s1", "正文。", unreliable=True)]},
            "$.source_blocks[0].unreliable",
            "unsupported_source",
        ),
    ],
)
def test_context_rejects_invalid_or_unsupported_members(
    changes: dict[str, Any], location: str, category: str
) -> None:
    with pytest.raises(ReadContextError) as error:
        context_for(**changes)
    assert (error.value.issues[0].location, error.value.issues[0].category.value) == (
        location,
        category,
    )


@pytest.mark.parametrize("page", [True, False, 0, -1, 3.0, "3"])
def test_original_page_number_is_strict_positive_integer(page: Any) -> None:
    with pytest.raises(ReadContextError) as error:
        context_for(pages=[PageFact(IDENTITY, page, 600, 800, "top_left")])
    assert error.value.issues[0].category.value == "invalid_page"


@pytest.mark.parametrize("dimension", [True, 0, -1, float("nan"), float("inf"), "600"])
def test_page_dimensions_are_finite_positive_points(dimension: Any) -> None:
    with pytest.raises(ReadContextError) as error:
        context_for(pages=[PageFact(IDENTITY, 3, dimension, 800, "top_left")])
    assert error.value.issues[0].location == "$.pages[0]"
    assert error.value.issues[0].category.value == "invalid_page"


@pytest.mark.parametrize(
    "bbox",
    [
        (0, 0, 0, 1),
        (-1, 0, 1, 1),
        (0, 0, 601, 1),
        (0, 0, 1, 801),
        (0, 0, float("inf"), 1),
        (False, 0, 1, 1),
        (1, 0, 0, 1),
        (0, 0, 1),
    ],
)
def test_each_bbox_is_exact_non_degenerate_and_within_page(bbox: Any) -> None:
    with pytest.raises(ReadContextError) as error:
        context_for(
            evidence=[Evidence(IDENTITY, "e1", (Provenance("s1", 3, bbox, 0, 1),))]
        )
    assert (error.value.issues[0].location, error.value.issues[0].category.value) == (
        "$.evidence[0].provenance[0].bbox",
        "invalid_bbox",
    )


@pytest.mark.parametrize(
    ("start", "end"),
    [(True, 1), (0, False), (-1, 1), (1, 1), (2, 1), (0, 100), (0.0, 1)],
)
def test_charspan_uses_original_unicode_code_points(start: Any, end: Any) -> None:
    with pytest.raises(ReadContextError) as error:
        context_for(
            evidence=[
                Evidence(
                    IDENTITY, "e1", (Provenance("s1", 3, (0, 0, 1, 1), start, end),)
                )
            ]
        )
    assert error.value.issues[0].category.value == "invalid_charspan"


@pytest.mark.parametrize(
    ("provenance", "category"),
    [
        (
            (Provenance("formula-candidate-secret", 3, (0, 0, 1, 1), 0, 1),),
            "unknown_source",
        ),
        ((Provenance("s1", 2, (0, 0, 1, 1), 0, 1),), "unknown_page"),
        ((Provenance("s1", 3, (0, 0, 1, 1), 0, 1),) * 2, "duplicate_provenance"),
        ((), "empty_support"),
    ],
)
def test_provenance_closure_is_checked_for_every_member(
    provenance: Any, category: str
) -> None:
    with pytest.raises(ReadContextError) as error:
        context_for(evidence=[Evidence(IDENTITY, "e1", provenance)])
    assert error.value.issues[0].category.value == category
    assert "secret" not in str(error.value)


@pytest.mark.parametrize("identifier", ["", " e1", "e1 ", "e\n1", "e\x001"])
def test_evidence_id_is_not_trimmed_or_normalized(identifier: str) -> None:
    with pytest.raises(ReadContextError) as error:
        context_for(
            evidence=[
                Evidence(
                    IDENTITY, identifier, (Provenance("s1", 3, (0, 0, 1, 1), 0, 1),)
                )
            ]
        )
    assert error.value.issues[0].category.value == "invalid_evidence_id"


def test_every_provenance_is_preserved_without_normalization_or_page_sorting() -> None:
    source = " Ａ中👩‍🔬e\u0301 \n"
    first = Provenance("s1", 9, (0, 0, 600, 800), 1, 6)
    second = Provenance("s1", 3, (0, 0, 1, 1), 6, 8)
    context = context_for(
        source,
        pages=[
            PageFact(IDENTITY, 9, 600, 800, "bottom_left"),
            PageFact(IDENTITY, 3, 600, 800, "top_left"),
        ],
        evidence=[Evidence(IDENTITY, "e1", [first, second])],
    )
    assert tuple(s.text for s in context.replay()) == ("Ａ中👩‍🔬", "e\u0301")
    assert tuple(s.provenance.page_no for s in context.replay()) == (9, 3)
    assert context.pages[0].origin == "bottom_left"


def test_whitespace_support_is_not_valid_evidence() -> None:
    with pytest.raises(ReadContextError) as error:
        context_for(" \n\u3000")
    assert error.value.issues[0].category.value == "empty_support"


def test_context_and_result_defensively_freeze_caller_containers() -> None:
    bbox: Any = [0, 0, 600, 800]
    provenance: Any = [Provenance("s1", 3, bbox, 0, 3)]
    evidence: Any = [Evidence(IDENTITY, "e1", provenance)]
    pages: Any = [PageFact(IDENTITY, 3, 600, 800, "top_left")]
    sources: Any = [SourceBlock(IDENTITY, "s1", "原字符。")]
    context = context_for(pages=pages, source_blocks=sources, evidence=evidence)
    bbox[2] = -1
    provenance.clear()
    evidence.clear()
    pages.clear()
    sources.clear()
    result = validate_read_output(candidate(), context)
    assert result.support[0].text == "原字符"
    analysis = result.analysis
    analysis.value_types.clear()
    analysis.research_value_reason.evidence.clear()
    assert len(result.analysis.value_types) == 1
    assert len(result.analysis.research_value_reason.evidence) == 1


def test_unused_invalid_provenance_cannot_hide_in_context() -> None:
    context = context_for()
    bad = replace(
        context.evidence[0],
        evidence_id="unused",
        provenance=(Provenance("s1", 3, (0, 0, 1, 1), 0, 999),),
    )
    with pytest.raises(ReadContextError) as error:
        context_for(evidence=[*context.evidence, bad])
    assert error.value.issues[0].location == "$.evidence[1].provenance[0].charspan"


def test_duplicate_provenance_cannot_hide_behind_list_and_tuple_bbox_forms() -> None:
    bbox: Any = [0, 0, 1, 1]
    with pytest.raises(ReadContextError) as error:
        context_for(
            evidence=[
                Evidence(
                    IDENTITY,
                    "e1",
                    [
                        Provenance("s1", 3, bbox, 0, 1),
                        Provenance("s1", 3, (0, 0, 1, 1), 0, 1),
                    ],
                )
            ]
        )
    assert error.value.issues[0].category.value == "duplicate_provenance"


def test_omitted_identity_is_a_controlled_context_error() -> None:
    from paper_radar.reading import ReadContext

    with pytest.raises(ReadContextError) as error:
        ReadContext(expected_language="zh")
    assert error.value.issues[0].category.value == "invalid_identity"


@pytest.mark.parametrize(
    "identity",
    [
        ExtractionIdentity("extraction-1", "other-reading", "map-1"),
        ExtractionIdentity("extraction-1", "reading-1", "other-map"),
    ],
)
def test_same_fingerprint_with_different_consumption_hash_is_not_interchangeable(
    identity: ExtractionIdentity,
) -> None:
    with pytest.raises(ReadContextError) as error:
        context_for(
            evidence=[
                Evidence(identity, "e1", [Provenance("s1", 3, (0, 0, 1, 1), 0, 1)])
            ]
        )
    assert error.value.issues[0].category.value == "identity_mismatch"


@pytest.mark.parametrize("page", [True, 3.0, "3"])
def test_provenance_page_does_not_coerce_to_an_existing_number(page: Any) -> None:
    with pytest.raises(ReadContextError) as error:
        context_for(
            evidence=[
                Evidence(IDENTITY, "e1", [Provenance("s1", page, (0, 0, 1, 1), 0, 1)])
            ]
        )
    assert error.value.issues[0].category.value == "unknown_page"
