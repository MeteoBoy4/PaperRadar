"""关系输入的封闭正负矩阵。"""

from pathlib import Path

import pytest

from paper_radar.papers import PaperFacts
from paper_radar.storage.database import upgrade_database
from tests.test_paper_service import observation
from tests.test_version_relations import relation


@pytest.mark.parametrize("order", [("pre", "journal"), ("journal", "pre")])
@pytest.mark.parametrize("when", ["before", "with_first"])
def test_endpoint_order_preserves_one_paper_and_formal_priority(
    tmp_path: Path, order: tuple[str, str], when: str
) -> None:
    db = tmp_path / "facts.sqlite"
    upgrade_database(db)
    service = PaperFacts(db, tmp_path / "data")
    if when == "before":
        assert (
            service.submit(
                observation(
                    doi="10.1/pre",
                    version_kind="preprint",
                    fields={},
                    relations=relation(),
                )
            ).status
            == "retained"
        )
    results = {}
    for index, name in enumerate(order):
        results[name] = service.submit(
            observation(
                doi="10.1/" + name,
                version_kind="preprint" if name == "pre" else "journal",
                payload=name.encode(),
                relations=relation() if when == "with_first" and index == 0 else (),
            )
        )
    assert results["pre"].paper_id == results["journal"].paper_id
    assert results["pre"].paper_id
    trace = service.trace(results["pre"].paper_id)
    assert len(trace.versions) == 2
    assert trace.current.version_id == results["journal"].version_id
    assert trace.relations[0].state == "effective"
    service.validate_all()


@pytest.mark.parametrize(
    "changes,reason",
    [
        (
            {
                "relations": (
                    {
                        "kind": "cites",
                        "source_doi": "10.1/pre",
                        "target_doi": "10.1/journal",
                        "locator": "r",
                    },
                )
            },
            "unsupported_relation",
        ),
        (
            {
                "relations": (
                    {
                        "kind": "is-preprint-of",
                        "source_doi": "10.1/pre",
                        "target_doi": "10.1/pre",
                        "locator": "r",
                    },
                )
            },
            "invalid_relation",
        ),
        (
            {
                "relations": (
                    {
                        "kind": "is-preprint-of",
                        "source_doi": "10.1/pre",
                        "target_doi": "10.1/journal",
                        "locator": " ",
                    },
                )
            },
            "invalid_relation",
        ),
        ({"doi": "10.1/unrelated"}, "invalid_relation"),
        ({"version_kind": "journal"}, "invalid_relation"),
        ({"source_kind": "manual"}, "unsupported_source"),
        ({"source_kind": "feed"}, "unsupported_relation"),
        (
            {
                "relations": (
                    {
                        "kind": "is-preprint-of",
                        "source_doi": "10.1/pre",
                        "target_doi": "10.1/journal",
                        "locator": "https://example.org/?secret=x",
                    },
                )
            },
            "invalid_observation",
        ),
    ],
)
def test_invalid_relation_rejects_entire_observation(
    tmp_path: Path, changes: dict[str, object], reason: str
) -> None:
    db = tmp_path / "facts.sqlite"
    upgrade_database(db)
    service = PaperFacts(db, tmp_path / "data")
    result = service.submit(
        observation(
            doi="10.1/pre", version_kind="preprint", relations=relation(), **changes
        )
        if not ({"doi", "version_kind", "relations"} & changes.keys())
        else observation(
            **{
                "doi": "10.1/pre",
                "version_kind": "preprint",
                "relations": relation(),
                **changes,
            }
        )
    )
    assert (result.status, result.reason, result.paper_id) == ("rejected", reason, None)
    service.validate_all()


def test_registry_can_retain_relation_before_versions_and_receive_related_endpoint(
    tmp_path: Path,
) -> None:
    db = tmp_path / "facts.sqlite"
    upgrade_database(db)
    service = PaperFacts(db, tmp_path / "data")
    request = observation(
        doi="10.1/pre",
        version_kind="preprint",
        source_kind="registry",
        provider="crossref",
        query_key="10.1/pre",
        fields={},
        relations=relation(),
    )
    result = service.submit(request)
    assert (result.status, result.version_id) == ("retained", None)
    pre = service.submit(observation(doi="10.1/pre", version_kind="preprint"))
    journal = service.submit(
        observation(
            doi="10.1/journal",
            source_kind="registry",
            provider="crossref",
            query_key="10.1/journal",
        )
    )
    assert pre.paper_id and journal.paper_id == pre.paper_id
    assert service.show(pre.paper_id).version_id == journal.version_id
    service.validate_all()


def test_same_material_same_parser_cannot_change_relation_interpretation(
    tmp_path: Path,
) -> None:
    from datetime import UTC, datetime

    db = tmp_path / "facts.sqlite"
    upgrade_database(db)
    service = PaperFacts(db, tmp_path / "data")
    original = service.submit(observation(doi="10.1/pre", version_kind="preprint"))
    result = service.submit(
        observation(
            doi="10.1/pre",
            version_kind="preprint",
            observed_at=datetime(2026, 1, 2, tzinfo=UTC),
            relations=relation(),
        )
    )
    assert (result.status, result.reason) == ("rejected", "invalid_observation")
    assert original.paper_id and not service.trace(original.paper_id).relations
