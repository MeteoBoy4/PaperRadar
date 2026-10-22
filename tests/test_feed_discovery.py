"""Feed 发现与无 DOI 连续版本的公共服务行为。"""

from pathlib import Path

from paper_radar.storage.artifacts import ArtifactStore
from tests.feed_support import facts, item


def test_single_item_retains_exact_bytes_and_continuous_identity_without_doi(
    tmp_path: Path,
) -> None:
    service = facts(tmp_path)
    feed = service.register_feed("https://feeds.example/f?key=1")
    request = item(feed.feed_id)
    result = service.submit(request)
    assert result.status == "retained" and result.paper_id
    trace = service.trace(result.paper_id, verify_source_bytes=True)
    assert trace.current.doi is None
    assert trace.current.fields["title"].source_kind == "feed"
    assert len(trace.discoveries) == 1
    found = trace.discoveries[0]
    assert (found.feed_id, found.entry_id, found.first_seen, found.last_seen) == (
        feed.feed_id,
        "entry-1",
        "2026-01-01T00:00:00.000000+00:00",
        "2026-01-01T00:00:00.000000+00:00",
    )
    assert (
        found.item_fingerprint
        == "16506d51144077919b7c9b0f7b86c58f2d836dd8631a3c20c227110fa2e1c0f4"
    )
    assert service.data_root
    assert (
        ArtifactStore(service.database, service.data_root).read_artifact(
            found.artifact_id
        )["payload"]
        == request["payload"]
    )
    assert service.submit(request) == result


def test_changed_item_reuses_entry_and_replay_only_advances_last_seen(
    tmp_path: Path,
) -> None:
    from datetime import UTC, datetime

    service = facts(tmp_path)
    feed = service.register_feed("https://feeds.example/f")
    original = item(feed.feed_id)
    first = service.submit(original)
    assert first.paper_id
    changed = service.submit(
        item(
            feed.feed_id,
            payload=b"B",
            observed_at=datetime(2026, 1, 2, tzinfo=UTC),
            fields={"title": {"value": "B", "locator": "item/title"}},
        )
    )
    assert (changed.paper_id, changed.version_id) == (first.paper_id, first.version_id)
    before = service.trace(first.paper_id)
    replay = service.submit(
        {**original, "observed_at": datetime(2026, 1, 3, tzinfo=UTC)}
    )
    assert replay == first
    after = service.trace(first.paper_id)
    assert after.current == before.current
    assert after.revisions == before.revisions
    assert after.observations == before.observations
    assert after.acquisitions == before.acquisitions
    assert after.current.fields["title"].value == "B"
    assert (after.discoveries[0].first_seen, after.discoveries[0].last_seen) == (
        "2026-01-01T00:00:00.000000+00:00",
        "2026-01-03T00:00:00.000000+00:00",
    )
    service.submit({**original, "observed_at": datetime(2025, 1, 1, tzinfo=UTC)})
    assert service.trace(first.paper_id) == after


def test_reparse_preserves_explanations_and_enforces_monotonic_new_requests(
    tmp_path: Path,
) -> None:
    from datetime import UTC, datetime

    service = facts(tmp_path)
    feed = service.register_feed("https://feeds.example/f")
    original = item(
        feed.feed_id,
        fields={
            "title": {"value": "A", "locator": "title"},
            "journal": {"value": "Old journal", "locator": "journal"},
        },
    )
    first = service.submit(original)
    assert first.paper_id
    second = service.submit(
        {
            **original,
            "parser_version": 2,
            "observed_at": datetime(2026, 1, 2, tzinfo=UTC),
            "fields": {"title": {"value": "Parsed B", "locator": "title"}},
        }
    )
    assert second.status == "retained"
    trace = service.trace(first.paper_id)
    assert len(trace.discoveries) == 1
    assert len(trace.discoveries[0].observation_ids) == 2
    assert trace.current.fields["title"].value == "Parsed B"
    assert "journal" not in trace.current.fields
    assert trace.revisions[0].fields["journal"].value == "Old journal"
    assert service.submit(original) == first
    rejected = service.submit(
        {**original, "observed_at": datetime(2026, 1, 3, tzinfo=UTC)}
    )
    assert (rejected.status, rejected.reason) == ("rejected", "invalid_observation")
    assert service.trace(first.paper_id).current == trace.current


def test_trace_includes_empty_parser_explanation_and_its_real_submission_time(
    tmp_path: Path,
) -> None:
    from datetime import UTC, datetime

    service = facts(tmp_path)
    feed = service.register_feed("https://feeds.example/f")
    first = service.submit(item(feed.feed_id))
    assert first.paper_id
    empty = service.submit(
        item(
            feed.feed_id,
            parser_version=2,
            fields={},
            observed_at=datetime(2026, 2, 1, tzinfo=UTC),
        )
    )
    assert empty.status == "not_retained"
    discovery = service.trace(first.paper_id).discoveries[0]
    assert [
        (parsed.parser_version, parsed.submitted_at)
        for parsed in discovery.interpretations
    ] == [
        (1, "2026-01-01T00:00:00.000000+00:00"),
        (2, "2026-02-01T00:00:00.000000+00:00"),
    ]
    assert discovery.interpretations[1].acquisition_id == empty.acquisition_id
    assert discovery.interpretations[1].observation_id is None
