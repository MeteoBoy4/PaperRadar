"""#23 公共配置服务的投影身份与阶段隔离。"""

import json
import shutil
from pathlib import Path

import pytest

from paper_radar.config import (
    StageName,
    compile_config,
    diff_config_snapshots,
    load_config_snapshot,
    project_config,
    upgrade_database,
)
from tests.config_projection_support import full_inputs, new_yaml_version

# 由手写的六份 null 载荷独立核算。不调用被测投影函数生成期望。
EMPTY_PROJECTION_IDS = {
    "boundary": "aab555b7f9a72aa0defc46e26c2acff8e2c049aa0a1963269f58939b5890edef",
    "value": "596117b4c02102a311e6ad12b3ccf7d78a9e8fb476ea331902d13542cc2bfcd7",
    "reuse": "479fd77a3c5ad0f34573ae098805e2847fff9225506f55290f9e46848708c312",
    "extraction": "7f02369742e41760dfeb0f60cd590c75113ede7d628ae6891d4db2e923998ad3",
    "read": "d29eb8a9f2ffb87b1274dac11155a5736bd3a00f66bfdeb15845a679092a14e2",
    "suggestion": "ca6dabac4c760f6f3f2b92b808d497b5c2c9ee0834300f5e1a50b5ca9dc07fdc",
}
EMPTY_BASELINE_ID = "5e2a09709f8d43c7790e5ca68ac144e22f7492d11486b317170270104894ec59"


def test_missing_materials_have_fixed_projection_and_baseline_payloads(
    tmp_path: Path,
) -> None:
    settings = tmp_path / "config/settings.yaml"
    settings.parent.mkdir()
    settings.write_text("{}\n", encoding="utf-8")
    database = tmp_path / "db.sqlite3"
    upgrade_database(database)
    snapshot = compile_config(settings, database)
    semantics = project_config(load_config_snapshot(database, snapshot.snapshot_id))
    boundary = semantics.projections[StageName.BOUNDARY]
    assert boundary.payload_json == (
        '{"components":{"adapter":null,"contract":null,"model":null,'
        '"profile":null,"prompt":null},"format_version":1,'
        '"kind":"stage_config_projection","stage":"boundary"}'
    )
    assert len(semantics.projections) == 6
    assert {
        stage.value: projection.projection_id
        for stage, projection in semantics.projections.items()
    } == EMPTY_PROJECTION_IDS
    assert semantics.baseline.baseline_id == EMPTY_BASELINE_ID
    assert json.loads(semantics.baseline.payload_json) == {
        "format_version": 1,
        "kind": "calibration_baseline",
        "projections": {
            stage: EMPTY_PROJECTION_IDS[stage]
            for stage in ("boundary", "value", "reuse", "extraction", "suggestion")
        },
    }
    assert all(stage.status.value == "not_ready" for stage in snapshot.stages.values())
    result = diff_config_snapshots(database, snapshot.snapshot_id, snapshot.snapshot_id)
    assert not result.snapshot_changed
    assert not result.identity_changes
    assert not result.projection_changes
    assert not result.calibration_changed
    assert result.before_baseline == result.after_baseline == semantics.baseline


