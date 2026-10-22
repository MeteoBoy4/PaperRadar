"""完整组合事实由公共服务构造;仅向新进程传受控引用与独立散列。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from paper_radar.config import compile_config
from paper_radar.papers import PaperFacts, WriteResult
from tests.config_projection_support import full_inputs, new_yaml_version
from tests.feed_support import item
from tests.paper_recovery_reader import digest, mapping_summary
from tests.test_manual_corrections import correction
from tests.test_paper_mapping import screening_fields
from tests.test_paper_service import observation


def at(day: int) -> datetime:
    return datetime(2026, 1, day, tzinfo=UTC)


def links(pre: str, journal: str) -> tuple[dict[str, str], ...]:
    return (
        {
            "kind": "is-preprint-of",
            "source_doi": pre,
            "target_doi": journal,
            "locator": "relations/0",
        },
    )


@dataclass
class RecoveryFacts:
    service: PaperFacts
    papers: tuple[str, ...]
    mappings: list[dict[str, object]]
    pre: WriteResult
    journal: WriteResult
    never: WriteResult
    feed_version: WriteResult
    unbound_artifact: str


def populated(root: Path, *, journal_abstract: bool = True) -> RecoveryFacts:
    settings, database = full_inputs(root)
    old = compile_config(settings, database)
    new_yaml_version(
        settings,
        "topics",
        lambda value: value["topics"][0].update(description="second research focus"),
    )
    new = compile_config(settings, database)
    service = PaperFacts(database, root / "data")
    papers: list[str] = []
    mappings: list[dict[str, object]] = []

    def remember(saved: WriteResult) -> None:
        assert saved.paper_id and saved.version_id and saved.revision_no, (
            saved.model_dump()
        )
        if saved.paper_id not in papers:
            papers.append(saved.paper_id)
        for snapshot in (old, new):
            selector: dict[str, object] = {
                "version_id": saved.version_id,
                "revision_no": saved.revision_no,
                "snapshot_id": snapshot.snapshot_id,
            }
            mapped = service.map_screening_inputs(
                version_id=saved.version_id,
                revision_no=saved.revision_no,
                snapshot_id=snapshot.snapshot_id,
            )
            mappings.append({"selector": selector, "expected": mapping_summary(mapped)})

    feed = service.register_feed("https://example.org/primary?format=rss")
    second_feed = service.register_feed("https://example.org/secondary")
    pre = service.submit(
        observation(
            doi="10.74/pre",
            version_kind="preprint",
            payload=b"preprint material",
            fields=screening_fields(
                "PRIVATE-RECOVERY pre", "PRIVATE-RECOVERY old abstract"
            ),
            relations=links("10.74/pre", "10.74/journal"),
        )
    )
    remember(pre)
    assert pre.paper_id and pre.version_id
    registry = service.submit(
        observation(
            doi="10.74/pre",
            version_kind="preprint",
            source_kind="registry",
            provider="crossref",
            query_key="10.74/pre",
            target_paper_id=pre.paper_id,
            target_version_id=pre.version_id,
            payload=b"registry competing material",
            fields=screening_fields(
                "Registry competing title", "Registry competing abstract"
            ),
        )
    )
    assert registry.status == "retained"
    assert (
        service.submit(
            item(
                feed.feed_id,
                doi="10.74/pre",
                version_kind="preprint",
                payload=b"preprint feed item",
                fields={"pages": {"value": "e74", "locator": "pages"}},
            )
        ).status
        == "retained"
    )
    manual = service.correct(
        correction(
            pre.version_id,
            fields={
                "title": {
                    "value": "PRIVATE-RECOVERY corrected pre",
                    "locator": "page/1",
                }
            },
        )
    )
    remember(manual)
    journal_fields = screening_fields(
        "PRIVATE-RECOVERY formal", "PRIVATE-RECOVERY formal abstract"
    )
    if not journal_abstract:
        del journal_fields["abstract"]
    journal = service.submit(
        observation(
            doi="10.74/journal",
            payload=b"formal material",
            fields=journal_fields,
        )
    )
    remember(journal)
    assert journal.paper_id == pre.paper_id
    mapped = service.map_screening_inputs(
        paper_id=pre.paper_id, snapshot_id=old.snapshot_id
    )
    if journal_abstract:
        assert mapped.value.value and mapped.evidence
        assert mapped.evidence.fields["abstract"].source_kind == "publisher"
    else:
        assert mapped.boundary.reason == mapped.value.reason == "missing_abstract"
    never = service.submit(
        observation(
            doi="10.74/ambiguous",
            payload=b"ambiguous formal",
            fields=screening_fields(
                "PRIVATE-RECOVERY never selected", "PRIVATE-RECOVERY independent"
            ),
            relations=links("10.74/pre", "10.74/ambiguous"),
        )
    )
    remember(never)
    assert never.version_id and never.paper_id == pre.paper_id
    assert service.revision(never.version_id, 1).selection is None
    assert service.show(pre.paper_id).version_id == journal.version_id

    # Feed D3: no DOI -> later registration; cross-feed reuse; A->B->A is
    # last_seen only.
    first = service.submit(item(second_feed.feed_id, fields=screening_fields()))
    remember(first)
    feed_version = service.submit(
        item(
            second_feed.feed_id,
            doi="10.74/feed",
            payload=b"item B",
            observed_at=at(2),
            fields=screening_fields("Feed B", "Feed B abstract"),
        )
    )
    remember(feed_version)
    assert feed_version.paper_id == first.paper_id
    assert (
        service.submit(
            item(second_feed.feed_id, observed_at=at(3), fields=screening_fields())
        )
        == first
    )
    assert service.show(first.paper_id).fields["title"].value == "Feed B"  # type: ignore[arg-type]
    assert (
        service.submit(
            item(
                feed.feed_id,
                doi="10.74/feed",
                entry_id="cross-feed",
                payload=b"cross feed item",
                fields=screening_fields(),
            )
        ).paper_id
        == first.paper_id
    )
    no_doi = service.submit(
        item(
            feed.feed_id,
            entry_id="still-no-doi",
            payload=b"no DOI",
            fields=screening_fields("Unregistered", "No DOI is legal"),
        )
    )
    remember(no_doi)
    assert no_doi.paper_id and service.show(no_doi.paper_id).doi is None

    # Independent current Paper endpoints remain requires_merge; one missing and
    # zero endpoints.
    merge_pre = service.submit(
        observation(
            doi="10.74/merge-pre", version_kind="preprint", payload=b"merge pre"
        )
    )
    merge_journal = service.submit(
        observation(doi="10.74/merge-journal", payload=b"merge formal")
    )
    remember(merge_pre)
    remember(merge_journal)
    assert (
        service.submit(
            observation(
                doi="10.74/merge-pre",
                version_kind="preprint",
                fields={},
                payload=b"merge evidence",
                relations=links("10.74/merge-pre", "10.74/merge-journal"),
            )
        ).reason
        == "requires_merge"
    )
    missing = service.submit(
        observation(
            doi="10.74/missing-pre",
            version_kind="preprint",
            payload=b"one endpoint",
            relations=links("10.74/missing-pre", "10.74/missing-journal"),
        )
    )
    remember(missing)
    unbound = service.submit(
        observation(
            doi="10.74/absent-pre",
            version_kind="preprint",
            fields={},
            payload=b"PRIVATE-RECOVERY relation-only evidence",
            relations=links("10.74/absent-pre", "10.74/absent-journal"),
        )
    )
    assert unbound.status == "retained" and unbound.paper_id is None
    # A relation-only material visible to a real Paper trace, separate from
    # field observations.
    evidence = service.submit(
        observation(
            doi="10.74/pre",
            version_kind="preprint",
            fields={},
            payload=b"PRIVATE-RECOVERY separate relation material",
            relations=links("10.74/pre", "10.74/third-journal"),
        )
    )
    assert evidence.status == "retained"
    unbound_artifact = next(
        r.artifact_id
        for r in service.trace(pre.paper_id).relations
        if r.journal_doi == "10.74/third-journal"
    )

    # Same-payload complete replacement, fallback, text change and all-empty protection.
    reparse = observation(
        doi="10.74/reparse",
        payload=b"reparsed material",
        fields=screening_fields("Reparsed title", "Reparsed old abstract"),
    )
    parsed = service.submit(reparse)
    remember(parsed)
    missing_abstract = service.submit(
        {
            **reparse,
            "parser_version": 2,
            "fields": {"title": screening_fields("Reparsed title")["title"]},
        }
    )
    remember(missing_abstract)
    assert parsed.paper_id and parsed.version_id
    assert (
        service.map_screening_inputs(
            paper_id=parsed.paper_id, snapshot_id=old.snapshot_id
        ).value.reason
        == "missing_abstract"
    )
    fallback = service.submit(
        observation(
            doi="10.74/reparse",
            source_kind="registry",
            provider="crossref",
            query_key="10.74/reparse",
            target_paper_id=parsed.paper_id,
            target_version_id=parsed.version_id,
            payload=b"fallback material",
            fields=screening_fields("Reparsed title", "Reparsed old abstract"),
        )
    )
    remember(fallback)
    assert service.show(parsed.paper_id).fields["abstract"].source_kind == "registry"
    assert fallback.revision_no and missing_abstract.revision_no
    assert fallback.revision_no > missing_abstract.revision_no
    assert (
        service.show(parsed.paper_id).fields["abstract"].acquisition_id
        == fallback.acquisition_id
    )
    original_input = service.map_screening_inputs(
        version_id=parsed.version_id, revision_no=1, snapshot_id=old.snapshot_id
    )
    fallback_input = service.map_screening_inputs(
        paper_id=parsed.paper_id, snapshot_id=old.snapshot_id
    )
    assert original_input.boundary.value == fallback_input.boundary.value
    assert original_input.value.value == fallback_input.value.value
    changed = service.submit(
        {
            **reparse,
            "parser_version": 3,
            "fields": screening_fields("Reparsed title", "Reparsed changed abstract"),
        }
    )
    remember(changed)
    changed_input = service.map_screening_inputs(
        paper_id=parsed.paper_id, snapshot_id=old.snapshot_id
    )
    assert changed_input.value.value and fallback_input.value.value
    assert (
        changed_input.value.value.fingerprint != fallback_input.value.value.fingerprint
    )
    before_empty = service.show(parsed.paper_id)
    empty = service.submit({**reparse, "parser_version": 4, "fields": {}})
    assert empty.status == "not_retained"
    assert service.show(parsed.paper_id) == before_empty
    assert service.submit(reparse) == parsed
    assert (
        service.submit({**reparse, "parser_version": 2, "observed_at": at(4)}).reason
        == "invalid_observation"
    )

    # B4 lightweight acquisitions preserve out-of-order observation authority
    # and references.
    repeated = observation(
        doi="10.74/repeated", payload=b"A response", fields=screening_fields()
    )
    acquired = service.submit(repeated)
    remember(acquired)
    repeat = service.submit({**repeated, "observed_at": at(3)})
    assert repeat.status == "not_retained" and repeat.acquisition_id
    remember(repeat)
    late = service.submit(
        {
            **repeated,
            "payload": b"B response",
            "observed_at": at(2),
            "fields": screening_fields("Earlier B", "Earlier B abstract"),
        }
    )
    assert late.status == "retained" and acquired.paper_id
    assert service.show(acquired.paper_id).fields["title"].value == "Title"
    assert service.submit({**repeated, "observed_at": at(3)}) == repeat
    # Capture all current selectors independently of the historical selector samples.
    for paper_id in papers:
        for snapshot in (old, new):
            mappings.append(
                {
                    "selector": {
                        "paper_id": paper_id,
                        "snapshot_id": snapshot.snapshot_id,
                    },
                    "expected": mapping_summary(
                        service.map_screening_inputs(
                            paper_id=paper_id, snapshot_id=snapshot.snapshot_id
                        )
                    ),
                }
            )
    service.validate_all()
    return RecoveryFacts(
        service,
        tuple(papers),
        mappings,
        pre,
        journal,
        never,
        feed_version,
        unbound_artifact,
    )


def paper_expectations(facts: RecoveryFacts) -> dict[str, object]:
    return {
        paper_id: {
            "trace": digest(facts.service.trace(paper_id).model_dump(mode="json")),
            "show": digest(facts.service.show(paper_id).model_dump(mode="json")),
        }
        for paper_id in facts.papers
    }


def tree_hash(root: Path, *, ignore_sqlite_sidecars: bool = False) -> str:
    """失败断言只展示独立散列,避免 pytest 展开数据库或来源原字节。"""
    import hashlib

    from tests.backup_support import tree

    return digest(
        {
            key: hashlib.sha256(value).hexdigest() if value is not None else None
            for key, value in tree(root).items()
            if not (ignore_sqlite_sidecars and key.endswith(("-wal", "-shm")))
        }
    )
