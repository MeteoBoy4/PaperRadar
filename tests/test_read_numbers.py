"""数值 v1 独立固定向量;全部通过 Read 公共入口。"""

import pytest

from paper_radar.reading import (
    Evidence,
    ExtractionIdentity,
    Provenance,
    SourceBlock,
    validate_read_output,
)
from tests.read_support import candidate, context_for

# 本组字面量供受限矩阵/恢复组合复用,预期独立于识别器。
NUMBER_MATCH_VECTORS = (
    ("增加了30%", "increased by 30%"),
    ("降水增加了30%，ERA5 与 CMIP6 一致", "increased by 30%"),
    ("两套方案和三倍改进", "无对应阿拉伯数字"),
    ("ERA5 CMIP6 PM2.5 CO2 O3 H2O", "普通原文"),
    ("图 3 表 2 式 (5) 节 4", "普通原文"),
    ("Fig. 3 Figure 2 Table 4 Eq. (5) Section 6", "普通原文"),
    ("30°N", "30 degrees north"),
    ("1979–2020", "between 1979 and 2020"),
    ("(Smith et al., 2020)", "2020"),
    ("温度为−3.5摄氏度", "-3.5 °C"),
    ("５００ 百帕", "500-hPa"),
    ("850 hPa", "850-hPa"),
    ("2 m", "2-m"),
    ("1,000 km", "1000 千米"),
    ("30 %", "30%"),
    ("3～5 公里", "3 to 5 km"),
    ("3至5 km", "3–5 km"),
    ("3-5 km", "3 to 5 km"),
    ("1.2e-3", "1.2×10⁻³"),
    ("1.2×10⁴", "1.2e4"),
    ("10⁻³", "1e-3"),
    ("±0.5", "±0.5"),
    ("速度为3米/秒", "3 m s−1"),
    ("速度为3 m/s", "3 m s⁻¹"),
    ("5 unknown", "5 another"),
    ("2.5", "2.5 (Smith, 2020)"),
    (".5", "0.5"),
)


@pytest.mark.parametrize(("statement", "source"), NUMBER_MATCH_VECTORS)
def test_closed_numeric_equivalences_match_own_support(
    statement: str, source: str
) -> None:
    raw = candidate(
        main_findings=[{"statement": statement, "evidence": [{"evidence_id": "e1"}]}]
    )
    result = validate_read_output(raw, context_for(source))
    assert result.diagnostics == ()
    assert result.analysis.main_findings[0].statement == statement
    assert result.support[0].text == source


@pytest.mark.parametrize(
    ("statement", "source", "reason"),
    [
        ("3", "30", "number_not_supported"),
        ("3", "13", "number_not_supported"),
        ("3", "3.5", "number_not_supported"),
        ("3", "0.3", "number_not_supported"),
        ("3 km", "3 m", "unit_not_supported"),
        ("3–5 km", "3–6 km", "range_not_supported"),
        ("1,00", "100", "unrecognized_numeric_form"),
        ("1e", "1", "unrecognized_numeric_form"),
        ("2.3.4", "2.3", "unrecognized_numeric_form"),
        ("±0.5", "0.5", "number_not_supported"),
        ("Table 3 比较 12 个流域", "表格结构说明", "number_not_supported"),
    ],
)
def test_missing_or_unrecognized_support_degrades_without_rewriting(
    statement: str, source: str, reason: str
) -> None:
    raw = candidate(
        main_findings=[{"statement": statement, "evidence": [{"evidence_id": "e1"}]}]
    )
    result = validate_read_output(raw, context_for(source))
    assert [(d.location, d.reason, d.ordinal) for d in result.diagnostics] == [
        ("$.main_findings[0].statement", reason, 0)
    ]
    assert result.analysis.main_findings[0].statement == statement
    assert result.analysis.research_value == 3
    assert result.warnings[0].origin == "program"
    assert statement in result.warnings[0].text or (
        "12" in statement and "12" in result.warnings[0].text
    )
    assert result == validate_read_output(raw, context_for(source))


def test_ranges_need_one_slice_but_distinct_numbers_can_use_separate_slices() -> None:
    identity = ExtractionIdentity("extraction-1", "reading-1", "map-1")
    context = context_for(
        "3",
        source_blocks=[
            SourceBlock(identity, "s1", "3"),
            SourceBlock(identity, "s2", "5 km"),
        ],
        evidence=[
            Evidence(
                identity,
                "e1",
                [
                    Provenance("s1", 3, (0, 0, 1, 1), 0, 1),
                    Provenance("s2", 3, (0, 0, 1, 1), 0, 4),
                ],
            )
        ],
    )
    ranged = candidate(
        main_findings=[{"statement": "3–5 km", "evidence": [{"evidence_id": "e1"}]}]
    )
    result = validate_read_output(ranged, context)
    assert result.diagnostics[0].reason == "range_not_supported"
    separate = candidate(
        main_findings=[{"statement": "3 与 5 km", "evidence": [{"evidence_id": "e1"}]}]
    )
    assert validate_read_output(separate, context).diagnostics == ()


