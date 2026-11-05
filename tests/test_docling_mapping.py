"""D1:真实 docling-core 对象的窄映射,不解析 PDF/加载模型。"""

import importlib.util
from importlib import import_module
from pathlib import Path
from typing import Any

import pytest

from paper_radar.body.models import ParserFailure
from paper_radar.docling_execution.mapping import map_document

# 基础安装不收集 SDK 构造测试;extra+dev 必须收集并实际执行。
pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("docling_core") is None,
    reason="仅 extra+dev 的真实 core 对象映射",
)


def sample() -> tuple[Any, Any, Any, Any]:
    BoundingBox = import_module("docling_core.types.doc.base").BoundingBox
    CoordOrigin = import_module("docling_core.types.doc.base").CoordOrigin
    Size = import_module("docling_core.types.doc.base").Size
    ProvenanceItem = import_module(
        "docling_core.types.doc.common.reference"
    ).ProvenanceItem
    DoclingDocument = import_module("docling_core.types.doc.document").DoclingDocument
    DocItemLabel = import_module("docling_core.types.doc.labels").DocItemLabel

    document = DoclingDocument(name="synthetic")
    for page in (1, 2):
        document.add_page(page_no=page, size=Size(width=600, height=800))
    group = document.add_group(name="section")
    heading = document.add_heading(
        "Methods",
        level=3,
        parent=group,
        prov=ProvenanceItem(
            page_no=1,
            bbox=BoundingBox(
                coord_origin=CoordOrigin.BOTTOMLEFT, l=10, t=700, r=500, b=680
            ),
            charspan=(0, 7),
        ),
    )
    text = document.add_text(
        label=DocItemLabel.TEXT,
        text="A😀BC",
        orig="A😀BC",
        parent=group,
        prov=ProvenanceItem(
            page_no=1,
            bbox=BoundingBox(
                coord_origin=CoordOrigin.BOTTOMLEFT, l=10, t=660, r=500, b=640
            ),
            charspan=(0, 2),
        ),
    )
    text.prov.append(
        ProvenanceItem(
            page_no=2,
            bbox=BoundingBox(
                coord_origin=CoordOrigin.BOTTOMLEFT, l=10, t=700, r=500, b=680
            ),
            charspan=(2, 4),
        )
    )
    formula = document.add_formula(
        text="x=2",
        orig="x≈2",
        prov=ProvenanceItem(
            page_no=2,
            bbox=BoundingBox(
                coord_origin=CoordOrigin.BOTTOMLEFT, l=10, t=600, r=500, b=580
            ),
            charspan=(0, 3),
        ),
    )
    return document, heading, text, formula


def test_tree_order_all_provenance_orig_and_candidates_are_preserved() -> None:
    document, heading, text, formula = sample()
    document.body.children.reverse()
    mapped, raw = map_document(
        document,
        page_count=2,
        processed_pages=(1, 2),
        has_text_layer=True,
        formula_enabled=True,
    )
    assert [b.ref for b in mapped.blocks] == [
        "#/body",
        formula.self_ref,
        "#/groups/0",
        heading.self_ref,
        text.self_ref,
    ]
    assert mapped.blocks[1].orig == "x≈2"
    assert mapped.blocks[1].generated_text == "x=2"
    assert mapped.blocks[1].formula_mode == "unknown"
    assert mapped.blocks[3].heading_level == 3
    assert mapped.blocks[4].parent_ref == "#/groups/0"
    assert [p.charspan for p in mapped.blocks[4].provenance] == [(0, 2), (2, 4)]
    assert mapped.blocks[4].provenance[0].bbox == (10.0, 640.0, 500.0, 660.0)
    assert b'"schema_name":"DoclingDocument"' in raw


def test_missing_pages_and_unknown_layers_fail_closed() -> None:
    ContentLayer = import_module(
        "docling_core.types.doc.common.content_layer"
    ).ContentLayer

    document, _, text, _ = sample()
    with pytest.raises(ParserFailure) as error:
        map_document(
            document,
            page_count=3,
            processed_pages=(1, 2),
            has_text_layer=True,
            formula_enabled=True,
        )
    assert error.value.failure == "extraction_failed_quality_gate"
    text.content_layer = ContentLayer.INVISIBLE
    with pytest.raises(ParserFailure):
        map_document(
            document,
            page_count=2,
            processed_pages=(1, 2),
            has_text_layer=True,
            formula_enabled=True,
        )


