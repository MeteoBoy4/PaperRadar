"""公共配置服务的正文提取配置与可回放语义。"""

import json
from dataclasses import FrozenInstanceError
from enum import StrEnum
from pathlib import Path

import pytest

from paper_radar.config import (
    StageName,
    check_config,
    compile_config,
    load_config_snapshot,
)
from tests.config_extraction_support import FORMULA_YAML, extraction_inputs


def test_extraction_is_ready_without_profile_pdf_or_installed_parser(
    tmp_path: Path,
) -> None:
    settings, _, db = extraction_inputs(tmp_path)
    checked = check_config(settings, db)
    assert checked.stages[StageName.EXTRACTION].status == "ready"
    assert checked.stages[StageName.EXTRACTION].missing == ()
    assert checked.stages[StageName.BOUNDARY].status == "not_ready"
    saved = compile_config(settings, db)
    assert saved == checked == compile_config(settings, db)
    assert load_config_snapshot(db, saved.snapshot_id) == saved


def test_default_formula_candidates_freeze_model_and_source_separation(
    tmp_path: Path,
) -> None:
    settings, _, db = extraction_inputs(tmp_path)
    saved = compile_config(settings, db)
    assert saved.extraction is not None
    options = json.loads(saved.extraction.backend_config_json)
    assert options["policy"]["do_formula_enrichment"] is True
    assert options["formula"]["engine"] == "transformers"
    assert options["formula"]["torch_dtype"] == "float32"
    assert options["formula"]["expansion_factor"] == 0.18
    assert options["policy"]["formula_evidence"] == "candidate_requires_pdf_review"
    assert options["policy"]["preserve_source_text"] is True
    assert [model.stage for model in saved.extraction.model_artifacts] == [
        "layout",
        "table",
        "formula",
    ]


def test_model_stages_are_controlled_without_changing_persisted_identity(
    tmp_path: Path,
) -> None:
    settings, _, db = extraction_inputs(tmp_path)
    saved = compile_config(settings, db)
    assert saved.extraction is not None
    assert all(
        isinstance(model.stage, StrEnum) for model in saved.extraction.model_artifacts
    )
    # 从改动前公共服务得到的固定身份。类型整理不能改变既有有效配置语义。
    assert saved.snapshot_id == (
        "ba91a2df31e69d9caa248ee0ffb899dfaa2302a0b0d8fde6cac1047a0acd42d4"
    )
    assert saved.extraction.backend_config_hash == (
        "c5ab2231b523d646b9766610c262fcc602fc6c6d9b2803bd011c813d3e53adcb"
    )
    assert saved.extraction.model_artifacts_hash == (
        "a68e0a79937ae0622c5d47103225ab9571e2399ec3764e07a603877c6106fd38"
    )
    assert load_config_snapshot(db, saved.snapshot_id) == saved


def test_effective_defaults_and_controlled_toolchain_are_archived(
    tmp_path: Path,
) -> None:
    settings, _, db = extraction_inputs(tmp_path)
    saved = compile_config(settings, db)
    assert saved.extraction is not None
    backend = saved.extraction.backend
    assert backend.backend_id == "docling"
    assert backend.backend_version == "2.135.0"
    assert dict(backend.component_versions) == {
        "docling-slim": "2.135.0",
        "docling-core": "2.101.1",
        "docling-ibm-models": "4.0.3",
        "pypdfium2": "5.14.0",
        "torch": "2.14.1+cpu",
        "torchvision": "0.29.1+cpu",
        "transformers": "5.19.0",
    }
    options = json.loads(saved.extraction.backend_config_json)
    assert options["pdf_backend"] == "pypdfium2"
    assert options["pdf_options"] == {}
    assert options["layout_engine"] == "transformers"
    assert options["table_mode"] == "accurate"
    for field, expected in {
        "device": "cpu",
        "paper_execution": "serial",
        "do_ocr": False,
        "do_table_structure": True,
        "do_cell_matching": True,
        "heading_hierarchy": True,
        "keep_empty_clusters": False,
        "force_backend_text": False,
        "use_reading_order_separators": True,
        "json_image_mode": "placeholder",
        "markdown_image_mode": "placeholder",
    }.items():
        assert options["policy"][field] == expected
    assert saved.extraction.normalization_version == "v1"
    entry = json.loads(saved.payload_json)["materials"][0]
    assert entry["kind"] == entry["name"] == "extraction"
    assert entry["config"]["backend"]["component_versions"] == dict(
        backend.component_versions
    )
    assert entry["config"]["backend_config"] == options
    with pytest.raises(FrozenInstanceError):
        saved.extraction.backend_config_json = "{}"  # type: ignore[misc]


