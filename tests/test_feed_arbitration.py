"""出版者优先、Feed 补缺与稳定同级仲裁。"""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from paper_radar.papers import AbstractValue
from tests.feed_support import facts, item
from tests.test_paper_service import observation


def abstract(text: str) -> dict[str, object]:
    return {
        "value": {"text": text, "is_truncated": None, "rule": "fixture"},
        "locator": "abstract",
    }


@pytest.mark.parametrize("publisher_first", [False, True])
def test_feed_only_fills_missing_publisher_fields_and_reparse_can_fall_back(
    tmp_path: Path, publisher_first: bool
) -> None:
    service = facts(tmp_path)
    feed = service.register_feed("https://feeds.example/f")
    publisher = observation(
        fields={
            "title": {"value": "Publisher", "locator": "title"},
            "abstract": abstract("Publisher abstract"),
        }
    )
    feed_item = item(
        feed.feed_id,
        doi="10.1234/abc",
        observed_at=datetime(2026, 2, 1, tzinfo=UTC),
        fields={
            "title": {"value": "Feed", "locator": "title"},
            "journal": {"value": "Feed journal", "locator": "journal"},
            "abstract": abstract("Feed abstract"),
        },
    )
    for request in (
        (publisher, feed_item) if publisher_first else (feed_item, publisher)
    ):
        result = service.submit(request)
        assert result.status == "retained"
    assert result.paper_id
    shown = service.show(result.paper_id)
    assert shown.fields["title"].value == "Publisher"
    publisher_abstract = shown.fields["abstract"].value
    assert isinstance(publisher_abstract, AbstractValue)
    assert publisher_abstract.text == "Publisher abstract"
    assert shown.fields["journal"].value == "Feed journal"
    assert shown.fields["journal"].source_kind == "feed"
    original = service.trace(result.paper_id).revisions
    reparsed = service.submit(
        {
            **publisher,
            "parser_version": 2,
            "observed_at": datetime(2026, 3, 1, tzinfo=UTC),
            "fields": {"title": {"value": "Publisher", "locator": "title"}},
        }
    )
    assert reparsed.status == "retained"
    trace = service.trace(result.paper_id)
    feed_abstract = trace.current.fields["abstract"].value
    assert isinstance(feed_abstract, AbstractValue)
    assert feed_abstract.text == "Feed abstract"
    assert trace.current.fields["abstract"].source_kind == "feed"
    assert trace.revisions[:-1] == original


@pytest.mark.parametrize("reverse", [False, True])
def test_cross_feed_same_priority_uses_time_then_stable_url_stream_tie_break(
    tmp_path: Path, reverse: bool
) -> None:
    service = facts(tmp_path)
    urls = ["https://feeds.example/" + letter for letter in "abcdefgh"]
    feeds = [
        service.register_feed(url) for url in (reversed(urls) if reverse else urls)
    ]
    result = None
    for number, feed in enumerate(feeds):
        result = service.submit(
            item(
                feed.feed_id,
                doi="10.1/x",
                payload=("item:" + feed.url).encode(),
                fields={"title": {"value": feed.url, "locator": "title"}},
            )
        )
        assert result.status == "retained", number
    assert result and result.paper_id
    # Independent fixed SHA-256 vector: d has the greatest payload digest,
    # f75d4dd1dc814338da660c4b4d85dadf9a90c80898b6c7b87a616c8b2ca27d14.
    assert (
        service.show(result.paper_id).fields["title"].value == "https://feeds.example/d"
    )
    # Distinct bytes participate before the stream key; equal payloads are
    # prohibited across entries. Later observed_at must win regardless of arrival.
    later = service.submit(
        item(
            feeds[0].feed_id,
            doi="10.1/x",
            payload=b"later",
            observed_at=datetime(2026, 2, 1, tzinfo=UTC),
            fields={"title": {"value": "Later", "locator": "title"}},
        )
    )
    assert later.status == "retained"
    assert service.show(result.paper_id).fields["title"].value == "Later"
    service.validate_all()


def test_empty_reparse_keeps_current_fields_and_empty_first_item_is_a_real_discovery(
    tmp_path: Path,
) -> None:
    service = facts(tmp_path)
    feed = service.register_feed("https://feeds.example/f")
    first = service.submit(item(feed.feed_id))
    assert first.paper_id
    old = service.show(first.paper_id)
    result = service.submit(item(feed.feed_id, parser_version=2, fields={}))
    assert (result.status, result.reason) == ("not_retained", "not_retained")
    assert service.show(first.paper_id) == old
    assert len(service.trace(first.paper_id).discoveries) == 1
    empty = service.submit(
        item(feed.feed_id, entry_id="empty", payload=b"empty item", fields={})
    )
    assert empty.status == "retained" and empty.paper_id
    trace = service.trace(empty.paper_id)
    assert trace.current.fields == {}
    assert len(trace.discoveries) == len(trace.observations) == 1
    service.validate_all()
