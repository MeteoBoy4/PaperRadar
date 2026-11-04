"""D1:新增质量闭集、DTO、中文指引与共享 unreliable 语义。"""

from dataclasses import replace

import pytest

from paper_radar.content_reliability import is_unreliable
from paper_radar.eligibility import (
    Concept,
    PaperProjection,
    QualityBasis,
    QualityFact,
    QualityFailure,
    evaluate_paper,
)
from paper_radar.eligibility.presentation import (
    QUALITY_FAILURE_GUIDANCE,
    quality_failure_guidance,
)


@pytest.mark.parametrize(
    "failure",
    [
        QualityFailure.SOURCE_GENERATED_SEPARATION,
        QualityFailure.EMBEDDED_BINARY,
        QualityFailure.TEXT_INTEGRITY,
    ],
)
def test_new_failures_survive_eligibility_dto_with_chinese_guidance(
    failure: QualityFailure,
) -> None:
    facts = PaperProjection(
        paper_id="paper", version_id="version", current_version_id="version"
    )
    projected = replace(
        facts, quality=QualityFact(QualityBasis.FAILED, "extraction", failure)
    )
    result = evaluate_paper(projected)[Concept.READ_PREREQUISITES]
    assert result.quality_failure == failure
    assert "quality_failed" in result.reasons
    assert any(
        "\u4e00" <= char <= "\u9fff" for char in quality_failure_guidance(failure)
    )
    assert set(QUALITY_FAILURE_GUIDANCE) == set(QualityFailure)


@pytest.mark.parametrize(
    ("text", "declared", "expected"),
    [
        ("α = 2", False, False),
        ("普通字符", False, False),
        ("tab\tline\n", False, False),
        ("\ue000", False, True),
        ("\ufffd", False, True),
        ("\x00", False, True),
        ("ordinary", True, True),
    ],
)
def test_unreliable_predicate_has_one_normalization_source(
    text: str, declared: bool, expected: bool
) -> None:
    assert is_unreliable(text, declared=declared) is expected
