"""权威关系与版本选择的公共服务行为。"""

from pathlib import Path

from paper_radar.papers import PaperFacts
from paper_radar.storage.database import upgrade_database
from tests.test_paper_service import observation


def relation(kind: str = "is-preprint-of") -> tuple[dict[str, str], ...]:
    return (
        {
            "kind": kind,
            "source_doi": "10.1/pre" if kind == "is-preprint-of" else "10.1/journal",
            "target_doi": "10.1/journal" if kind == "is-preprint-of" else "10.1/pre",
            "locator": "relation[0]",
        },
    )


def test_relation_before_endpoints_does_not_create_empty_version_and_upgrades(
    tmp_path: Path,
) -> None:
    db = tmp_path / "facts.sqlite"
    upgrade_database(db)
    service = PaperFacts(db, tmp_path / "data")
    evidence = service.submit(
        observation(
            doi="10.1/pre", version_kind="preprint", fields={}, relations=relation()
        )
    )
    assert (evidence.status, evidence.paper_id, evidence.version_id) == (
        "retained",
        None,
        None,
    )
    pre = service.submit(
        observation(doi="10.1/pre", version_kind="preprint", payload=b"pre")
    )
    journal = service.submit(observation(doi="10.1/journal", payload=b"journal"))
    assert pre.paper_id and journal.paper_id == pre.paper_id
    trace = service.trace(pre.paper_id, verify_source_bytes=True)
    assert trace.current.version_id == journal.version_id
    assert "abstract" not in trace.current.fields
    assert [event.reason for event in trace.selections] == [
        "initial",
        "journal_upgrade",
    ]
    assert trace.relations[0].state == "effective"
    assert (
        service.submit(
            observation(
                doi="10.1/pre", version_kind="preprint", fields={}, relations=relation()
            )
        )
        == evidence
    )
    service.validate_all()


def test_existing_papers_keep_identity_and_relation_is_retained_success(
    tmp_path: Path,
) -> None:
    db = tmp_path / "facts.sqlite"
    upgrade_database(db)
    service = PaperFacts(db, tmp_path / "data")
    pre = service.submit(observation(doi="10.1/pre", version_kind="preprint"))
    journal = service.submit(observation(doi="10.1/journal"))
    assert pre.paper_id and journal.paper_id
    linked = service.submit(
        observation(
            doi="10.1/pre",
            version_kind="preprint",
            payload=b"linked",
            relations=relation(),
        )
    )
    assert (linked.status, linked.reason) == ("retained", "requires_merge")
    left, right = service.trace(pre.paper_id), service.trace(journal.paper_id)
    assert left.relations == right.relations
    assert left.relations[0].state == "requires_merge"
    assert left.current.paper_id != right.current.paper_id
    assert (
        service.submit(
            observation(
                doi="10.1/pre",
                version_kind="preprint",
                payload=b"linked",
                relations=relation(),
            )
        )
        == linked
    )
    service.validate_all()


def test_reverse_alias_is_one_fact_and_never_selected_history_is_explicit(
    tmp_path: Path,
) -> None:
    db = tmp_path / "facts.sqlite"
    upgrade_database(db)
    service = PaperFacts(db, tmp_path / "data")
    pre = service.submit(
        observation(doi="10.1/pre", version_kind="preprint", relations=relation())
    )
    first = service.submit(
        observation(doi="10.1/journal", relations=relation("has-preprint"))
    )
    second_relation = (
        {
            "kind": "is-preprint-of",
            "source_doi": "10.1/pre",
            "target_doi": "10.1/journal2",
            "locator": "relation[1]",
        },
    )
    service.submit(
        observation(
            doi="10.1/pre",
            version_kind="preprint",
            payload=b"second relation",
            relations=second_relation,
        )
    )
    second = service.submit(observation(doi="10.1/journal2"))
    assert pre.paper_id and second.version_id and first.version_id
    trace = service.trace(pre.paper_id)
    assert trace.current.version_id == first.version_id
    assert trace.selection_conflicts == (second.version_id,)
    assert len(trace.relations) == 2
    assert service.revision(second.version_id, 1).selection is None
    assert pre.version_id
    selected = service.revision(pre.version_id, 1).selection
    assert selected is not None and selected.version_id == pre.version_id
    service.validate_all()


