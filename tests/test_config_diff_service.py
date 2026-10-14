"""真实 SQLite 历史加载、只读 diff、缺项与损坏拒绝。"""

import json
import shutil
import sqlite3
from pathlib import Path

import pytest
import yaml

from paper_radar.config import (
    ConfigError,
    StageName,
    compile_config,
    diff_config_snapshots,
    load_config_snapshot,
    project_config,
)
from tests.config_projection_support import empty_inputs, full_inputs, new_yaml_version
from tests.config_test_support import boundary_inputs


def test_diff_is_read_only_repeatable_and_replays_saved_materials(
    tmp_path: Path,
) -> None:
    settings, database = full_inputs(tmp_path)
    before = compile_config(settings, database)
    new_yaml_version(
        settings, "profile", lambda c: c.update(background="PRIVATE_PROFILE_MARKER")
    )
    after = compile_config(settings, database)
    for folder in ("config", "prompts", "contracts"):
        shutil.rmtree(tmp_path / folder)
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    original = database.read_bytes()
    result = diff_config_snapshots(database, before.snapshot_id, after.snapshot_id)
    assert (
        diff_config_snapshots(database, before.snapshot_id, after.snapshot_id) == result
    )
    assert (
        result.before_baseline
        == project_config(load_config_snapshot(database, before.snapshot_id)).baseline
    )
    assert (
        result.after_baseline
        == project_config(load_config_snapshot(database, after.snapshot_id)).baseline
    )
    assert result.calibration_changed
    assert database.read_bytes() == original
    assert "PRIVATE_PROFILE_MARKER" not in repr(result)


@pytest.mark.parametrize(
    "invalid", ["a" * 63, "A" * 64, "x" * 64, "PRIVATE_ID_MARKER", "a" * 65]
)
@pytest.mark.parametrize("position", ["before", "after"])
def test_diff_rejects_noncanonical_ids_without_echoing_them(
    tmp_path: Path, invalid: str, position: str
) -> None:
    settings, database = empty_inputs(tmp_path)
    saved = compile_config(settings, database)
    ids = (
        (invalid, saved.snapshot_id)
        if position == "before"
        else (saved.snapshot_id, invalid)
    )
    with pytest.raises(ConfigError, match="64 位小写") as error:
        diff_config_snapshots(database, *ids)
    assert invalid not in str(error.value)


def test_identical_unknown_id_and_missing_database_are_not_no_difference(
    tmp_path: Path,
) -> None:
    settings, database = empty_inputs(tmp_path)
    saved = compile_config(settings, database)
    with pytest.raises(ConfigError, match="不存在"):
        diff_config_snapshots(database, "0" * 64, "0" * 64)
    missing = tmp_path / "missing.sqlite3"
    with pytest.raises(ConfigError, match="db upgrade"):
        diff_config_snapshots(missing, saved.snapshot_id, saved.snapshot_id)
    assert not missing.exists()


@pytest.mark.parametrize(
    "damage", ["unknown_format", "payload", "material", "reference", "missing_table"]
)
def test_diff_validates_even_identical_ids_and_never_repairs_damage(
    tmp_path: Path, damage: str
) -> None:
    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    with sqlite3.connect(database) as connection:
        if damage == "unknown_format":
            payload = json.loads(snapshot.payload_json)
            payload["format_version"] = 999
            connection.execute(
                "UPDATE runtime_config_snapshots SET payload_json = ?",
                (json.dumps(payload),),
            )
        elif damage == "payload":
            connection.execute(
                "UPDATE runtime_config_snapshots SET payload_json = ?",
                ("PRIVATE_DAMAGE_MARKER",),
            )
        elif damage == "material":
            connection.execute(
                "UPDATE config_versions SET raw_content = ? WHERE kind = 'profile'",
                (b"PRIVATE_DAMAGE_MARKER",),
            )
        elif damage == "reference":
            connection.execute(
                "DELETE FROM snapshot_version_refs WHERE kind = 'profile'"
            )
        else:
            connection.execute("DROP TABLE runtime_config_snapshots")
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    original = database.read_bytes()
    with pytest.raises(ConfigError) as error:
        diff_config_snapshots(database, snapshot.snapshot_id, snapshot.snapshot_id)
    assert "PRIVATE_DAMAGE_MARKER" not in str(error.value)
    assert database.read_bytes() == original


def test_missing_escalation_changes_only_reuse_suggestion_and_baseline(
    tmp_path: Path,
) -> None:
    settings, database = full_inputs(tmp_path)
    selectors = yaml.safe_load(settings.read_text())
    selectors.pop("escalation")
    settings.write_text(yaml.safe_dump(selectors))
    before = compile_config(settings, database)
    selectors["escalation"] = "escalation-v1"
    settings.write_text(yaml.safe_dump(selectors))
    after = compile_config(settings, database)
    result = diff_config_snapshots(database, before.snapshot_id, after.snapshot_id)
    assert tuple(change.stage.value for change in result.projection_changes) == (
        "reuse",
        "suggestion",
    )
    assert result.calibration_changed
    for change in result.projection_changes:
        assert all(
            not component.before_configured and component.after_configured
            for component in change.components
        )
    assert before.stages[StageName.REUSE].missing == ("excerpt_selector",)
    assert before.stages[StageName.SUGGESTION].missing == (
        "suggestion_rule",
        "escalation_parameters",
    )
    assert after.stages[StageName.READ].missing == ("read_contract",)


def test_placeholder_to_real_text_changes_semantics_without_claiming_readiness(
    tmp_path: Path,
) -> None:
    settings, database = full_inputs(tmp_path)
    profile = settings.parent / "profiles/profile-v1.yaml"
    profile.write_text(
        profile.read_text().replace("background: climate", "background: '... '")
    )
    before = compile_config(settings, database)
    new_yaml_version(settings, "profile", lambda c: c.update(background="climate"))
    after = compile_config(settings, database)
    result = diff_config_snapshots(database, before.snapshot_id, after.snapshot_id)
    assert before.profile_status.value == "placeholder"
    assert tuple(change.stage.value for change in result.projection_changes) == (
        "boundary",
        "value",
        "reuse",
        "read",
    )
    assert result.calibration_changed
    assert after.stages[StageName.READ].status.value == "not_ready"


def test_model_output_protocol_is_semantic_without_requiring_an_adapter(
    tmp_path: Path,
) -> None:
    settings, database = boundary_inputs(tmp_path)
    before = compile_config(settings, database)
    new_yaml_version(
        settings, "models", lambda c: c["screening"].update(protocol="json_object")
    )
    after = compile_config(settings, database)
    result = diff_config_snapshots(database, before.snapshot_id, after.snapshot_id)
    assert tuple(change.stage.value for change in result.projection_changes) == (
        "boundary",
        "value",
    )
    assert result.calibration_changed
