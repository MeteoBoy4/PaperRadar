"""Issue #146:合成字段共存向量,新规则与冻结 v1 分别解释。"""

import hashlib

import pytest

from paper_radar.fixture_audit.abstract_parser import parse_material
from paper_radar.fixture_audit.acquisition_models import SourceRequest
from paper_radar.fixture_audit.models import Journal

MAIN = (
    "Synthetic atmospheric measurements establish a reproducible result across "
    "several controlled experiments and describe the complete scientific method."
)
NOTE = "Journal of Synthetic Atmospheres, Volume 9, Issue 2, Pages 1-8."


def feed(fields: str) -> bytes:
    return (
        '<rss xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel>'
        "<item><guid>entry-1</guid><title>Synthetic title</title>"
        + fields
        + "</item></channel></rss>"
    ).encode()


def test_wiley_coexisting_fields_choose_encoded_main_and_preserve_v1() -> None:
    raw = feed(
        f"<description>{NOTE}</description>"
        "<dc:description><![CDATA[<h2>Abstract</h2><p>Short preview...</p>]]>"
        "</dc:description><content:encoded><![CDATA[<h2>Abstract</h2>"
        f"<p>{MAIN}</p><h2>Plain Language Summary</h2><p>EXTRA</p>]]>"
        "</content:encoded>"
    )
    request = SourceRequest(journal="jgr", route="feed")
    old, _, old_texts, _ = parse_material(
        request, raw, decoding="utf-8", acquisition_id="old", entry_locator="item[1]"
    )
    assert old_texts[old[-1].candidate_id] == NOTE
    new, excluded, texts, _ = parse_material(
        request,
        raw,
        decoding="utf-8",
        acquisition_id="new",
        entry_locator="item[1]",
        rules_version="audit-abstract-v2",
    )
    abstract = next(value for value in new if value.field == "abstract")
    assert texts[abstract.candidate_id] == MAIN
    assert abstract.text_sha256 == hashlib.sha256(MAIN.encode()).hexdigest()
    assert abstract.codepoints == 149
    assert abstract.signals == ()
    assert (
        abstract.locator == "item[1]/{http://purl.org/rss/1.0/modules/content/}encoded"
    )
    assert {value.kind for value in excluded} == {"plain_language_summary"}


def test_empty_main_does_not_promote_plain_language_or_issue_note() -> None:
    raw = feed(
        f"<description>{NOTE}</description>"
        "<content:encoded><![CDATA[<h2>Abstract</h2>"
        "<h2>Plain Language Summary</h2><p>EXTRA</p>]]></content:encoded>"
    )
    values, _, _, _ = parse_material(
        SourceRequest(journal="qjrms", route="feed"),
        raw,
        decoding="utf-8",
        acquisition_id="empty",
        rules_version="audit-abstract-v2",
    )
    assert [value.field for value in values] == ["title"]


# Missing, empty and conflicting fields are all explicit; XML order is immaterial.
@pytest.mark.parametrize("journal", ["jgr", "qjrms"])
@pytest.mark.parametrize(
    "fields,expected,location",
    [
        (f"<description>{NOTE}</description>", None, None),
        ("<content:encoded>Unlabelled note.</content:encoded>", None, None),
        (
            "<dc:description>Abstract\nFallback.</dc:description>",
            "Fallback.",
            "description",
        ),
        (
            "<content:encoded/>"
            "<dc:description>"
            "<![CDATA[<p>Abstract</p>"
            "<p>Fallback.</p>]]>"
            "</dc:description>",
            "Fallback.",
            "description",
        ),
        (
            "<dc:description>"
            "<![CDATA[<h2>Abstract</h2>"
            "<p>Preview...</p>]]>"
            "</dc:description>"
            "<content:encoded>"
            "<![CDATA[<h2>Abstract</h2>"
            "<p>Chosen.</p>]]>"
            "</content:encoded>",
            "Chosen.",
            "encoded",
        ),
        (
            "<content:encoded>"
            "<![CDATA[<h2>Abstract</h2>"
            "<p>Chosen.</p>]]>"
            "</content:encoded>"
            "<dc:description>"
            "<![CDATA[<h2>Abstract</h2>"
            "<p>Preview...</p>]]>"
            "</dc:description>",
            "Chosen.",
            "encoded",
        ),
        (
            "<content:encoded>"
            "<![CDATA[<h2>Abstract</h2>"
            "<p>A.</p>]]>"
            "</content:encoded>"
            "<content:encoded>"
            "<![CDATA[<h2>Abstract</h2>"
            "<p>B.</p>]]>"
            "</content:encoded>"
            "<dc:description>Abstract: Fallback.</dc:description>",
            None,
            None,
        ),
        (
            "<content:encoded>"
            "<![CDATA[<h2>Abstract</h2>"
            "<p>A.</p>"
            "<h2>Abstract</h2>"
            "<p>B.</p>]]>"
            "</content:encoded>",
            None,
            None,
        ),
        (
            "<content:encoded>"
            "<![CDATA[<h2>Key Points</h2>"
            "<p>EXTRA</p>]]>"
            "</content:encoded>",
            None,
            None,
        ),
        (
            "<description><![CDATA[<h2>Abstract</h2><p>Fallback.</p>]]></description>",
            "Fallback.",
            "description",
        ),
    ],
)
def test_wiley_missing_fallback_priority_and_conflict(
    fields: str, expected: str | None, location: str | None, journal: Journal
) -> None:
    candidates, _, texts, _ = parse_material(
        SourceRequest(journal=journal, route="feed"),
        feed(fields),
        decoding="utf-8",
        acquisition_id="vector",
        rules_version="audit-abstract-v2",
    )
    abstracts = [value for value in candidates if value.field == "abstract"]
    if expected is None:
        assert abstracts == []
    else:
        assert len(abstracts) == 1
        assert texts[abstracts[0].candidate_id] == expected
        assert location and abstracts[0].locator.endswith(location)


def test_unknown_rule_is_explicitly_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported_abstract_rules_version"):
        parse_material(
            SourceRequest(journal="jgr", route="feed"),
            feed(""),
            decoding="utf-8",
            acquisition_id="bad",
            rules_version="unavailable",
        )


@pytest.mark.parametrize(
    "heading", ["<p><strong>Abstract</strong></p>", "<h2><b>Abstract</b></h2>"]
)
def test_nested_markup_is_one_abstract_label(heading: str) -> None:
    values, _, texts, _ = parse_material(
        SourceRequest(journal="jgr", route="feed"),
        feed(f"<content:encoded><![CDATA[{heading}<p>{MAIN}</p>]]></content:encoded>"),
        decoding="utf-8",
        acquisition_id="nested",
        rules_version="audit-abstract-v2",
    )
    abstracts = [value for value in values if value.field == "abstract"]
    assert len(abstracts) == 1
    assert texts[abstracts[0].candidate_id] == MAIN


@pytest.mark.parametrize("prefix", ["", "<h2>Abstract</h2>"])
def test_supplementary_locations_survive_missing_main(prefix: str) -> None:
    values, excluded, _, _ = parse_material(
        SourceRequest(journal="qjrms", route="feed"),
        feed(
            "<description><![CDATA["
            + prefix
            + "<h2>Plain Language Summary</h2><p>EXTRA</p>]]></description>"
        ),
        decoding="utf-8",
        acquisition_id="extra",
        entry_locator="item[1]",
        rules_version="audit-abstract-v2",
    )
    assert [value.field for value in values] == ["title"]
    assert [value.kind for value in excluded] == ["plain_language_summary"]
    assert excluded[0].locator.startswith("item[1]/description/")