def test_digits_in_another_evidence_are_not_support() -> None:
    base = context_for("可靠的原文。")
    identity = base.identity
    context = context_for(
        source_blocks=[*base.source_blocks, SourceBlock(identity, "s2", "30%")],
        evidence=[
            *base.evidence,
            Evidence(identity, "e2", [Provenance("s2", 3, (0, 0, 1, 1), 0, 3)]),
        ],
    )
    raw = candidate(
        main_findings=[
            {"statement": "增加了30%。", "evidence": [{"evidence_id": "e1"}]}
        ]
    )
    assert (
        validate_read_output(raw, context).diagnostics[0].reason
        == "number_not_supported"
    )


def test_typical_chinese_analysis_over_english_source_has_zero_warnings() -> None:
    source = (
        "ERA5 and CMIP6 indicate precipitation increased by 30% at 850-hPa "
        "during 1979–2020. The speed is 3 m s−1. (Smith et al., 2022)"
    )
    raw = candidate(
        main_findings=[
            {
                "statement": (
                    "ERA5 与 CMIP6 表明，1979至2020 年降水增加了30%，对应850百帕。"
                ),
                "evidence": [{"evidence_id": "e1"}],
            }
        ],
        reusable_points=[
            {
                "item": "可复用3米/秒的设置。",
                "how_to_reuse": "与公开观测比较。",
                "evidence": [{"evidence_id": "e1"}],
            }
        ],
    )
    assert validate_read_output(raw, context_for(source)).diagnostics == ()


@pytest.mark.parametrize("language", ["zh", "en"])
def test_program_warnings_keep_origin_and_safe_structured_positions(
    language: str,
) -> None:
    raw = candidate(
        output_language=language,
        main_findings=[
            {"statement": "降水增加了30%。", "evidence": [{"evidence_id": "e1"}]}
        ],
        degraded_content_warnings=["已有模型警告。", "已有模型警告。"],
    )
    result = validate_read_output(raw, context_for(expected_language=language))
    assert result.model_warnings == ("已有模型警告。", "已有模型警告。")
    assert [w.origin for w in result.warnings] == ["model", "model", "program"]
    warning = result.warnings[-1]
    assert "30%" in warning.text
    assert ("请核对" if language == "zh" else "Please verify") in warning.text
    assert "30%" not in repr(result)
    assert "30%" not in repr(result.diagnostics)
    assert "30%" not in repr(warning)
    assert result.analysis.degraded_content_warnings[-1] == warning.text


@pytest.mark.parametrize(
    "field",
    [
        "main_findings",
        "research_value_reason",
        "reuse_feasibility_reason",
        "key_limitations",
        "reusable_points.item",
        "reusable_points.how_to_reuse",
    ],
)
def test_all_five_protected_content_types_check_their_own_numbers(field: str) -> None:
    statement = {"statement": "增加了30%", "evidence": [{"evidence_id": "e1"}]}
    changes: dict[str, object]
    if field.startswith("reusable_points"):
        item = {
            "item": "可复用的方法。",
            "how_to_reuse": "与公开观测比较。",
            "evidence": [{"evidence_id": "e1"}],
        }
        item[field.split(".")[1]] = "增加了30%"
        changes = {"reusable_points": [item]}
    else:
        changes = {
            field: [statement]
            if field in ("main_findings", "key_limitations")
            else statement
        }
    result = validate_read_output(candidate(**changes), context_for())
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].location.startswith("$." + field.split(".")[0])


def test_model_warning_cannot_impersonate_or_suppress_program_diagnostic() -> None:
    raw = candidate(
        main_findings=[{"statement": "30%", "evidence": [{"evidence_id": "e1"}]}]
    )
    first = validate_read_output(raw, context_for())
    template = first.warnings[0].text
    result = validate_read_output(
        candidate(
            main_findings=[{"statement": "30%", "evidence": [{"evidence_id": "e1"}]}],
            degraded_content_warnings=[template, template],
        ),
        context_for(),
    )
    assert tuple(w.text for w in result.warnings) == (template, template, template)
    assert tuple(w.origin for w in result.warnings) == ("model", "model", "program")
    assert result.diagnostics == first.diagnostics


def test_unprotected_text_fields_are_not_numerically_checked() -> None:
    changes = dict.fromkeys(
        (
            "one_sentence_conclusion",
            "research_question",
            "methods_summary",
            "data_summary",
            "why_it_matters",
            "next_action",
        ),
        "未引用的数值99999%",
    )
    raw = candidate(
        **changes,
        required_adaptations=["99999%"],
        open_questions=["99999%"],
        degraded_content_warnings=["99999%"],
    )
    assert validate_read_output(raw, context_for()).diagnostics == ()


