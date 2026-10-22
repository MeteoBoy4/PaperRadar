"""人工字段修正绑定版本、原子事件次序和请求身份。"""

from pathlib import Path

import pytest

from paper_radar.papers import AbstractValue
from tests.feed_support import facts, item
from tests.test_paper_service import observation


def correction(version_id: str, **changes: object) -> dict[str, object]:
    return {
        "version_id": version_id,
        "request_id": "request-1",
        "actor": "researcher",
        "reason": "核对原文",
        "fields": {"title": {"value": "人工题名", "locator": "page/1"}},
        **changes,
    }


def test_manual_is_partial_highest_priority_and_exact_request_retry(
    tmp_path: Path,
) -> None:
    service = facts(tmp_path)
    original = service.submit(observation())
    assert original.version_id and original.paper_id
    request = correction(original.version_id)
    first = service.correct(request)
    assert first.status == "retained"
    assert service.correct(request) == first
    second = service.correct(
        correction(
            original.version_id,
            request_id="request-2",
            fields={"volume": {"value": "X", "locator": "page/2"}},
        )
    )
    assert second.status == "retained"
    service.submit(
        observation(
            payload=b"newer",
            fields={"title": {"value": "Publisher", "locator": "title"}},
        )
    )
    trace = service.trace(original.paper_id, verify_source_bytes=True)
    assert trace.current.fields["title"].value == "人工题名"
    assert trace.current.fields["volume"].value == "X"
    assert [event.event_no for event in trace.corrections] == [2, 3]
    assert trace.corrections[0].actor == "researcher"
    assert trace.corrections[0].reason == "核对原文"
    changed = service.correct(correction(original.version_id, reason="different"))
    assert (changed.status, changed.reason) == ("rejected", "invalid_manual_correction")
    assert len(service.trace(original.paper_id).corrections) == 2


@pytest.mark.parametrize(
    "fields",
    [
        {},
        {"title": {"value": " \r\n\u3000", "locator": "page/1"}},
        {
            "abstract": {
                "value": {"is_truncated": False, "rule": "manual"},
                "locator": "page/1",
            }
        },
        {"title": {"value": "secret\ud800", "locator": "page/1"}},
        {"title": {"value": "<b>secret</b>", "locator": "page/1"}},
        {"title": {"value": 4, "locator": "page/1"}},
    ],
)
def test_blank_marker_only_and_illegal_manual_values_are_rejected(
    tmp_path: Path, fields: dict[str, object]
) -> None:
    service = facts(tmp_path)
    first = service.submit(observation())
    assert first.version_id and first.paper_id
    result = service.correct(correction(first.version_id, fields=fields))
    assert (result.status, result.reason) == ("rejected", "invalid_manual_correction")
    assert "secret" not in repr(result)
    assert not service.trace(first.paper_id).corrections


def test_manual_abstract_whole_value_and_latest_event_override(tmp_path: Path) -> None:
    service = facts(tmp_path)
    feed = service.register_feed("https://example.org/feed")
    first = service.submit(
        item(
            feed.feed_id,
            fields={
                "abstract": {
                    "value": {
                        "text": " Original\r\n\n\nText ",
                        "is_truncated": None,
                        "rule": "feed",
                    },
                    "locator": "summary",
                }
            },
        )
    )
    assert first.version_id and first.paper_id
    corrected = service.correct(
        correction(
            first.version_id,
            fields={
                "abstract": {
                    "value": {
                        "text": "Original\n\n\nText",
                        "is_truncated": False,
                        "rule": "manual-v1",
                    },
                    "locator": "page/1",
                }
            },
        )
    )
    assert corrected.status == "retained"
    second = service.correct(
        correction(
            first.version_id,
            request_id="second",
            fields={
                "abstract": {
                    "value": {
                        "text": "Final\t摘要",
                        "is_truncated": True,
                        "rule": "manual-v2",
                    },
                    "locator": "page/2",
                }
            },
        )
    )
    assert second.status == "retained"
    trace = service.trace(first.paper_id)
    current_abstract = trace.current.fields["abstract"].value
    old_abstract = trace.revisions[-2].fields["abstract"].value
    assert isinstance(current_abstract, AbstractValue)
    assert isinstance(old_abstract, AbstractValue)
    assert current_abstract.text == "Final\t摘要"
    assert current_abstract.is_truncated is True
    assert old_abstract.is_truncated is False
    assert trace.corrections[-1].event_no == 3
    service.validate_all()


def test_manual_no_doi_version_stays_valid_after_feed_supplements_doi(
    tmp_path: Path,
) -> None:
    service = facts(tmp_path)
    feed = service.register_feed("https://example.org/feed")
    first = service.submit(item(feed.feed_id))
    assert first.version_id and first.paper_id
    request = correction(
        first.version_id,
        fields={"authors": {"value": (" A\r\nB ", "作者"), "locator": "page/1"}},
    )
    corrected = service.correct(request)
    assert corrected.status == "retained"
    supplemented = service.submit(
        item(feed.feed_id, doi="10.1234/abc", payload=b"supplement")
    )
    assert supplemented.status == "retained"
    trace = service.trace(first.paper_id, verify_source_bytes=True)
    assert trace.current.fields["authors"].value == ("A\nB", "作者")
    assert service.correct(request) == corrected
    service.validate_all()


def test_manual_request_identity_is_version_scoped_and_no_field_crosses_versions(
    tmp_path: Path,
) -> None:
    service = facts(tmp_path)
    one = service.submit(observation())
    two = service.submit(observation(doi="10.1234/other"))
    assert one.version_id and two.version_id and one.paper_id and two.paper_id
    assert service.correct(correction(one.version_id)).status == "retained"
    assert service.show(two.paper_id).fields["title"].value == "Original\nTitle"
    assert service.correct(correction(two.version_id)).status == "retained"
    assert len(service.trace(one.paper_id).corrections) == 1
    assert len(service.trace(two.paper_id).corrections) == 1
