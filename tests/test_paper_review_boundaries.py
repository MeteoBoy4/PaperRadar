"""外部审查补齐的公开规范化边界;不改变既有固定向量分母。"""

import pytest

from paper_radar.papers.doi import normalize_doi
from paper_radar.papers.errors import PaperError, PaperReason


@pytest.mark.parametrize(
    "value",
    [
        "doi:doi:10.1/a",
        "DOI:HTTPS://doi.org/10.1/a",
        "https://doi.org/https://doi.org/10.1/a",
        "https://doi.org/doi:10.1/a",
        "https://doi.org/DOI%3A10.1/a",
        "https://doi.org/HTTP%3A//doi.org/10.1/a",
    ],
)
def test_double_doi_wrapping_has_unsupported_form_reason(value: str) -> None:
    with pytest.raises(PaperError) as caught:
        normalize_doi(value)
    assert caught.value.reason == PaperReason.UNSUPPORTED_FORM
    assert caught.value.path == "doi"


@pytest.mark.parametrize(
    "location,path",
    [
        ("provider", "provider"),
        ("query_key", "query_key"),
        ("candidate", "fields.title.locator"),
        ("relation", "relations.locator"),
        ("source_url", "source_url"),
    ],
)
def test_url_rejection_names_actual_controlled_field(location: str, path: str) -> None:
    from paper_radar.papers.text import normalize_fields, parse_observation
    from tests.test_paper_service import observation

    private_url = "https://PRIVATE:SECRET@publisher.example/path"
    changes: dict[str, object] = {}
    if location in {"provider", "query_key"}:
        changes[location] = private_url
    elif location == "relation":
        changes["relations"] = (
            {
                "kind": "has-preprint",
                "source_doi": "10.1234/abc",
                "target_doi": "10.1/pre",
                "locator": private_url,
            },
        )
    else:
        name = "title" if location == "candidate" else "source_url"
        changes["fields"] = {
            name: {
                "value": private_url if location == "source_url" else "Title",
                "locator": private_url if location == "candidate" else "field",
            }
        }
    with pytest.raises(PaperError) as caught:
        item = parse_observation(observation(**changes))
        normalize_fields(item.fields)
    assert caught.value.reason == "invalid_observation"
    assert caught.value.path == path
    assert "PRIVATE" not in str(caught.value)
    assert "SECRET" not in str(caught.value)


@pytest.mark.parametrize(
    "value",
    ["Type safety for List<String>", "Arrays of Array<int>", "<custom>Title</custom>"],
)
def test_ambiguous_tag_shapes_are_rejected_as_documented(value: str) -> None:
    from paper_radar.papers.text_rules import normalize_text

    with pytest.raises(PaperError) as caught:
        normalize_text(value)
    assert caught.value.reason == "invalid_text"
    assert caught.value.path == "fields"


@pytest.mark.parametrize("value", ["a < b", "Bounds on T <: Number"])
def test_mathematical_comparisons_preserve_text(value: str) -> None:
    from paper_radar.papers.text_rules import normalize_text

    assert normalize_text(value) == value


def test_raw_source_rejection_keeps_dedicated_reason() -> None:
    from paper_radar.papers.text import parse_observation
    from tests.test_paper_service import observation

    with pytest.raises(PaperError) as caught:
        parse_observation(observation(source_kind="unsupported"))
    assert caught.value.reason == "unsupported_source"
    assert caught.value.path == "source_kind"


@pytest.mark.parametrize("typed", [False, True])
def test_raw_relation_rejection_keeps_dedicated_reason(typed: bool) -> None:
    from paper_radar.papers.models import RelationInput
    from paper_radar.papers.text import parse_observation
    from tests.test_paper_service import observation

    relation = RelationInput(
        kind="unsupported",
        source_doi="10.1234/abc",
        target_doi="10.1/pre",
        locator="relation[0]",
    )
    value = relation if typed else relation.model_dump()
    with pytest.raises(PaperError) as caught:
        parse_observation(observation(relations=(value,)))
    assert caught.value.reason == "unsupported_relation"
    assert caught.value.path == "relations.kind"


@pytest.mark.parametrize("typed", [False, True])
def test_relation_normalization_retains_original_assertion(typed: bool) -> None:
    from paper_radar.papers.models import NormalizedRelation, RelationInput
    from paper_radar.papers.text import parse_observation
    from tests.test_paper_service import observation

    relation = RelationInput(
        kind="has-preprint",
        source_doi="DOI:10.1234/AbC",
        target_doi="https://doi.org/10.1/Pre",
        locator="relation[0]",
    )
    value = relation if typed else relation.model_dump()
    item = parse_observation(observation(relations=(value,)))
    normalized = item.relations[0]
    assert isinstance(normalized, NormalizedRelation)
    assert (normalized.kind, normalized.source_doi, normalized.target_doi) == (
        "is-preprint-of",
        "10.1/pre",
        "10.1234/abc",
    )
    assert (
        normalized.raw_kind,
        normalized.raw_source_doi,
        normalized.raw_target_doi,
    ) == (
        "has-preprint",
        "DOI:10.1234/AbC",
        "https://doi.org/10.1/Pre",
    )


def test_date_dictionary_still_selects_date_value_in_candidate_union() -> None:
    from paper_radar.papers.models import DateValue
    from paper_radar.papers.text import normalize_fields, parse_observation
    from tests.test_paper_service import observation

    item = parse_observation(
        observation(
            fields={
                "online_date": {
                    "value": {"value": "2026-10", "precision": "month"},
                    "locator": "date",
                },
            }
        )
    )
    selected = normalize_fields(item.fields)["online_date"].value
    assert isinstance(selected, DateValue)
    assert (selected.value, selected.precision) == ("2026-10", "month")
