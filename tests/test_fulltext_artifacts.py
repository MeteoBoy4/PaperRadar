"""Body D1:规范正文公共生产/读取服务,不继承 A9 固定结论。"""

from pathlib import Path

import pytest

from paper_radar.eligibility import QualityFailure
from paper_radar.fulltext.artifacts import FulltextArtifacts
from paper_radar.fulltext.canonical import (
    CanonicalBlock,
    CanonicalDocument,
    CanonicalPage,
    CanonicalProvenance,
)
from paper_radar.fulltext.models import FulltextError
from paper_radar.storage.artifacts import ArtifactStore
from paper_radar.storage.database import upgrade_database


def document() -> CanonicalDocument:
    return CanonicalDocument(
        pages=(CanonicalPage(page_no=1, width=600.0, height=800.0),),
        blocks=(
            CanonicalBlock(
                ref="#/texts/0",
                order=(0,),
                label="section_header",
                orig="Results",
                text="Results",
                heading_level=3,
                provenance=(
                    CanonicalProvenance(
                        page_no=1, bbox=(20.0, 20.0, 500.0, 50.0), charspan=(0, 7)
                    ),
                ),
            ),
            CanonicalBlock(
                ref="#/texts/1",
                order=(1,),
                label="text",
                orig="Exact source α = 2.",
                text="Exact source α = 2.",
                provenance=(
                    CanonicalProvenance(
                        page_no=1, bbox=(20.0, 60.0, 500.0, 90.0), charspan=(0, 19)
                    ),
                ),
            ),
        ),
    )


def test_registered_body_reconstructs_exact_evidence(tmp_path: Path) -> None:
    database = tmp_path / "database.sqlite3"
    upgrade_database(database)
    service = FulltextArtifacts(ArtifactStore(database, tmp_path / "data"))
    saved = service.publish(
        document(),
        extraction_fingerprint="a" * 64,
        backend_config_hash="b" * 64,
        model_artifacts_hash="c" * 64,
        elapsed_seconds=1.0,
        peak_memory_bytes=4096,
    )
    loaded = service.load(saved.artifact_id, expected_identity=saved.identity)
    assert saved.quality.passed
    assert loaded.context.replay()[1].text == "Exact source α = 2."
    assert loaded.context.evidence[1].evidence_id == "e000002"
    assert b"# Results" in loaded.reading
    assert (
        service.lookup(saved.artifact_id, saved.identity, "e000002")[0].text
        == "Exact source α = 2."
    )


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({"orig": "Bad \ufffd text"}, "text_integrity"),
        ({"orig": "data:image/png;base64,AAAA"}, "embedded_binary"),
        (
            {"role": "generated", "orig": "generated LaTeX"},
            "source_generated_separation",
        ),
        ({"provenance": ()}, "evidence_replay"),
    ],
)
def test_complete_body_retains_exact_automatic_failure(
    tmp_path: Path,
    change: dict[str, object],
    expected: str,
) -> None:
    database = tmp_path / "db"
    upgrade_database(database)
    service = FulltextArtifacts(ArtifactStore(database, tmp_path / "root"))
    original = document()
    block = original.blocks[1].model_copy(update=change)
    if "orig" in change:
        block = block.model_copy(
            update={
                "text": block.orig,
                "provenance": (
                    CanonicalProvenance(
                        page_no=1,
                        bbox=(20.0, 60.0, 500.0, 90.0),
                        charspan=(0, len(block.orig)),
                    ),
                ),
            }
        )
    changed = original.model_copy(update={"blocks": (original.blocks[0], block)})
    saved = service.publish(
        changed,
        extraction_fingerprint="a" * 64,
        backend_config_hash="b" * 64,
        model_artifacts_hash="c" * 64,
        elapsed_seconds=1.0,
        peak_memory_bytes=42,
    )
    assert not saved.quality.passed
    assert QualityFailure(expected) in {issue.failure for issue in saved.quality.issues}
    with pytest.raises(FulltextError) as failure:
        service.load(saved.artifact_id, expected_identity=saved.identity)
    assert failure.value.reason == "quality_failed"
    assert failure.value.quality == saved.quality


