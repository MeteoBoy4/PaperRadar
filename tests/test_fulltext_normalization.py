"""normalization v1 的合成版面;不证明真实 Docling 覆盖。"""

from pathlib import Path

import pytest

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


def layout() -> CanonicalDocument:
    def block(
        number: int,
        label: str,
        orig: str,
        page: int,
        *,
        top: float = 100.0,
        **kwargs: object,
    ) -> CanonicalBlock:
        values: dict[str, object] = {
            "ref": f"#/items/{number}",
            "order": (number,),
            "label": label,
            "orig": orig,
            "text": orig,
            "provenance": (
                CanonicalProvenance(
                    page_no=page,
                    bbox=(20.0, top, 500.0, top + 20.0),
                    charspan=(0, len(orig)),
                ),
            ),
            **kwargs,
        }
        return CanonicalBlock.model_validate(values)

    return CanonicalDocument(
        pages=tuple(
            CanonicalPage(page_no=p, width=600.0, height=800.0) for p in (1, 2, 3)
        ),
        blocks=(
            block(0, "title", "Repository cover sheet", 1),
            block(1, "text", "Terms of use", 1),
            block(2, "text", "Journal header", 2, top=5.0),
            block(3, "section_header", "Methods", 2, heading_level=4),
            block(
                4,
                "text",
                "跨页源字符",
                2,
                provenance=(
                    CanonicalProvenance(
                        page_no=2, bbox=(20.0, 700.0, 500.0, 730.0), charspan=(0, 3)
                    ),
                    CanonicalProvenance(
                        page_no=3,
                        bbox=(20.0, 80.0, 500.0, 110.0),
                        charspan=(3, 5),
                        origin="bottom_left",
                    ),
                ),
            ),
            block(5, "text", "Journal header", 3, top=5.0),
            block(
                6,
                "section_header",
                "Nested",
                3,
                heading_level=5,
                parent_ref="#/items/3",
            ),
            block(
                7,
                "formula",
                "a = b",
                3,
                generated_text=r"a = \beta",
                formula_mode="display",
            ),
            block(8, "formula", "", 3, generated_text=r"x^2", formula_mode="inline"),
            block(9, "table", "Value 12", 3),
            block(10, "text", "Glyph \ue000", 3),
            block(11, "picture", "", 3),
        ),
    )


def service_at(tmp_path: Path) -> FulltextArtifacts:
    database = tmp_path / "db"
    upgrade_database(database)
    return FulltextArtifacts(ArtifactStore(database, tmp_path / "root"))


def test_cover_margins_hierarchy_cross_page_and_restricted_sources(
    tmp_path: Path,
) -> None:
    service = service_at(tmp_path)
    saved = service.publish(
        layout(),
        extraction_fingerprint="a" * 64,
        backend_config_hash="b" * 64,
        model_artifacts_hash="c" * 64,
        elapsed_seconds=1.0,
        peak_memory_bytes=4096,
    )
    loaded = service.load(saved.artifact_id, expected_identity=saved.identity)
    text = loaded.reading.decode()
    assert "Repository cover sheet" not in text
    assert "Terms of use" not in text
    assert "Journal header" not in text
    assert "# Methods" in text and "## Nested" in text
    assert [
        part.text
        for part in service.lookup(saved.artifact_id, saved.identity, "e000005")
    ] == ["跨页源", "字符"]
    assert [part.kind for part in loaded.context.replay()][-3:] == [
        "formula",
        "table",
        "text",
    ]
    assert loaded.context.replay()[-1].unreliable
    assert len(loaded.context.evidence) == 6
    assert "[evidence:e000009]" not in text
    assert "[公式不可用" in text and "[图片不可用" in text
    assert [
        (s.mode, s.total, s.with_parent_source, s.placeholder_only)
        for s in saved.statistics.formula
    ] == [
        ("display", 1, 1, 0),
        ("inline", 1, 0, 1),
        ("unknown", 0, 0, 0),
    ]
    assert dict(saved.statistics.member_bytes)["evidence_map"] > 0


