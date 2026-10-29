"""独立审查回归;通过生产服务公共边界核验。"""

from pathlib import Path

import httpx
import pytest

from tests.test_feed_ingestion import feed_service, run_check


def test_deep_xml_item_is_isolated_from_following_valid_item(tmp_path: Path) -> None:
    invalid = (
        b"<item><guid>bad</guid><description>"
        + b"<p>" * 1200
        + b"text"
        + b"</p>" * 1200
        + b"</description></item>"
    )
    valid = b"<item><guid>good</guid><title>Good</title></item>"
    raw = b"<rss><channel>" + invalid + valid + b"</channel></rss>"
    papers, feed, service = feed_service(
        tmp_path, lambda _: httpx.Response(200, content=raw)
    )
    check = run_check(service, feed)
    assert check.complete
    assert check.items[0].reason == "invalid_item"
    assert check.items[1].result is not None
    assert check.items[1].result.status == "retained"
    assert check.items[1].result.paper_id is not None
    assert papers.show(check.items[1].result.paper_id).fields["title"].value == "Good"
    assert service.item_bytes(check.check_id, 1) == invalid
    assert service.item_bytes(check.check_id, 2) == valid
    assert service.replay(check.check_id) == check
    service.validate_all()


def test_unknown_abstract_truncation_blocks_metadata_completeness(
    tmp_path: Path,
) -> None:
    from tests.test_feed_metadata import DOI, FULL, setup_metadata

    def respond(request: httpx.Request) -> httpx.Response:
        if "doiRA" in str(request.url):
            return httpx.Response(200, json=[{"DOI": DOI, "RA": "Crossref"}])
        return httpx.Response(404)

    fields = {
        "title": {"value": "Title", "locator": "item/title"},
        "abstract": {
            "value": {"text": FULL, "is_truncated": None, "rule": "unknown"},
            "locator": "item/description",
        },
        "source_url": {
            "value": "https://agupubs.onlinelibrary.wiley.com/doi/" + DOI,
            "locator": "item/link",
        },
    }
    _papers, paper_id, service = setup_metadata(tmp_path, respond, fields=fields)
    result = service.enrich(
        paper_id, request_id="unknown-truncation", contact_email="contact@example.org"
    )
    assert result.abstract_present
    assert result.suspected_truncated is None
    assert not result.minimum_complete
    assert not result.nontruncated_complete
    assert result.missing == ("unknown_truncation",)
    assert service.replay(result.request_key) == result
    service.validate_all()


@pytest.mark.parametrize(
    "corruption",
    [
        "unknown_status",
        "resolved_without_bool",
        "missing_with_bool",
        "source_bool",
        "ambiguous_single_source",
    ],
)
def test_language_observations_reject_invalid_domain_states(
    tmp_path: Path, corruption: str
) -> None:
    import hashlib
    import json
    import sqlite3
    from contextlib import closing

    from paper_radar.screening_tasks import TaskError
    from tests.a7_value_support import value_archive
    from tests.test_feed_language import discovered

    data = value_archive(tmp_path)
    service = discovered(data)
    resolution = service.language_status(data.paper_id)
    assert resolution["status"] == "resolved"
    basis: dict[str, object] = dict(resolution)
    if corruption == "unknown_status":
        basis["status"] = "resovled"
    elif corruption == "resolved_without_bool":
        basis["original_title_is_zh"] = None
    elif corruption == "missing_with_bool":
        basis["status"] = "missing"
    elif corruption == "ambiguous_single_source":
        basis["status"] = "ambiguous"
        basis["original_title_is_zh"] = None
    else:
        basis["sources"] = [
            {**resolution["sources"][0], "original_title_is_zh": False},
            *resolution["sources"][1:],
        ]
    payload = json.dumps(
        basis, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    with closing(sqlite3.connect(data.database)) as connection:
        connection.execute(
            "UPDATE title_language_resolutions SET basis_json=?, resolution_id=?",
            (payload, hashlib.sha256(payload.encode()).hexdigest()),
        )
        connection.commit()
    with pytest.raises(TaskError, match="corrupt_reference"):
        service.language_observations(data.paper_id)
    with pytest.raises(TaskError, match="corrupt_reference"):
        service.validate_all()