def test_diagnostic_order_is_stable_by_field_reason_and_ordinal() -> None:
    raw = candidate(
        main_findings=[
            {"statement": "30% 与 12 km", "evidence": [{"evidence_id": "e1"}]}
        ],
        key_limitations=[{"statement": "3–5 km", "evidence": [{"evidence_id": "e1"}]}],
    )
    result = validate_read_output(raw, context_for())
    assert [(d.location, d.reason, d.ordinal) for d in result.diagnostics] == [
        ("$.key_limitations[0].statement", "range_not_supported", 0),
        ("$.main_findings[0].statement", "number_not_supported", 0),
        ("$.main_findings[0].statement", "number_not_supported", 1),
    ]


@pytest.mark.parametrize("statement", ["1.2×10^?", "10^unknown", "1.2×10", "1/2"])
def test_unsupported_numeric_shapes_cannot_be_supported_by_their_component_digits(
    statement: str,
) -> None:
    raw = candidate(
        main_findings=[{"statement": statement, "evidence": [{"evidence_id": "e1"}]}]
    )
    result = validate_read_output(raw, context_for("1.2 and 10 and 1 and 2"))
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].reason == "unrecognized_numeric_form"


def test_range_unit_belongs_to_the_second_endpoint() -> None:
    raw = candidate(
        main_findings=[{"statement": "2–3 m", "evidence": [{"evidence_id": "e1"}]}]
    )
    assert validate_read_output(raw, context_for("2 and 3 m")).diagnostics == ()


@pytest.mark.parametrize(
    ("statement", "source"),
    [
        ("13±5", "13±3"),
        ("13±5", "13"),
        ("13 ±5", "13 ±3"),
        ("13±5 km", "13±3 km"),
    ],
)
def test_adjacent_uncertainty_must_match_its_own_support(
    statement: str, source: str
) -> None:
    raw = candidate(
        main_findings=[{"statement": statement, "evidence": [{"evidence_id": "e1"}]}]
    )
    result = validate_read_output(raw, context_for(source))
    assert [(d.reason, d.ordinal) for d in result.diagnostics] == [
        ("number_not_supported", 1)
    ]


@pytest.mark.parametrize(
    ("statement", "source"),
    [("13±5", "13 ±5"), ("13 ±5", "13±5"), ("13±5 km", "13 ±5 km")],
)
def test_uncertainty_spacing_keeps_the_same_numeric_meaning(
    statement: str, source: str
) -> None:
    raw = candidate(
        main_findings=[{"statement": statement, "evidence": [{"evidence_id": "e1"}]}]
    )
    assert validate_read_output(raw, context_for(source)).diagnostics == ()


@pytest.mark.parametrize(
    ("statement", "source"),
    [
        ("210⁻³", "0.021"),
        ("110^3", "11000"),
        ("210⁻³", "210⁻³"),
        ("10³2", "1e32"),
        ("10³⁴5", "1e345"),
    ],
)
def test_power_suffix_cannot_create_a_scientific_equivalence(
    statement: str, source: str
) -> None:
    raw = candidate(
        main_findings=[{"statement": statement, "evidence": [{"evidence_id": "e1"}]}]
    )
    result = validate_read_output(raw, context_for(source))
    assert [(d.reason, d.ordinal) for d in result.diagnostics] == [
        ("unrecognized_numeric_form", 0)
    ]


def test_complete_ten_power_preserves_sentence_punctuation() -> None:
    raw = candidate(
        main_findings=[{"statement": "10^3.", "evidence": [{"evidence_id": "e1"}]}]
    )
    assert validate_read_output(raw, context_for("1000")).diagnostics == ()


@pytest.mark.parametrize(
    ("statement", "source"),
    [
        ("3 km–5 km", "3 m and 5 km"),
        ("3 m–5 km", "3 km and 5 km"),
        ("3 km–5 km", "3 m–5 km"),
        ("3–5 km", "3 m and 5 km"),
        ("3 km–5 m", "3 km and 5 km"),
    ],
)
def test_range_cannot_discard_an_explicit_source_endpoint_unit(
    statement: str, source: str
) -> None:
    raw = candidate(
        main_findings=[{"statement": statement, "evidence": [{"evidence_id": "e1"}]}]
    )
    result = validate_read_output(raw, context_for(source))
    assert [(d.reason, d.ordinal) for d in result.diagnostics] == [
        ("unit_not_supported", 0)
    ]


@pytest.mark.parametrize(
    ("statement", "source"),
    [
        ("3 km–5 km", "3 km and 5 km"),
        ("3 m–5 km", "3 m and 5 km"),
        ("3–5 km", "3 km and 5 km"),
        ("3 km–5 km", "3 and 5 km"),
    ],
)
def test_range_retains_explicit_units_and_permitted_implicit_front_unit(
    statement: str, source: str
) -> None:
    raw = candidate(
        main_findings=[{"statement": statement, "evidence": [{"evidence_id": "e1"}]}]
    )
    assert validate_read_output(raw, context_for(source)).diagnostics == ()
