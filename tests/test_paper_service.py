"""公共论文事实服务:真实 SQLite 与来源制品。"""

from datetime import UTC, datetime
from pathlib import Path

from paper_radar.papers import PaperFacts
from paper_radar.storage.database import upgrade_database


def observation(**changes: object) -> dict[str, object]:
    return {
        "doi": "DOI:10.1234/AbC",
        "version_kind": "journal",
        "source_kind": "publisher",
        "provider": "publisher.example",
        "query_key": "article-1",
        "observed_at": datetime(2026, 1, 1, tzinfo=UTC),
        "parser_version": 1,
        "interpretation": "complete",
        "payload": b"original response",
        "fields": {"title": {"value": "  Original\r\nTitle  ", "locator": "title"}},
        **changes,
    }


def test_publisher_observation_is_queryable_and_retry_keeps_identity(
    tmp_path: Path,
) -> None:
    database = tmp_path / "facts.sqlite"
    upgrade_database(database)
    service = PaperFacts(database, tmp_path / "data")
    retained = service.submit(observation())
    assert retained.status == "retained"
    assert retained.paper_id is not None
    shown = service.show(retained.paper_id)
    assert shown.doi == "10.1234/abc"
    assert shown.fields["title"].value == "Original\nTitle"
    assert shown.revision_no == 1
    assert service.submit(observation()) == retained
    trace = service.trace(retained.paper_id, verify_source_bytes=True)
    assert len(trace.observations) == 1
    assert (
        trace.observations[0].payload_sha256
        == "8f64c5e365050c3bb03bf8a36720c10dfaed7b38451048caa854c758fbfc0085"
    )


def test_distinct_doi_never_merge_on_shared_text_or_url(tmp_path: Path) -> None:
    database = tmp_path / "facts.sqlite"
    upgrade_database(database)
    service = PaperFacts(database, tmp_path / "data")
    common = {
        "title": {"value": "Same title", "locator": "title"},
        "authors": {"value": ("Same author",), "locator": "authors"},
        "source_url": {"value": "https://publisher.example/same", "locator": "url"},
    }
    first = service.submit(observation(fields=common))
    second = service.submit(observation(doi="10.1234/different", fields=common))
    assert first.paper_id != second.paper_id
    assert first.version_id != second.version_id


def test_explicit_target_and_kind_conflicts_leave_all_business_history_unchanged(
    tmp_path: Path,
) -> None:
    database = tmp_path / "facts.sqlite"
    upgrade_database(database)
    service = PaperFacts(database, tmp_path / "data")
    first = service.submit(observation())
    second = service.submit(observation(doi="10.1/other"))
    assert first.paper_id and second.paper_id
    before = service.trace(first.paper_id)
    mismatch = service.submit(
        observation(target_paper_id=second.paper_id, target_version_id=first.version_id)
    )
    assert (mismatch.status, mismatch.reason, mismatch.conflict) == (
        "rejected",
        "identity_conflict",
        "target_mismatch",
    )
    owner = service.submit(
        observation(
            target_paper_id=second.paper_id, target_version_id=second.version_id
        )
    )
    assert (owner.reason, owner.conflict) == ("identity_conflict", "doi_owner_conflict")
    kind = service.submit(observation(version_kind="preprint"))
    assert (kind.reason, kind.conflict) == (
        "identity_conflict",
        "version_kind_conflict",
    )
    assert service.trace(first.paper_id) == before


def test_missing_title_is_real_absence_and_blank_observation_is_not_retained(
    tmp_path: Path,
) -> None:
    database = tmp_path / "facts.sqlite"
    upgrade_database(database)
    service = PaperFacts(database, tmp_path / "data")
    empty = service.submit(
        observation(fields={"title": {"value": "\u3000\r\n", "locator": "title"}})
    )
    assert (empty.status, empty.reason, empty.paper_id) == (
        "not_retained",
        "not_retained",
        None,
    )
    result = service.submit(
        observation(
            payload=b"volume", fields={"volume": {"value": "12", "locator": "volume"}}
        )
    )
    assert result.paper_id
    assert set(service.show(result.paper_id).fields) == {"volume"}


def test_changed_observation_keeps_full_old_revision_and_provenance(
    tmp_path: Path,
) -> None:
    database = tmp_path / "facts.sqlite"
    upgrade_database(database)
    service = PaperFacts(database, tmp_path / "data")
    first = service.submit(observation())
    assert first.paper_id
    updated = service.submit(
        observation(
            payload=b"updated",
            observed_at=datetime(2026, 1, 2, tzinfo=UTC),
            fields={"title": {"value": "Updated", "locator": "new-title"}},
        )
    )
    assert updated.revision_no == 2
    trace = service.trace(first.paper_id, verify_source_bytes=True)
    assert [revision.fields["title"].value for revision in trace.revisions] == [
        "Original\nTitle",
        "Updated",
    ]
    assert trace.current.fields["title"].observation_id == updated.observation_id
    assert service.submit(observation()) == first
    changed_retry = service.submit(
        observation(fields={"title": {"value": "Forged", "locator": "title"}})
    )
    assert (changed_retry.status, changed_retry.reason) == (
        "rejected",
        "invalid_observation",
    )


def test_old_observation_is_retained_without_stealing_current_revision(
    tmp_path: Path,
) -> None:
    database = tmp_path / "facts.sqlite"
    upgrade_database(database)
    service = PaperFacts(database, tmp_path / "data")
    newest = service.submit(observation(observed_at=datetime(2026, 2, 1, tzinfo=UTC)))
    old = service.submit(
        observation(
            payload=b"older", fields={"title": {"value": "Older", "locator": "title"}}
        )
    )
    assert newest.paper_id
    trace = service.trace(newest.paper_id)
    assert old.status == "retained"
    assert len(trace.observations) == 2
    assert len(trace.revisions) == 1
    assert trace.current.fields["title"].value == "Original\nTitle"


def test_storage_failures_stay_inside_paper_boundary(tmp_path: Path) -> None:
    service = PaperFacts(tmp_path / "missing.sqlite", tmp_path / "data")
    result = service.submit(observation())
    assert (result.status, result.reason) == ("rejected", "corrupt_reference")