def test_complete_snapshot_projects_exact_consumers_and_is_immutable(
    tmp_path: Path,
) -> None:
    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    semantics = project_config(snapshot)
    components = {
        stage: json.loads(projection.payload_json)["components"]
        for stage, projection in semantics.projections.items()
    }
    assert components[StageName.BOUNDARY]["profile"] == {
        "background": "climate",
        "core_questions": "rain",
        "transferable_methods": "statistics",
        "available_data_and_tools": "reanalysis",
        "theory_and_cognitive_interests": "mechanisms",
        "constraints_and_exclusions": "none",
    }
    assert components[StageName.BOUNDARY]["model"] == {
        "provider": "provider-a",
        "model": "shared-model",
        "protocol": "prompt_only",
        "temperature": 0.0,
        "top_p": 1.0,
    }
    assert components[StageName.BOUNDARY]["prompt"] == "Boundary prompt\n"
    assert components[StageName.VALUE]["topics"] == [
        {"id": "active", "name": "启用方向", "description": "storms"}
    ]
    assert components[StageName.REUSE]["excerpt_priority"] == [
        "availability",
        "methods",
    ]
    assert components[StageName.REUSE]["excerpt_selector_version"] == "v1"
    assert set(components[StageName.SUGGESTION]) == {
        "suggestion_rule_version",
        "reuse_escalation_research_values",
        "contract",
    }
    assert components[StageName.SUGGESTION]["reuse_escalation_research_values"] == [3]
    assert components[StageName.READ]["contract"] is None
    assert components[StageName.READ]["chunking_version"] == "v1"
    assert snapshot.stages[StageName.READ].missing == ("read_contract",)
    schema = components[StageName.BOUNDARY]["contract"]["schema"]
    assert schema["x-paper-radar-contract"] == {"name": "boundary", "version": "v1"}
    assert set(components[StageName.BOUNDARY]) == {
        "profile",
        "model",
        "prompt",
        "contract",
        "adapter",
    }
    assert "extraction" not in components[StageName.REUSE]
    assert "extraction" not in components[StageName.READ]
    replacement = semantics.projections[StageName.BOUNDARY]
    with pytest.raises(TypeError):
        semantics.projections[StageName.READ] = replacement  # type: ignore[index]
    assert "climate" not in repr(semantics)


@pytest.mark.parametrize(
    ("slot", "expected"),
    [
        ("screening", ("boundary", "value")),
        ("reuse_assessment", ("reuse",)),
        ("reading", ("read",)),
    ],
)
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("provider", "provider-b"),
        ("model", "new-model"),
        ("temperature", 0.7),
        ("top_p", 0.8),
    ],
)
def test_models_file_changes_only_the_selected_slot(
    tmp_path: Path, slot: str, expected: tuple[str, ...], field: str, value: str | float
) -> None:
    settings, database = full_inputs(tmp_path)
    before = compile_config(settings, database)
    new_yaml_version(
        settings, "models", lambda content: content[slot].update({field: value})
    )
    after = compile_config(settings, database)
    result = diff_config_snapshots(database, before.snapshot_id, after.snapshot_id)
    assert tuple(change.stage.value for change in result.projection_changes) == expected
    assert result.calibration_changed == (slot != "reading")
    assert [change.category for change in result.identity_changes] == ["models.models"]


@pytest.mark.parametrize(
    ("prompt", "expected"),
    [
        ("boundary", ("boundary",)),
        ("value", ("value",)),
        ("reuse", ("reuse",)),
        ("reading", ("read",)),
    ],
)
def test_prompt_text_including_whitespace_changes_only_its_consumer(
    tmp_path: Path, prompt: str, expected: tuple[str, ...]
) -> None:
    settings, database = full_inputs(tmp_path)
    before = compile_config(settings, database)
    relative = "reading/v1.md" if prompt == "reading" else f"screening/{prompt}-v1.md"
    source = tmp_path / "prompts" / relative
    source.with_name(source.name.replace("v1", "v2")).write_bytes(
        source.read_bytes() + b" \n"
    )
    settings.write_text(
        settings.read_text().replace(f"  {prompt}: v1", f"  {prompt}: v2", 1)
    )
    after = compile_config(settings, database)
    result = diff_config_snapshots(database, before.snapshot_id, after.snapshot_id)
    assert tuple(change.stage.value for change in result.projection_changes) == expected
    assert result.calibration_changed == (prompt != "reading")


