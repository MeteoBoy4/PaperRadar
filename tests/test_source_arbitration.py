"""来源仲裁公共服务验收,不依赖表布局。"""

from datetime import UTC, datetime
from itertools import permutations
from pathlib import Path

import pytest

from paper_radar.papers import AbstractValue
from tests.feed_support import facts, item
from tests.test_paper_service import observation


def test_registry_fills_feed_below_publisher_and_requires_matching_target(
    tmp_path: Path,
) -> None:
    service = facts(tmp_path)
    feed = service.register_feed("https://example.org/feed")
    first = service.submit(item(feed.feed_id, doi="10.1234/abc"))
    assert first.paper_id and first.version_id
    registered = service.submit(
        observation(
            source_kind="registry",
            provider="crossref",
            query_key="10.1234/abc",
            target_paper_id=first.paper_id,
            target_version_id=first.version_id,
            fields={"title": {"value": "Registry", "locator": "message/title"}},
        )
    )
    assert registered.status == "retained"
    assert service.show(first.paper_id).fields["title"].value == "Registry"
    published = service.submit(observation())
    assert published.status == "retained"
    assert service.show(first.paper_id).fields["title"].value == "Original\nTitle"
    bad = service.submit(
        observation(
            source_kind="registry",
            provider="crossref",
            query_key="10.1234/wrong",
            target_paper_id=first.paper_id,
            target_version_id=first.version_id,
        )
    )
    assert (bad.status, bad.reason) == ("rejected", "invalid_observation")
    assert len(service.trace(first.paper_id).observations) == 3


def test_public_history_reconstructs_one_complete_revision(tmp_path: Path) -> None:
    service = facts(tmp_path)
    first = service.submit(observation())
    assert first.version_id and first.paper_id
    service.submit(
        observation(
            payload=b"later", fields={"volume": {"value": "9", "locator": "volume"}}
        )
    )
    historical = service.revision(first.version_id, 1)
    assert (historical.paper_id, historical.version_id, historical.revision_no) == (
        first.paper_id,
        first.version_id,
        1,
    )
    assert set(historical.fields) == {"title"}
    assert historical.fields["title"].value == "Original\nTitle"
    assert historical.selection is not None


def test_cross_stream_highest_parser_is_material_local_and_fallback_is_historical(
    tmp_path: Path,
) -> None:
    service = facts(tmp_path)
    first = service.submit(
        observation(
            fields={
                "title": {"value": "Publisher", "locator": "title"},
                "abstract": {
                    "value": {
                        "text": "Old abstract",
                        "is_truncated": None,
                        "rule": "publisher-v1",
                    },
                    "locator": "abstract",
                },
            }
        )
    )
    assert first.paper_id and first.version_id
    lower = service.submit(
        observation(
            source_kind="registry",
            provider="crossref",
            query_key="10.1234/abc",
            target_paper_id=first.paper_id,
            target_version_id=first.version_id,
            fields={
                "abstract": {
                    "value": {
                        "text": "Registry abstract",
                        "is_truncated": False,
                        "rule": "registry-v1",
                    },
                    "locator": "message/abstract",
                }
            },
        )
    )
    assert lower.status == "retained"
    reparsed = service.submit(
        observation(
            parser_version=2,
            fields={"title": {"value": "Publisher", "locator": "title"}},
        )
    )
    assert reparsed.status == "retained"
    current = service.show(first.paper_id)
    assert current.fields["abstract"].source_kind == "registry"
    current_abstract = current.fields["abstract"].value
    assert isinstance(current_abstract, AbstractValue)
    assert current_abstract.text == "Registry abstract"
    historical_abstract = service.revision(first.version_id, 1).fields["abstract"].value
    assert isinstance(historical_abstract, AbstractValue)
    assert historical_abstract.text == "Old abstract"
    before = service.trace(first.paper_id)
    empty = service.submit(observation(parser_version=3, fields={}))
    assert empty.status == "not_retained"
    assert service.show(first.paper_id).fields == current.fields
    assert len(service.trace(first.paper_id).revisions) == len(before.revisions)
    rejected = service.submit(
        observation(
            parser_version=2,
            observed_at=datetime(2026, 2, 1, tzinfo=UTC),
            fields={"title": {"value": "Publisher", "locator": "title"}},
        )
    )
    assert rejected.reason == "invalid_observation"
    service.validate_all()


@pytest.mark.parametrize("order", list(permutations(range(3))))
def test_cross_publisher_streams_are_deterministic_and_retry_is_exact(
    tmp_path: Path, order: tuple[int, ...]
) -> None:
    service = facts(tmp_path)
    requests = [
        observation(
            provider="a",
            query_key="article",
            payload=b"same",
            fields={"title": {"value": "A", "locator": "title"}},
        ),
        observation(
            provider="z",
            query_key="article",
            payload=b"same",
            fields={"title": {"value": "Z", "locator": "title"}},
        ),
        observation(
            provider="a",
            query_key="later",
            payload=b"last",
            observed_at=datetime(2026, 1, 2, tzinfo=UTC),
            fields={"volume": {"value": "9", "locator": "volume"}},
        ),
    ]
    results = [service.submit(requests[index]) for index in order]
    assert all(result.status == "retained" for result in results)
    paper_id = results[0].paper_id
    assert paper_id
    current = service.show(paper_id)
    assert current.fields["title"].value == "Z"
    assert current.fields["volume"].value == "9"
    for index, result in zip(order, results, strict=True):
        assert service.submit(requests[index]) == result
    assert len(service.trace(paper_id).observations) == 3


def test_trace_explains_selected_and_unselected_candidates_without_invented_status(
    tmp_path: Path,
) -> None:
    service = facts(tmp_path)
    first = service.submit(observation())
    assert first.paper_id and first.version_id
    lower = service.submit(
        observation(
            source_kind="registry",
            provider="crossref",
            query_key="10.1234/abc",
            target_paper_id=first.paper_id,
            target_version_id=first.version_id,
            fields={"title": {"value": "Registry", "locator": "message/title"}},
        )
    )
    trace = service.trace(first.paper_id)
    assert first.acquisition_id and lower.acquisition_id
    by_acquisition = {choice.acquisition_id: choice for choice in trace.decisions}
    assert by_acquisition[first.acquisition_id].reason == "selected"
    assert by_acquisition[lower.acquisition_id].reason == "lower_source_priority"
    assert (
        trace.manual_correction_scope == "人工修正绑定版本，不随 Paper 当前版本升级迁移"
    )