@pytest.mark.parametrize("selector", ["", "extraction: null\n"])
def test_missing_extraction_is_saved_as_not_ready(
    tmp_path: Path, selector: str
) -> None:
    settings, _, db = extraction_inputs(tmp_path)
    settings.write_text(selector or "{}\n")
    saved = compile_config(settings, db)
    assert saved.stages[StageName.EXTRACTION].missing == ("extraction_config",)
    assert saved.extraction is None
    assert load_config_snapshot(db, saved.snapshot_id) == saved


def test_formula_can_be_explicitly_disabled_without_unused_model_identity(
    tmp_path: Path,
) -> None:
    settings, path, db = extraction_inputs(tmp_path)
    path.write_text(
        path.read_text().replace(FORMULA_YAML, "")
        + "policy:\n  do_formula_enrichment: false\n"
    )
    saved = compile_config(settings, db)
    assert saved.extraction is not None
    assert [model.stage for model in saved.extraction.model_artifacts] == [
        "layout",
        "table",
    ]
    assert "formula" not in json.loads(saved.extraction.backend_config_json)
    assert load_config_snapshot(db, saved.snapshot_id) == saved


@pytest.mark.parametrize("backend", ["pypdfium2", "threaded_docling_parse"])
def test_pdf_backend_versions_come_from_one_controlled_manifest(
    tmp_path: Path,
    backend: str,
) -> None:
    settings, path, db = extraction_inputs(tmp_path)
    path.write_text(path.read_text() + f"pdf_backend: {backend}\n")
    saved = compile_config(settings, db)
    assert saved.extraction is not None
    components = dict(saved.extraction.backend.component_versions)
    if backend == "pypdfium2":
        assert "docling-parse" not in components
    else:
        assert components["docling-parse"] == "7.22.2"
        assert components["pypdfium2"] == "5.14.0"
        assert json.loads(saved.extraction.backend_config_json)["pdf_options"] == {
            "enforce_same_font": True,
            "include_bitmap_images": False,
            "render_pages": True,
            "render_scale": 1.0,
        }


@pytest.mark.parametrize("change", ["backend", "commit", "file_hash", "table_mode"])
def test_new_versions_change_only_their_extraction_semantics(
    tmp_path: Path,
    change: str,
) -> None:
    settings, path, db = extraction_inputs(tmp_path)
    first = compile_config(settings, db)
    raw = path.read_text().replace("extraction-v1", "extraction-v2")
    if change == "backend":
        raw += "pdf_backend: threaded_docling_parse\n"
    elif change == "commit":
        raw = raw.replace("77ede7cc7bed96d853c58f319734803d6ea2ea5c", "1" * 40)
    elif change == "file_hash":
        raw = raw.replace("a" * 64, "2" * 64)
    else:
        raw = raw.replace("tableformer/accurate/", "tableformer/fast/")
        raw = raw.replace("tableformer_accurate", "tableformer_fast")
        raw = raw.replace("  table:\n", "  table:\n    mode: fast\n")
    (path.parent / "extraction-v2.yaml").write_text(raw)
    settings.write_text("extraction: extraction-v2\n")
    second = compile_config(settings, db)
    assert first.extraction != second.extraction
    assert first.snapshot_id != second.snapshot_id
    assert first.escalation == second.escalation
    assert first.extraction is not None and second.extraction is not None
    if change in ("commit", "file_hash"):
        assert (
            first.extraction.backend_config_hash
            == second.extraction.backend_config_hash
        )
        assert (
            first.extraction.model_artifacts_hash
            != second.extraction.model_artifacts_hash
        )
    else:
        assert (
            first.extraction.backend_config_hash
            != second.extraction.backend_config_hash
        )
    assert load_config_snapshot(db, first.snapshot_id) == first
    assert load_config_snapshot(db, second.snapshot_id) == second


def test_synthetic_example_is_ready_and_history_replays(tmp_path: Path) -> None:
    from paper_radar.config import upgrade_database

    db = tmp_path / "example.sqlite3"
    upgrade_database(db)
    settings = (
        Path(__file__).resolve().parents[1] / "examples/config/settings-extraction.yaml"
    )
    saved = compile_config(settings, db)
    assert saved.stages[StageName.EXTRACTION].status == "ready"
    assert load_config_snapshot(db, saved.snapshot_id) == saved
