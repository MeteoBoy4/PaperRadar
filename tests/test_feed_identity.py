"""Feed DOI 补登记是唯一连续身份变更入口。"""

from pathlib import Path

import pytest

from tests.feed_support import facts, item
from tests.test_paper_service import observation


def test_feed_entry_acquires_unoccupied_doi_and_preserves_original_spelling(
    tmp_path: Path,
) -> None:
    service = facts(tmp_path)
    feed = service.register_feed("https://feeds.example/f")
    first = service.submit(item(feed.feed_id))
    assert first.paper_id
    assert service.trace(first.paper_id).acquisitions[0].raw_doi is None
    second = service.submit(
        item(feed.feed_id, payload=b"with DOI", doi="DOI:10.1234/AbC")
    )
    assert (second.paper_id, second.version_id) == (first.paper_id, first.version_id)
    assert service.show(first.paper_id).doi == "10.1234/abc"
    assert service.trace(first.paper_id).acquisitions[-1].raw_doi == "DOI:10.1234/AbC"
    missing = service.submit(item(feed.feed_id, payload=b"DOI disappeared"))
    assert missing.status == "retained"
    assert service.show(first.paper_id).doi == "10.1234/abc"
    publisher = service.submit(observation())
    assert publisher.paper_id == first.paper_id
    assert any(
        acquired.raw_doi == "DOI:10.1234/AbC" and acquired.source_kind == "publisher"
        for acquired in service.trace(first.paper_id).acquisitions
    )


@pytest.mark.parametrize(
    "conflict",
    [
        "entry_doi_changed",
        "doi_owner_conflict",
        "target_mismatch",
        "version_kind_conflict",
        "explicit_cannot_supplement",
    ],
)
def test_identity_conflict_writes_no_discovery_observation_or_source_association(
    tmp_path: Path, conflict: str
) -> None:
    service = facts(tmp_path)
    feed = service.register_feed("https://feeds.example/f")
    first = service.submit(
        item(feed.feed_id, doi="10.1/x" if conflict == "entry_doi_changed" else None)
    )
    other = service.submit(observation(doi="10.1/y"))
    assert first.paper_id and other.paper_id
    before = service.trace(first.paper_id)
    other_before = service.trace(other.paper_id)
    changes: dict[str, object] = {"payload": b"conflicting changed bytes"}
    if conflict == "entry_doi_changed":
        changes["doi"] = "10.1/z"
    elif conflict == "doi_owner_conflict":
        changes["doi"] = "10.1/y"
    elif conflict == "target_mismatch":
        changes.update(
            target_paper_id=other.paper_id, target_version_id=other.version_id
        )
    elif conflict == "version_kind_conflict":
        changes["version_kind"] = "preprint"
    else:
        changes.update(
            doi="10.1/z",
            target_paper_id=first.paper_id,
            target_version_id=first.version_id,
        )
    result = service.submit(item(feed.feed_id, **changes))
    expected = (
        "target_mismatch" if conflict == "explicit_cannot_supplement" else conflict
    )
    assert (result.status, result.reason, result.conflict) == (
        "rejected",
        "identity_conflict",
        expected,
    )
    assert service.trace(first.paper_id) == before
    assert service.trace(other.paper_id) == other_before


def test_cross_feed_doi_reuses_version_but_no_doi_stays_separate(
    tmp_path: Path,
) -> None:
    service = facts(tmp_path)
    one = service.register_feed("https://feeds.example/one")
    two = service.register_feed("https://feeds.example/two")
    first = service.submit(item(one.feed_id, doi="10.1/x"))
    second = service.submit(item(two.feed_id, doi="10.1/x", payload=b"other feed item"))
    assert (first.paper_id, first.version_id) == (second.paper_id, second.version_id)
    assert first.paper_id
    assert len(service.trace(first.paper_id).discoveries) == 2
    no_doi_one = service.submit(
        item(one.feed_id, entry_id="none", payload=b"no doi one")
    )
    no_doi_two = service.submit(
        item(two.feed_id, entry_id="none", payload=b"no doi two")
    )
    assert no_doi_one.paper_id != no_doi_two.paper_id
    service.validate_all()
