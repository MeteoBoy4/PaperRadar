"""Feed 与元数据实际 HTTP/事务路径共用显式 sink。"""

import json
from pathlib import Path

import httpx
import pytest

from paper_radar.feed_ingestion import JGRFeed
from paper_radar.feed_metadata import JGRMetadata
from paper_radar.runtime_logging import FileSink
from tests.test_feed_ingestion import FEED, feed_service
from tests.test_feed_metadata import DOI, setup_metadata


def events(root: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in (root / "logs/runtime.jsonl").read_text().splitlines()
    ]


@pytest.mark.parametrize(
    "status,category", [(200, "acquired"), (403, "access_blocked_403")]
)
def test_feed_check_and_resume_log_controlled_route_results(
    tmp_path: Path, status: int, category: str
) -> None:
    papers, feed, original = feed_service(
        tmp_path, lambda _: httpx.Response(status, content=FEED)
    )
    assert papers.data_root is not None
    papers.data_root.mkdir(exist_ok=True)
    service = JGRFeed(
        papers.database,
        papers.data_root,
        http=original.http,
        sink=FileSink(papers.data_root),
    )
    result = service.check(
        feed.feed_id,
        request_id="SENTINEL_REQUEST",
        contact_email="SENTINEL@example.org",
    )
    assert result.reason == category
    assert (
        service.resume(result.check_id, contact_email="SENTINEL@example.org") == result
    )
    logged = events(papers.data_root)
    assert [event["event"] for event in logged] == [
        "run_started",
        "route_settled",
        "run_finished",
        "run_started",
        "run_finished",
    ]
    assert logged[1]["category"] == category
    assert logged[1]["execution_id"] == result.check_id
    assert "SENTINEL" not in (papers.data_root / "logs/runtime.jsonl").read_text()


def test_metadata_enrich_resume_keep_run_and_route_granularity(tmp_path: Path) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if "doiRA" in str(request.url):
            return httpx.Response(200, json=[{"DOI": DOI, "RA": "Crossref"}])
        return httpx.Response(404)

    papers, paper_id, original = setup_metadata(tmp_path, respond)
    assert papers.data_root is not None
    papers.data_root.mkdir(exist_ok=True)
    service = JGRMetadata(
        papers.database,
        papers.data_root,
        http=original.http,
        sink=FileSink(papers.data_root),
    )
    result = service.enrich(
        paper_id, request_id="SENTINEL_REQUEST", contact_email="SENTINEL@example.org"
    )
    assert (
        service.resume(result.request_key, contact_email="SENTINEL@example.org")
        == result
    )
    logged = events(papers.data_root)
    assert [value["event"] for value in logged] == [
        "run_started",
        "route_settled",
        "route_settled",
        "route_settled",
        "run_finished",
        "run_started",
        "run_finished",
    ]
    assert [
        value["category"] for value in logged if value["event"] == "route_settled"
    ] == ["acquired", "not_found", "not_found"]
    assert {value["paper_id"] for value in logged if "paper_id" in value} == {paper_id}
    assert logged[-1]["paper_id"] == paper_id
    assert "SENTINEL" not in (papers.data_root / "logs/runtime.jsonl").read_text()


def test_composition_forwards_one_explicit_sink_to_all_services(tmp_path: Path) -> None:
    from datetime import UTC, datetime

    from paper_radar.feed_pipeline import FeedPipeline
    from tests.test_feed_pipeline import setup_pipeline

    original, feed_id, snapshot_id, _calls = setup_pipeline(tmp_path)
    pipeline = FeedPipeline(
        original.database,
        original.data_root,
        http=original.feed.http,
        sink=FileSink(original.data_root),
        clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
    )
    prepared = pipeline.prepare(
        feed_id, request_id="composition", contact_email="contact@example.org"
    )
    paper_id = prepared.items[0].paper_id
    assert paper_id is not None
    receipt = pipeline.tasks.register(
        dict(
            paper_id=paper_id,
            snapshot_id=snapshot_id,
            stage="boundary",
            source="scheduled",
            scheduled_day="2026-01-01",
        )
    )
    pipeline.tasks.claim(receipt.receipt_id)
    logged = events(original.data_root)
    assert {value["component"] for value in logged} == {"feed", "metadata", "screening"}


@pytest.mark.parametrize("component", ["feed", "metadata"])
@pytest.mark.parametrize(
    "failure",
    [
        RuntimeError("PRIVATE_TRANSPORT_ERROR"),
        KeyboardInterrupt("PRIVATE_INTERRUPT"),
        SystemExit(31),
    ],
)
def test_source_execution_logs_unexpected_errors_and_rethrows_interruptions(
    tmp_path: Path,
    component: str,
    failure: BaseException,
) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        raise failure

    if component == "feed":
        papers, feed, original_feed = feed_service(tmp_path, respond)
        assert papers.data_root is not None
        papers.data_root.mkdir(exist_ok=True)
        feed_service_with_log = JGRFeed(
            papers.database,
            papers.data_root,
            http=original_feed.http,
            sink=FileSink(papers.data_root),
        )

        def run() -> object:
            return feed_service_with_log.check(
                feed.feed_id, request_id="broken", contact_email="contact@example.org"
            )
    else:
        papers, paper_id, original_metadata = setup_metadata(tmp_path, respond)
        assert papers.data_root is not None
        papers.data_root.mkdir(exist_ok=True)
        metadata_with_log = JGRMetadata(
            papers.database,
            papers.data_root,
            http=original_metadata.http,
            sink=FileSink(papers.data_root),
        )

        def run() -> object:
            return metadata_with_log.enrich(
                paper_id, request_id="broken", contact_email="contact@example.org"
            )

    with pytest.raises(type(failure)) as raised:
        run()
    assert raised.value is failure
    assert [value["event"] for value in events(papers.data_root)] == [
        "run_started",
        "unexpected_error" if isinstance(failure, Exception) else "interrupted",
    ]
    assert "PRIVATE" not in (papers.data_root / "logs/runtime.jsonl").read_text()


@pytest.mark.parametrize("component", ["feed", "metadata"])
def test_source_controlled_entry_rejection_is_not_an_unexpected_error(
    tmp_path: Path, component: str
) -> None:
    from paper_radar.papers.errors import PaperError, PaperReason

    if component == "feed":
        papers, feed, original_feed = feed_service(
            tmp_path, lambda _: httpx.Response(404)
        )
        assert papers.data_root is not None
        papers.data_root.mkdir(exist_ok=True)
        feed_with_log = JGRFeed(
            papers.database,
            papers.data_root,
            http=original_feed.http,
            sink=FileSink(papers.data_root),
        )

        def run() -> object:
            return feed_with_log.check(
                feed.feed_id, request_id="", contact_email="contact@example.org"
            )
    else:
        papers, paper_id, original_metadata = setup_metadata(
            tmp_path, lambda _: httpx.Response(404)
        )
        assert papers.data_root is not None
        papers.data_root.mkdir(exist_ok=True)
        metadata_with_log = JGRMetadata(
            papers.database,
            papers.data_root,
            http=original_metadata.http,
            sink=FileSink(papers.data_root),
        )

        def run() -> object:
            return metadata_with_log.enrich(
                paper_id, request_id="", contact_email="contact@example.org"
            )

    with pytest.raises(PaperError) as rejected:
        run()
    assert rejected.value.reason == PaperReason.INVALID_OBSERVATION
    logged = events(papers.data_root)
    assert [value["event"] for value in logged] == ["run_started", "run_finished"]
    assert logged[-1]["category"] == "controlled_failure"