@pytest.mark.parametrize(
    "category",
    [
        "profile",
        "models",
        "topics",
        "journals",
        "escalation",
        "extraction",
        "read",
        "adapters.screening",
    ],
)
def test_declaration_renaming_and_yaml_reformatting_preserve_semantics(
    tmp_path: Path, category: str
) -> None:
    settings, database = full_inputs(tmp_path)
    before = compile_config(settings, database)
    path = new_yaml_version(settings, category, lambda content: None)
    path.write_text("# changed comment\n" + path.read_text())
    after = compile_config(settings, database)
    result = diff_config_snapshots(database, before.snapshot_id, after.snapshot_id)
    assert result.snapshot_changed
    assert result.identity_changes
    assert not result.projection_changes
    assert not result.calibration_changed
    if category == "profile":
        assert json.loads(after.payload_json)["selectors"]["profile"] == "profile-v2"


def test_same_prompt_bytes_with_new_declaration_preserve_projections(
    tmp_path: Path,
) -> None:
    settings, database = full_inputs(tmp_path)
    before = compile_config(settings, database)
    prompt = tmp_path / "prompts/screening/boundary-v1.md"
    (prompt.parent / "boundary-v2.md").write_bytes(prompt.read_bytes())
    settings.write_text(
        settings.read_text().replace("  boundary: v1", "  boundary: v2", 1)
    )
    after = compile_config(settings, database)
    result = diff_config_snapshots(database, before.snapshot_id, after.snapshot_id)
    (change,) = result.identity_changes
    assert change.before[0].version == "v1"
    assert change.after[0].version == "v2"
    assert change.before[0].raw_sha256 == change.after[0].raw_sha256
    assert result.snapshot_changed and not result.projection_changes
    assert not result.calibration_changed


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("field", ["name", "description", "id"])
def test_only_enabled_topic_meanings_affect_value(
    tmp_path: Path, enabled: bool, field: str
) -> None:
    settings, database = full_inputs(tmp_path)
    before = compile_config(settings, database)
    index = 0 if enabled else 1
    new_yaml_version(
        settings,
        "topics",
        lambda content: content["topics"][index].update({field: "changed"}),
    )
    after = compile_config(settings, database)
    result = diff_config_snapshots(database, before.snapshot_id, after.snapshot_id)
    assert tuple(change.stage.value for change in result.projection_changes) == (
        ("value",) if enabled else ()
    )
    assert result.calibration_changed == enabled


def test_profile_text_semantics_change_all_model_consumers(tmp_path: Path) -> None:
    settings, database = full_inputs(tmp_path)
    before = compile_config(settings, database)
    new_yaml_version(
        settings, "profile", lambda content: content.update(background="climate ")
    )
    after = compile_config(settings, database)
    result = diff_config_snapshots(database, before.snapshot_id, after.snapshot_id)
    assert tuple(change.stage.value for change in result.projection_changes) == (
        "boundary",
        "value",
        "reuse",
        "read",
    )
    assert result.calibration_changed


def test_journal_reputation_changes_only_the_full_snapshot(tmp_path: Path) -> None:
    settings, database = full_inputs(tmp_path)
    before = compile_config(settings, database)
    new_yaml_version(
        settings, "journals", lambda content: content["journals"][0].update(tier="low")
    )
    after = compile_config(settings, database)
    result = diff_config_snapshots(database, before.snapshot_id, after.snapshot_id)
    assert result.snapshot_changed and result.identity_changes
    assert not result.projection_changes and not result.calibration_changed


def test_history_and_single_snapshot_semantics_do_not_need_source_files(
    tmp_path: Path,
) -> None:
    settings, database = full_inputs(tmp_path)
    before = compile_config(settings, database)
    new_yaml_version(settings, "read", lambda content: None)
    after = compile_config(settings, database)
    known = project_config(before)
    moved = tmp_path / "moved"
    for folder in ("config", "prompts", "contracts"):
        shutil.copytree(tmp_path / folder, moved / folder)
    other_database = moved / "db.sqlite3"
    upgrade_database(other_database)
    assert compile_config(moved / "config/settings.yaml", other_database) == after
    for folder in ("config", "prompts", "contracts"):
        shutil.rmtree(tmp_path / folder)
    loaded = load_config_snapshot(database, before.snapshot_id)
    database.unlink()
    assert project_config(loaded) == known
    assert (
        project_config(load_config_snapshot(other_database, after.snapshot_id)) == known
    )
