"""D1:生产CLI组合实际mapper/normalize/版式/Read消费,仅外部边界替身。"""

import json
from pathlib import Path

import pytest

from paper_radar.body import BodyService
from paper_radar.config import compile_config, load_config_snapshot, project_config
from paper_radar.fulltext.artifacts import FulltextArtifacts
from paper_radar.fulltext.models import EvidenceMap
from paper_radar.reading.acceptance_v2 import validate_read_output_v2
from tests.config_projection_support import new_yaml_version
from tests.experiment_extract_support import executor, extract_fixture
from tests.read_support import candidate
from tests.test_experiment_candidates_cli import FeedFixture, invoke
from tests.test_experiment_candidates_cli import feed as feed
from tests.test_extraction_normalization_repair import item, mapped


def test_cli_extract_v2_drives_persisted_layout_and_read_warnings(
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from paper_radar.docling_execution.models import WorkerResponse
    from paper_radar.experiment import layout_rendering
    from tests.experiment_layout_support import LayoutFixture

    prepared = extract_fixture(feed, tmp_path, monkeypatch)
    old_snapshot = prepared.snapshot
    new_yaml_version(
        prepared.root.settings,
        "extraction",
        lambda value: value.update(normalization_version="v2"),
    )
    prepared.snapshot = compile_config(
        prepared.root.settings, prepared.root.database
    ).snapshot_id
    old = load_config_snapshot(prepared.root.database, old_snapshot)
    new = load_config_snapshot(prepared.root.database, prepared.snapshot)
    assert old.extraction is not None and new.extraction is not None
    assert old.extraction.normalization_version == "v1"
    assert new.extraction.normalization_version == "v2"
    assert old.extraction.backend_config_hash == new.extraction.backend_config_hash
    assert project_config(old).projections != project_config(new).projections
    text = "A coefficient qr qr remains uncertain in this synthetic observation."
    canonical, raw = mapped(
        [
            item(0, "Synthetic recurring banner", label="page_header", top=5.0),
            item(
                1,
                "Synthetic recurring banner",
                label="section_header",
                level=1,
                page=2,
                top=5.0,
            ),
            item(2, "Methods", label="section_header", level=1),
            item(3, text),
            item(4, "Data Availability", label="section_header", level=1),
            item(5, "Competing Interests", label="section_header", level=2),
            item(6, "Bibliography", label="section_header", level=3),
        ]
    )
    calls = executor(
        monkeypatch, WorkerResponse(document=canonical, document_json=raw.decode())
    )
    response = prepared.extract()
    assert response.exit_code == 0, response.output
    assert len(calls) == 1
    body = BodyService(prepared.root.database, prepared.root.data_root)
    current = body.current_body(prepared.prepared.paper_id)
    assert current.identity is not None
    view = body.extraction(current.identity.extraction_fingerprint)
    assert view is not None and view.artifact_id is not None
    assert view.attempts[0].executor_audit is not None
    assert view.attempts[0].executor_audit.normalization_version == "v2"
    members = body.store.read_artifact(view.artifact_id)
    assert json.loads(members["manifest"])["normalization_version"] == "v2"
    evidence_map = EvidenceMap.model_validate_json(members["evidence_map"])
    assert evidence_map.normalization_version == "v2"
    assert "Synthetic recurring banner" not in members["reading"].decode()
    assert [
        b.heading_level for b in evidence_map.reading_blocks if b.heading_level
    ] == [1, 1, 1, 1]
    loaded = FulltextArtifacts(body.store).load(
        view.artifact_id, expected_identity=current.identity
    )
    (support,) = [source for source in loaded.context.replay() if source.text == text]
    assert support.unreliable and support.provenance.start == 0
    reference = {
        "statement": "这段系数待核对。",
        "evidence": [{"evidence_id": support.evidence_id}],
    }
    result = validate_read_output_v2(
        candidate(research_value_reason=reference, reuse_feasibility_reason=reference),
        loaded.context,
        attempt_ordinal=1,
    )
    assert len(result.warnings) == 2
    assert all(
        w.diagnostic and w.diagnostic.reason == "restricted_source_reference"
        for w in result.warnings
    )

    class Renderer:
        def render(
            self, pdf: bytes, evidence_map: EvidenceMap, directory: Path
        ) -> None:
            assert pdf.startswith(b"%PDF-")
            for page in evidence_map.pages:
                (directory / f"page-{page.page_no}.png").write_bytes(b"synthetic image")

    monkeypatch.setattr(layout_rendering, "PdfRenderer", Renderer)
    layout = LayoutFixture(prepared, current.identity)
    materials = invoke(*layout.args("layout-materials"))
    assert materials.exit_code == 0, materials.output
    paths = [
        prepared.root.root / name for name in json.loads(materials.stdout)["materials"]
    ]
    assert len(paths) == 6
    assert "层级=2" not in paths[2].read_text()
    assert "qr qr" in paths[5].read_text() and "unreliable" in paths[5].read_text()
    assert (
        "charspan" in paths[4].read_text()
        and support.evidence_id in paths[4].read_text()
    )
    # 同指纹成功缓存不能再次领取,质量仍须独立所有者核查。
    again = prepared.extract()
    assert again.exit_code == 0, again.output
    cached = body.extraction(view.fingerprint)
    assert len(calls) == 1 and cached is not None
    assert cached.quality.basis == "absent"
    layout.review(passed=False)
    vetoed = body.extraction(view.fingerprint)
    assert vetoed is not None and vetoed.permanent_failure
    rejected = invoke(
        *layout.args("layout-review"),
        "--reviewer",
        "owner",
        "--recorder",
        "agent",
        "--request-id",
        "cannot-override-veto",
        "--body-boundary",
        "true",
        "--reading-order",
        "true",
        "--sections",
        "true",
        "--headers-footers",
        "true",
        "--provenance",
        "true",
        "--restricted-content",
        "true",
    )
    assert rejected.exit_code == 2 and "layout_conflict" in rejected.output


def test_cli_new_normalization_gets_new_fingerprint_and_preserves_old_veto_and_budget(
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from paper_radar.docling_execution.models import WorkerResponse
    from tests.experiment_layout_support import LayoutFixture

    prepared = extract_fixture(feed, tmp_path, monkeypatch)
    canonical, raw = mapped([item(0, "The coefficient qr qr requires review.")])
    calls = executor(
        monkeypatch, WorkerResponse(document=canonical, document_json=raw.decode())
    )
    first = prepared.extract()
    assert first.exit_code == 0, first.output
    body = BodyService(prepared.root.database, prepared.root.data_root)
    old_identity = body.current_body(prepared.prepared.paper_id).identity
    assert old_identity is not None
    LayoutFixture(prepared, old_identity).review(passed=False)
    old = body.extraction(old_identity.extraction_fingerprint)
    assert old is not None and old.artifact_id is not None
    old_members = body.store.read_artifact(old.artifact_id)
    old_snapshot = prepared.snapshot
    old_config = load_config_snapshot(prepared.root.database, old_snapshot)
    new_yaml_version(
        prepared.root.settings,
        "extraction",
        lambda value: value.update(normalization_version="v2"),
    )
    prepared.snapshot = compile_config(
        prepared.root.settings, prepared.root.database
    ).snapshot_id
    second = prepared.extract()
    assert second.exit_code == 0, second.output
    assert len(calls) == 2
    history = body.extractions(prepared.prepared.paper_id)
    assert len(history) == 2
    new = next(value for value in history if value.fingerprint != old.fingerprint)
    assert new.identity is not None and new.artifact_id is not None
    assert new.remaining_attempts == old.remaining_attempts == 1
    assert not new.permanent_failure and new.quality.basis == "absent"
    assert body.extraction(old.fingerprint) == old
    assert body.store.read_artifact(old.artifact_id) == old_members
    assert load_config_snapshot(prepared.root.database, old_snapshot) == old_config
    assert (
        body.current_body(prepared.prepared.paper_id).reason == "ambiguous_extractions"
    )
    old_loaded = FulltextArtifacts(body.store).load(
        old.artifact_id, expected_identity=old_identity
    )
    new_loaded = FulltextArtifacts(body.store).load(
        new.artifact_id, expected_identity=new.identity
    )
    assert old_loaded.context.replay()[0].text == new_loaded.context.replay()[0].text
    assert not old_loaded.context.replay()[0].unreliable
    assert new_loaded.context.replay()[0].unreliable


@pytest.mark.parametrize("suffix", ["", "-threaded"])
def test_new_v2_normalization_examples_compile_through_cold_cli_without_sdk(
    tmp_path: Path,
    suffix: str,
) -> None:
    from paper_radar.config import upgrade_database
    from tests.config_test_support import run_cli

    settings = (
        Path(__file__).parents[1]
        / "examples/config"
        / f"settings-extraction-v3{suffix}.yaml"
    )
    database = tmp_path / "db"
    upgrade_database(database)
    result = run_cli(
        tmp_path,
        "config",
        "compile",
        "--settings",
        str(settings),
        "--database",
        str(database),
    )
    assert result.returncode == 0, result.stderr
    snapshot = load_config_snapshot(
        database, result.stdout.splitlines()[0].split("：")[1]
    )
    assert snapshot.extraction is not None
    assert snapshot.extraction.normalization_version == "v2"
    assert (
        dict(snapshot.extraction.backend.component_versions)["docling-core"]
        == "2.105.0"
    )
    assert json.loads(snapshot.extraction.backend_config_json)["pdf_backend"] == (
        "threaded_docling_parse" if suffix else "pypdfium2"
    )


def test_unknown_normalization_version_still_has_controlled_field_rejection(
    tmp_path: Path,
) -> None:
    from paper_radar.config import ConfigError, check_config
    from tests.config_extraction_support import extraction_inputs

    settings, path, database = extraction_inputs(tmp_path)
    path.write_text(
        path.read_text().replace(
            "normalization_version: v1", "normalization_version: v3"
        )
    )
    for operation in (check_config, compile_config):
        with pytest.raises(
            ConfigError, match=r"extraction\.normalization_version"
        ) as error:
            operation(settings, database)
        assert "extraction.normalization_version" in str(error.value)
