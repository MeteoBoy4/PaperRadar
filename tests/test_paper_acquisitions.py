"""用户裁决:候选复用的不可变取得事实与精确原结果重试。"""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from paper_radar.papers import PaperFacts
from paper_radar.storage.artifacts import ArtifactStore
from paper_radar.storage.database import upgrade_database
from tests.test_paper_service import observation


def request(text: str, day: int, payload: bytes) -> dict[str, object]:
    return observation(
        observed_at=datetime(2026, 1, day, tzinfo=UTC),
        payload=payload,
        fields={"title": {"value": text, "locator": "title"}},
    )


@pytest.mark.parametrize("order", [(0, 1, 2), (0, 2, 1)])
def test_repeat_acquisition_preserves_time_and_order_independent_current_fact(
    tmp_path: Path, order: tuple[int, ...]
) -> None:
    database = tmp_path / "facts.sqlite"
    upgrade_database(database)
    service = PaperFacts(database, tmp_path / "data")
    requests = [
        request("A", 1, b"A-first"),
        request("B", 2, b"B"),
        request("A", 3, b"A-nonbusiness-change"),
    ]
    results = [service.submit(requests[index]) for index in order]
    assert results[0].paper_id
    trace = service.trace(results[0].paper_id, verify_source_bytes=True)
    title = trace.current.fields["title"]
    assert title.value == "A"
    assert title.observed_at == "2026-01-03T00:00:00.000000+00:00"
    assert len(trace.observations) == 2
    assert len(trace.acquisitions) == 3
    assert len(ArtifactStore(database, tmp_path / "data").list_artifacts()) == 2
    assert title.observation_id == trace.acquisitions[0].source_observation_id
    assert title.acquisition_id == trace.acquisitions[-1].acquisition_id


def test_not_retained_retry_keeps_original_result_after_other_changes(
    tmp_path: Path,
) -> None:
    database = tmp_path / "facts.sqlite"
    upgrade_database(database)
    service = PaperFacts(database, tmp_path / "data")
    first = service.submit(request("A", 1, b"A-first"))
    repeated_request = request("A", 2, b"A-again")
    repeated = service.submit(repeated_request)
    assert repeated.status == "not_retained"
    service.submit(request("B", 3, b"B"))
    assert service.submit(repeated_request) == repeated
    different_parse = service.submit(
        {
            **repeated_request,
            "fields": {"title": {"value": "FORGED", "locator": "title"}},
        }
    )
    assert (different_parse.status, different_parse.reason) == (
        "rejected",
        "invalid_observation",
    )
    assert first.paper_id
    trace = service.trace(first.paper_id)
    assert len(trace.acquisitions) == 3
    assert len(trace.observations) == 2


def test_empty_request_retry_does_not_create_identity_or_publish_source(
    tmp_path: Path,
) -> None:
    database = tmp_path / "facts.sqlite"
    upgrade_database(database)
    service = PaperFacts(database, tmp_path / "data")
    empty = observation(fields={})
    original = service.submit(empty)
    created = service.submit(request("A", 2, b"A"))
    assert created.paper_id
    assert service.submit(empty) == original
    conflict = service.submit(
        {**empty, "fields": {"title": {"value": "changed", "locator": "title"}}}
    )
    assert conflict.reason == "invalid_observation"
    assert len(ArtifactStore(database, tmp_path / "data").list_artifacts()) == 1


def test_unbound_empty_receipt_is_not_reinterpreted_by_later_version_kind(
    tmp_path: Path,
) -> None:
    database = tmp_path / "facts.sqlite"
    upgrade_database(database)
    service = PaperFacts(database, tmp_path / "data")
    empty = observation(fields={})
    original = service.submit(empty)
    created = service.submit(
        {**request("Preprint", 2, b"preprint"), "version_kind": "preprint"}
    )
    assert created.status == "retained"
    assert service.submit(empty) == original
