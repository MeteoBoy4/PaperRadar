"""B-E15 独立 D1: 规范强身份、权威图与跨发现稳定性。"""

import sqlite3
from pathlib import Path

import pytest

from paper_radar.papers import PaperFacts
from tests.exposure_support import backup, decision, exposed, initialized, payload
from tests.test_experiment_candidates_cli import invoke
from tests.test_paper_service import observation


@pytest.mark.parametrize("state", ["effective", "requires_merge", "endpoint_missing"])
@pytest.mark.parametrize("side", ["preprint", "journal"])
def test_authoritative_edges_are_symmetric_conservative_and_semantically_deduplicated(
    tmp_path: Path, state: str, side: str
) -> None:
    root = initialized(tmp_path / "experiment")
    papers = PaperFacts(root.database, root.data_root)
    relation = {
        "kind": "is-preprint-of",
        "source_doi": "DOI:10.1/PRE",
        "target_doi": "https://doi.org/10.1/JOURNAL",
        "locator": "relation[0]",
    }
    if state == "effective":
        papers.submit(
            observation(
                doi="10.1/pre",
                version_kind="preprint",
                fields={},
                relations=(relation,),
            )
        )
    found = {}
    for kind in ("preprint", "journal"):
        if state == "endpoint_missing" and kind != side:
            continue
        result = papers.submit(
            observation(
                doi="10.1/pre" if kind == "preprint" else "10.1/journal",
                version_kind=kind,
                payload=kind.encode(),
            )
        )
        assert result.paper_id
        found[kind] = result.paper_id
        if state == "effective" and side == "preprint" and kind == "preprint":
            decision(root, result.paper_id)
    if state != "effective":
        papers.submit(
            observation(
                doi="10.1/pre",
                version_kind="preprint",
                fields={},
                payload=b"authority",
                relations=(relation,),
            )
        )
    # 关系断言不要求创建其 source_doi 端点。
    if not (state == "effective" and side == "preprint"):
        decision(root, found[side])
    papers.submit(
        observation(
            doi="10.1/unrelated-pre",
            version_kind="preprint",
            fields={},
            payload=b"unrelated",
            relations=(
                {
                    "kind": "is-preprint-of",
                    "source_doi": "10.1/unrelated-pre",
                    "target_doi": "10.1/unrelated-journal",
                    "locator": "relation[1]",
                },
            ),
        )
    )
    assert papers.trace(found[side]).relations[0].state == state
    first, document, original = payload(root)
    assert document["papers"] == [
        {
            "doi": "10.1/pre" if side == "preprint" else "10.1/journal",
            "version_kind": side,
            "categories": ["decision"],
        }
    ]
    assert document["relations"] == [
        {
            "kind": "is-preprint-of",
            "preprint_doi": "10.1/pre",
            "journal_doi": "10.1/journal",
        }
    ]
    papers.submit(
        observation(
            doi="10.1/journal",
            fields={},
            payload=b"duplicate-reverse-assertion",
            relations=(
                {
                    "kind": "has-preprint",
                    "source_doi": "10.1/journal",
                    "target_doi": "10.1/pre",
                    "locator": "reverse[0]",
                },
            ),
        )
    )
    if state == "endpoint_missing":
        other_kind = "journal" if side == "preprint" else "preprint"
        papers.submit(
            observation(
                doi="10.1/journal" if other_kind == "journal" else "10.1/pre",
                version_kind=other_kind,
                payload=b"later-discovered-endpoint",
            )
        )
    second, _, repeated = payload(root)
    assert second == first and repeated == original
    # VACUUM 可以重排隐式 rowid;冻结范围仍以显式持久键恢复。
    with sqlite3.connect(root.database) as connection:
        connection.execute("VACUUM")
    saved = backup(root, tmp_path / "backups")
    assert saved.exit_code == 0, saved.output


def test_metadata_revision_and_repeated_discovery_keep_portable_bytes(
    tmp_path: Path,
) -> None:
    root = initialized(tmp_path / "experiment")
    paper_id, version_id = exposed(root, doi="DOI:10.1/EXPOSED")
    first, _, original = payload(root)
    papers = PaperFacts(root.database, root.data_root)
    papers.correct(
        {
            "version_id": version_id,
            "request_id": "volume",
            "actor": "owner",
            "reason": "PRIVATE_REASON",
            "fields": {"volume": {"value": "42", "locator": "volume"}},
        }
    )
    assert papers.show(paper_id).revision_no == 2
    papers.submit(observation(doi="https://doi.org/10.1/exposed"))
    second, _, repeated = payload(root)
    assert second == first and repeated == original
    assert b"PRIVATE_" not in repeated and paper_id.encode() not in repeated


def test_exposed_subject_without_strong_doi_is_not_silently_omitted(
    tmp_path: Path,
) -> None:
    root = initialized(tmp_path / "experiment")
    exposed(root, doi=None)
    result = invoke("export-exposure", "--root", str(root.root))
    assert result.exit_code == 2 and "strong_identity_missing" in result.output
    assert "补充强 DOI" in result.output
    assert "PRIVATE_" not in result.output
    assert not (root.views / "exposure").exists()


def test_transitive_authoritative_graph_keeps_only_the_connected_component(
    tmp_path: Path,
) -> None:
    root = initialized(tmp_path / "experiment")
    exposed(root, doi="10.1/journal")
    papers = PaperFacts(root.database, root.data_root)
    first, _, _ = payload(root)
    for suffix, preprint, journal in (
        ("one", "10.1/pre", "10.1/journal"),
        ("two", "10.1/pre", "10.1/journal-two"),
        ("unrelated", "10.1/other-pre", "10.1/other-journal"),
    ):
        papers.submit(
            observation(
                doi=preprint,
                version_kind="preprint",
                fields={},
                payload=suffix.encode(),
                relations=(
                    {
                        "kind": "is-preprint-of",
                        "source_doi": preprint,
                        "target_doi": journal,
                        "locator": suffix,
                    },
                ),
            )
        )
    second, document, _ = payload(root)
    assert second["export_id"] != first["export_id"]
    assert document["papers"] == [
        {"doi": "10.1/journal", "version_kind": "journal", "categories": ["decision"]}
    ]
    assert document["relations"] == [
        {
            "kind": "is-preprint-of",
            "preprint_doi": "10.1/pre",
            "journal_doi": "10.1/journal",
        },
        {
            "kind": "is-preprint-of",
            "preprint_doi": "10.1/pre",
            "journal_doi": "10.1/journal-two",
        },
    ]
    saved = backup(root, tmp_path / "backups")
    assert saved.exit_code == 0, saved.output