def test_container_reordering_and_parser_refs_do_not_change_semantic_members(
    tmp_path: Path,
) -> None:
    service = service_at(tmp_path)
    first_document = layout()
    # 修正源 span 之后作为合成完整制品;SDK 容器枚举不参与顺序身份。
    blocks = list(first_document.blocks)
    cross = blocks[4]
    blocks[4] = cross.model_copy(
        update={
            "provenance": (
                cross.provenance[0],
                cross.provenance[1].model_copy(update={"charspan": (3, 5)}),
            )
        }
    )
    first_document = first_document.model_copy(update={"blocks": tuple(blocks)})
    refs = {b.ref: f"arbitrary-{i}" for i, b in enumerate(first_document.blocks)}
    second_document = first_document.model_copy(
        update={
            "blocks": tuple(
                b.model_copy(
                    update={
                        "ref": refs[b.ref],
                        "parent_ref": refs.get(b.parent_ref or ""),
                    }
                )
                for b in reversed(first_document.blocks)
            )
        }
    )
    first = service.publish(
        first_document,
        extraction_fingerprint="a" * 64,
        backend_config_hash="b" * 64,
        model_artifacts_hash="c" * 64,
        elapsed_seconds=1.0,
        peak_memory_bytes=10,
    )
    second = service.publish(
        second_document,
        extraction_fingerprint="a" * 64,
        backend_config_hash="b" * 64,
        model_artifacts_hash="c" * 64,
        elapsed_seconds=2.0,
        peak_memory_bytes=20,
    )
    assert first.identity == second.identity
    assert first.artifact_id != second.artifact_id
    assert (
        service.load(first.artifact_id, expected_identity=first.identity).context
        == service.load(second.artifact_id, expected_identity=second.identity).context
    )


@pytest.mark.parametrize("status", ["partial", "failure"])
def test_incomplete_conversion_has_no_quality_fact_or_registered_artifact(
    tmp_path: Path, status: str
) -> None:
    service = service_at(tmp_path)
    changed = layout().model_copy(update={"conversion_status": status})
    with pytest.raises(FulltextError) as failure:
        service.publish(
            changed,
            extraction_fingerprint="a" * 64,
            backend_config_hash="b" * 64,
            model_artifacts_hash="c" * 64,
            elapsed_seconds=1.0,
            peak_memory_bytes=10,
        )
    assert failure.value.reason == "conversion_incomplete"
    assert failure.value.quality is None
    assert service.store.list_artifacts() == ()


def test_generated_candidate_cannot_introduce_an_evidence_anchor(
    tmp_path: Path,
) -> None:
    service = service_at(tmp_path)
    original = layout()
    changed = original.model_copy(
        update={
            "blocks": tuple(
                block.model_copy(update={"generated_text": "[evidence:spoof]"})
                if block.label == "formula"
                else block
                for block in original.blocks
            )
        }
    )
    saved = service.publish(
        changed,
        extraction_fingerprint="a" * 64,
        backend_config_hash="b" * 64,
        model_artifacts_hash="c" * 64,
        elapsed_seconds=1.0,
        peak_memory_bytes=1,
    )
    loaded = service.load(saved.artifact_id, expected_identity=saved.identity)
    assert b"[evidence:spoof]" not in loaded.reading
    assert all(e.evidence_id != "spoof" for e in loaded.context.evidence)


def test_formula_placeholder_without_pdf_location_fails_replay_quality(
    tmp_path: Path,
) -> None:
    service = service_at(tmp_path)
    original = layout()
    changed = original.model_copy(
        update={
            "blocks": tuple(
                block.model_copy(update={"provenance": ()})
                if block.label == "formula" and not block.orig
                else block
                for block in original.blocks
            )
        }
    )
    saved = service.publish(
        changed,
        extraction_fingerprint="a" * 64,
        backend_config_hash="b" * 64,
        model_artifacts_hash="c" * 64,
        elapsed_seconds=1.0,
        peak_memory_bytes=1,
    )
    assert "evidence_replay" in {issue.failure.value for issue in saved.quality.issues}


def test_cyclic_hierarchy_is_refused_before_registering_a_body(tmp_path: Path) -> None:
    service = service_at(tmp_path)
    original = layout()
    changed = original.model_copy(
        update={
            "blocks": tuple(
                b.model_copy(update={"parent_ref": b.ref})
                if b.label == "section_header"
                else b
                for b in original.blocks
            )
        }
    )
    with pytest.raises(FulltextError) as failure:
        service.publish(
            changed,
            extraction_fingerprint="a" * 64,
            backend_config_hash="b" * 64,
            model_artifacts_hash="c" * 64,
            elapsed_seconds=1.0,
            peak_memory_bytes=42,
        )
    assert failure.value.reason == "invalid_hierarchy"
    assert service.store.list_artifacts() == ()