def test_bad_charspan_is_preserved_and_rejected_by_public_artifact_quality(
    tmp_path: Path,
) -> None:
    from paper_radar.fulltext.artifacts import FulltextArtifacts
    from paper_radar.storage.artifacts import ArtifactStore
    from paper_radar.storage.database import upgrade_database

    document, _, text, _ = sample()
    text.prov[-1].charspan = (2, 99)
    canonical, raw = map_document(
        document,
        page_count=2,
        processed_pages=(1, 2),
        has_text_layer=True,
        formula_enabled=True,
    )
    assert canonical.blocks[3].provenance[-1].charspan == (2, 99)
    database = tmp_path / "db.sqlite3"
    upgrade_database(database)
    saved = FulltextArtifacts(ArtifactStore(database, tmp_path / "data")).publish(
        canonical,
        extraction_fingerprint="a" * 64,
        backend_config_hash="b" * 64,
        model_artifacts_hash="c" * 64,
        elapsed_seconds=0.0,
        peak_memory_bytes=0,
        document_json=raw,
    )
    assert "evidence_replay" in {i.failure for i in saved.quality.issues}


def test_table_cells_remain_restricted_display_and_images_are_removed() -> None:
    import json

    BoundingBox = import_module("docling_core.types.doc.base").BoundingBox
    ImageRef = import_module("docling_core.types.doc.common.reference").ImageRef
    ProvenanceItem = import_module(
        "docling_core.types.doc.common.reference"
    ).ProvenanceItem
    TableCell = import_module("docling_core.types.doc.items.table.table_data").TableCell
    TableData = import_module("docling_core.types.doc.items.table.table_data").TableData
    from pydantic import AnyUrl

    document, _, _, _ = sample()
    table = document.add_table(
        data=TableData(
            num_rows=1,
            num_cols=1,
            table_cells=[
                TableCell(
                    text="12.5",
                    start_row_offset_idx=0,
                    end_row_offset_idx=1,
                    start_col_offset_idx=0,
                    end_col_offset_idx=1,
                )
            ],
        ),
        prov=ProvenanceItem(
            page_no=1, bbox=BoundingBox(l=1, t=1, r=100, b=100), charspan=(0, 0)
        ),
    )
    # 显式已有嵌图不能依赖 generate_images=False 或 PLACEHOLDER 消失。
    document.pages[1].image = ImageRef(
        mimetype="image/png",
        dpi=72,
        size=document.pages[1].size,
        uri=AnyUrl("data:image/png;base64,AAAA"),
    )
    canonical, raw = map_document(
        document,
        page_count=2,
        processed_pages=(1, 2),
        has_text_layer=True,
        formula_enabled=True,
    )
    mapped = next(b for b in canonical.blocks if b.ref == table.self_ref)
    assert mapped.orig == "" and mapped.text == "12.5" and mapped.role == "placeholder"
    assert mapped.provenance[0].charspan == (0, 0)
    assert "image" not in json.loads(raw)["pages"]["1"]
    assert b"base64" not in raw


def test_picture_children_and_furniture_are_not_lost() -> None:
    BoundingBox = import_module("docling_core.types.doc.base").BoundingBox
    ContentLayer = import_module(
        "docling_core.types.doc.common.content_layer"
    ).ContentLayer
    ProvenanceItem = import_module(
        "docling_core.types.doc.common.reference"
    ).ProvenanceItem
    DocItemLabel = import_module("docling_core.types.doc.labels").DocItemLabel
    document, _, _, _ = sample()
    picture = document.add_picture(
        prov=ProvenanceItem(
            page_no=2, bbox=BoundingBox(l=1, t=1, r=100, b=100), charspan=(0, 0)
        )
    )
    caption = document.add_text(
        label=DocItemLabel.CAPTION,
        text="Caption",
        orig="Caption",
        parent=picture,
        prov=ProvenanceItem(
            page_no=2, bbox=BoundingBox(l=1, t=101, r=100, b=120), charspan=(0, 7)
        ),
    )
    footer = document.add_text(
        label=DocItemLabel.PAGE_FOOTER,
        text="Journal",
        orig="Journal",
        content_layer=ContentLayer.FURNITURE,
        prov=ProvenanceItem(
            page_no=1, bbox=BoundingBox(l=1, t=780, r=100, b=790), charspan=(0, 7)
        ),
    )
    mapped, _ = map_document(
        document,
        page_count=2,
        processed_pages=(1, 2),
        has_text_layer=True,
        formula_enabled=True,
    )
    by_ref = {block.ref: block for block in mapped.blocks}
    assert by_ref[caption.self_ref].orig == "Caption"
    assert by_ref[caption.self_ref].parent_ref == picture.self_ref
    assert by_ref[footer.self_ref].content_layer == "furniture"