def test_existing_endpoint_wrong_kind_is_controlled_relation_rejection(
    tmp_path: Path,
) -> None:
    db = tmp_path / "facts.sqlite"
    upgrade_database(db)
    service = PaperFacts(db, tmp_path / "data")
    pre = service.submit(observation(doi="10.1/journal", version_kind="preprint"))
    assert pre.paper_id
    before = service.trace(pre.paper_id)
    result = service.submit(
        observation(doi="10.1/pre", version_kind="preprint", relations=relation())
    )
    assert (result.status, result.reason) == ("rejected", "invalid_relation")
    assert service.trace(pre.paper_id) == before


def test_relations_only_new_contribution_keeps_candidates_and_raw_alias(
    tmp_path: Path,
) -> None:
    from datetime import UTC, datetime

    db = tmp_path / "facts.sqlite"
    upgrade_database(db)
    service = PaperFacts(db, tmp_path / "data")
    pre = service.submit(observation(doi="10.1/pre", version_kind="preprint"))
    raw = (
        {
            "kind": "is-preprint-of",
            "source_doi": "DOI:10.1/Pre",
            "target_doi": "https://doi.org/10.1/Journal",
            "locator": "relation[0]",
        },
    )
    linked = service.submit(
        observation(
            doi="10.1/pre",
            version_kind="preprint",
            payload=b"new relation with same fields",
            observed_at=datetime(2026, 1, 2, tzinfo=UTC),
            relations=raw,
        )
    )
    assert linked.status == "retained" and pre.paper_id
    trace = service.trace(pre.paper_id)
    assert len(trace.observations) == 1
    assert trace.relations[0].state == "endpoint_missing"
    assert trace.relations[0].journal_paper_id is None
    assert (
        trace.relations[0].assertions[0].raw_target_doi
        == "https://doi.org/10.1/Journal"
    )
    assert trace.relations[0].assertions[0].raw_source_doi == "DOI:10.1/Pre"
    service.validate_all()


def test_multiple_papers_do_not_move_existing_versions(tmp_path: Path) -> None:
    db = tmp_path / "facts.sqlite"
    upgrade_database(db)
    service = PaperFacts(db, tmp_path / "data")
    first = service.submit(observation(doi="10.1/pre1", version_kind="preprint"))
    second = service.submit(observation(doi="10.1/pre2", version_kind="preprint"))
    links = tuple(
        {
            "kind": "has-preprint",
            "source_doi": "10.1/final",
            "target_doi": doi,
            "locator": doi,
        }
        for doi in ("10.1/pre1", "10.1/pre2")
    )
    final = service.submit(observation(doi="10.1/final", relations=links))
    assert final.status == "retained" and final.reason == "requires_merge"
    assert final.paper_id not in {first.paper_id, second.paper_id}
    assert final.paper_id
    assert {relation.state for relation in service.trace(final.paper_id).relations} == {
        "requires_merge"
    }
    service.validate_all()


def test_manual_preprint_fields_stay_on_old_version(tmp_path: Path) -> None:
    from tests.test_manual_corrections import correction

    db = tmp_path / "facts.sqlite"
    upgrade_database(db)
    service = PaperFacts(db, tmp_path / "data")
    pre = service.submit(
        observation(doi="10.1/pre", version_kind="preprint", relations=relation())
    )
    assert pre.paper_id and pre.version_id
    assert service.correct(correction(pre.version_id)).status == "retained"
    journal = service.submit(
        observation(
            doi="10.1/journal", fields={"volume": {"value": "1", "locator": "volume"}}
        )
    )
    assert service.show(pre.paper_id).version_id == journal.version_id
    assert set(service.show(pre.paper_id).fields) == {"volume"}
    assert service.revision(pre.version_id, 2).fields["title"].source_kind == "manual"


def test_feed_version_uses_previously_retained_authoritative_relation(
    tmp_path: Path,
) -> None:
    from tests.feed_support import item

    db = tmp_path / "facts.sqlite"
    upgrade_database(db)
    service = PaperFacts(db, tmp_path / "data")
    pre = service.submit(
        observation(doi="10.1/pre", version_kind="preprint", relations=relation())
    )
    feed = service.register_feed("https://example.org/feed")
    journal = service.submit(item(feed.feed_id, doi="10.1/journal"))
    assert pre.paper_id and journal.paper_id == pre.paper_id
    assert service.show(pre.paper_id).version_id == journal.version_id
    assert service.trace(pre.paper_id).relations[0].state == "effective"
    service.validate_all()