def test_every_source_span_must_be_replayable_even_when_excluded(
    tmp_path: Path,
) -> None:
    database = tmp_path / "db"
    upgrade_database(database)
    service = FulltextArtifacts(ArtifactStore(database, tmp_path / "root"))
    original = document()
    header = original.blocks[1].model_copy(
        update={
            "label": "page_header",
            "provenance": (),
        }
    )
    changed = original.model_copy(update={"blocks": (original.blocks[0], header)})
    saved = service.publish(
        changed,
        extraction_fingerprint="a" * 64,
        backend_config_hash="b" * 64,
        model_artifacts_hash="c" * 64,
        elapsed_seconds=1.0,
        peak_memory_bytes=42,
    )
    assert QualityFailure.EVIDENCE_REPLAY in {
        issue.failure for issue in saved.quality.issues
    }


def test_uncovered_source_characters_are_not_presented_as_supported(
    tmp_path: Path,
) -> None:
    database = tmp_path / "db"
    upgrade_database(database)
    service = FulltextArtifacts(ArtifactStore(database, tmp_path / "root"))
    original = document()
    truncated = original.blocks[1].model_copy(
        update={
            "provenance": (
                CanonicalProvenance(
                    page_no=1, bbox=(20.0, 60.0, 500.0, 90.0), charspan=(0, 3)
                ),
            )
        }
    )
    saved = service.publish(
        original.model_copy(update={"blocks": (original.blocks[0], truncated)}),
        extraction_fingerprint="a" * 64,
        backend_config_hash="b" * 64,
        model_artifacts_hash="c" * 64,
        elapsed_seconds=1.0,
        peak_memory_bytes=42,
    )
    assert QualityFailure.EVIDENCE_REPLAY in {
        issue.failure for issue in saved.quality.issues
    }


@pytest.mark.parametrize("extra", ["escaped_binary", "escaped_replacement"])
def test_audit_json_cannot_hide_bad_content_in_escapes(
    tmp_path: Path, extra: str
) -> None:
    database = tmp_path / "db"
    upgrade_database(database)
    service = FulltextArtifacts(ArtifactStore(database, tmp_path / "root"))
    audit = (
        b'{"audit":"\\u0064ata:image/png;base64,AAAA"}'
        if extra == "escaped_binary"
        else b'{"audit":"\\ufffd"}'
    )
    saved = service.publish(
        document(),
        extraction_fingerprint="a" * 64,
        backend_config_hash="b" * 64,
        model_artifacts_hash="c" * 64,
        elapsed_seconds=1.0,
        peak_memory_bytes=42,
        document_json=audit,
    )
    expected = "embedded_binary" if extra == "escaped_binary" else "text_integrity"
    assert expected in {issue.failure.value for issue in saved.quality.issues}


def test_source_display_without_orig_is_not_allowed_to_look_like_source(
    tmp_path: Path,
) -> None:
    database = tmp_path / "db"
    upgrade_database(database)
    service = FulltextArtifacts(ArtifactStore(database, tmp_path / "root"))
    original = document()
    changed = original.model_copy(
        update={
            "blocks": (
                original.blocks[0],
                original.blocks[1].model_copy(
                    update={
                        "orig": "",
                        "text": "generated display",
                        "provenance": (),
                    }
                ),
            )
        }
    )
    saved = service.publish(
        changed,
        extraction_fingerprint="a" * 64,
        backend_config_hash="b" * 64,
        model_artifacts_hash="c" * 64,
        elapsed_seconds=1.0,
        peak_memory_bytes=42,
    )
    assert "source_generated_separation" in {
        issue.failure.value for issue in saved.quality.issues
    }
