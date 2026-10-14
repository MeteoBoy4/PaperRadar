"""格式身份和冻结契约标记。未来格式只通过纯投影 fixture 验证。"""

import json
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

import pytest

from paper_radar.config import (
    ConfigError,
    StageName,
    compare_config_snapshots,
    compile_config,
    load_config_snapshot,
    project_config,
    projections,
)
from tests.config_projection_support import empty_inputs, full_inputs
from tests.config_test_support import boundary_inputs


def test_configured_boundary_identity_matches_the_reviewed_nonempty_payload(
    tmp_path: Path,
) -> None:
    settings, database = boundary_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    semantics = project_config(load_config_snapshot(database, snapshot.snapshot_id))
    # 独立手写六段、模型默认值、精确 Prompt 与固定 A1 契约内容核算。
    assert (
        semantics.projections[StageName.BOUNDARY].projection_id
        == "d67c818c67ecaf6f14361ee4f54cf771a50088c6e2d421031299b35a39c41532"
    )


@pytest.mark.parametrize("stage", list(StageName))
def test_projection_formats_evolve_independently_and_only_relevant_ones_affect_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stage: StageName
) -> None:
    settings, database = empty_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    before = project_config(snapshot)
    versions = dict(projections.PROJECTION_FORMAT_VERSIONS)
    versions[stage] = 2
    monkeypatch.setattr(
        projections, "PROJECTION_FORMAT_VERSIONS", MappingProxyType(versions)
    )
    after = project_config(snapshot)
    assert (
        after.projections[stage].projection_id
        != before.projections[stage].projection_id
    )
    for unaffected in StageName:
        if unaffected != stage:
            assert after.projections[unaffected] == before.projections[unaffected]
    assert (after.baseline.baseline_id != before.baseline.baseline_id) == (
        stage != StageName.READ
    )
    payload = json.loads(after.projections[stage].payload_json)
    assert payload["format_version"] == 2
    assert (
        payload["kind"] == "stage_config_projection" and payload["stage"] == stage.value
    )


def test_baseline_format_changes_identity_without_changing_stage_projections(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings, database = empty_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    before = project_config(snapshot)
    monkeypatch.setattr(projections, "BASELINE_FORMAT_VERSION", 2)
    after = project_config(snapshot)
    assert after.projections == before.projections
    assert after.baseline.baseline_id != before.baseline.baseline_id
    assert json.loads(after.baseline.payload_json)["format_version"] == 2


def test_frozen_contract_internal_version_is_retained_in_a_pure_fixture(
    tmp_path: Path,
) -> None:
    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    payload = json.loads(snapshot.payload_json)
    for entry in payload["materials"]:
        if entry["kind"] == "contract_schema" and entry["name"] == "boundary":
            entry["config"]["x-paper-radar-contract"]["version"] = "fixture-v2"
    future = replace(snapshot, payload_json=json.dumps(payload))
    result = compare_config_snapshots(snapshot, future)
    assert tuple(change.stage.value for change in result.projection_changes) == (
        "boundary",
    )
    assert result.calibration_changed


def test_profile_new_selector_must_match_the_embedded_version(tmp_path: Path) -> None:
    settings, database = boundary_inputs(tmp_path)
    original = compile_config(settings, database)
    source = settings.parent / "profiles/profile-v1.yaml"
    source.with_name("profile-v2.yaml").write_bytes(source.read_bytes())
    settings.write_text(settings.read_text().replace("profile-v1", "profile-v2"))
    with pytest.raises(ConfigError, match="不一致"):
        compile_config(settings, database)
    assert load_config_snapshot(database, original.snapshot_id) == original