def test_requires_merge_stays_successful_when_candidate_material_is_reused(
    tmp_path: Path,
) -> None:
    from datetime import UTC, datetime

    db = tmp_path / "facts.sqlite"
    upgrade_database(db)
    service = PaperFacts(db, tmp_path / "data")
    pre = service.submit(observation(doi="10.1/pre", version_kind="preprint"))
    service.submit(observation(doi="10.1/journal"))
    linked = service.submit(
        observation(
            doi="10.1/pre",
            version_kind="preprint",
            payload=b"links",
            relations=relation(),
        )
    )
    repeat = service.submit(
        observation(
            doi="10.1/pre",
            version_kind="preprint",
            observed_at=datetime(2026, 1, 2, tzinfo=UTC),
            payload=b"same fields different material",
        )
    )
    assert linked.reason == repeat.reason == "requires_merge"
    assert repeat.status == "retained" and pre.paper_id
    assert service.trace(pre.paper_id).relations[0].state == "requires_merge"
    service.validate_all()


def test_bidirectional_registry_evidence_is_one_canonical_relation(
    tmp_path: Path,
) -> None:
    db = tmp_path / "facts.sqlite"
    upgrade_database(db)
    service = PaperFacts(db, tmp_path / "data")
    first = service.submit(
        observation(
            doi="10.1/pre",
            version_kind="preprint",
            source_kind="registry",
            provider="crossref",
            query_key="10.1/pre",
            fields={},
            relations=relation(),
        )
    )
    reverse = service.submit(
        observation(
            doi="10.1/journal",
            source_kind="registry",
            provider="crossref",
            query_key="10.1/journal",
            fields={},
            relations=relation("has-preprint"),
        )
    )
    assert first.status == "retained" and reverse.status == "not_retained"
    pre = service.submit(observation(doi="10.1/pre", version_kind="preprint"))
    assert pre.paper_id
    trace = service.trace(pre.paper_id)
    assert len(trace.relations) == 1
    assert {assertion.raw_kind for assertion in trace.relations[0].assertions} == {
        "is-preprint-of",
        "has-preprint",
    }
    service.validate_all()


def test_strong_target_conflict_does_not_retain_new_relation(tmp_path: Path) -> None:
    db = tmp_path / "facts.sqlite"
    upgrade_database(db)
    service = PaperFacts(db, tmp_path / "data")
    pre = service.submit(observation(doi="10.1/pre", version_kind="preprint"))
    other = service.submit(observation(doi="10.1/other"))
    assert pre.paper_id
    before = service.trace(pre.paper_id)
    result = service.submit(
        observation(
            doi="10.1/pre",
            version_kind="preprint",
            relations=relation(),
            payload=b"new relation",
            target_paper_id=other.paper_id,
            target_version_id=other.version_id,
        )
    )
    assert (result.status, result.reason, result.conflict) == (
        "rejected",
        "identity_conflict",
        "doi_owner_conflict",
    )
    assert service.trace(pre.paper_id) == before
    service.validate_all()


def test_many_relations_to_one_paper_still_have_unique_ownership(
    tmp_path: Path,
) -> None:
    db = tmp_path / "facts.sqlite"
    upgrade_database(db)
    service = PaperFacts(db, tmp_path / "data")
    links = tuple(
        {
            "kind": "is-preprint-of",
            "source_doi": "10.1/pre",
            "target_doi": journal,
            "locator": journal,
        }
        for journal in ("10.1/j1", "10.1/j2")
    )
    original = service.submit(
        observation(doi="10.1/pre", version_kind="preprint", relations=links)
    )
    first = service.submit(observation(doi="10.1/j1"))
    service.submit(observation(doi="10.1/j2"))
    incoming_links = tuple({**link, "source_doi": "10.1/pre2"} for link in links)
    incoming = service.submit(
        observation(doi="10.1/pre2", version_kind="preprint", relations=incoming_links)
    )
    assert incoming.status == "retained" and incoming.reason is None
    assert original.paper_id and incoming.paper_id == original.paper_id
    assert service.show(original.paper_id).version_id == first.version_id
    service.validate_all()
