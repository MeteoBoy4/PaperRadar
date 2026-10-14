"""#23 审查修订的公共快照材料与差异类别。"""

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from paper_radar.config import (
    ConfigCategory,
    compile_config,
    diff_config_snapshots,
    load_config_snapshot,
)
from paper_radar.config.compile import MaterialKind
from tests.config_projection_support import full_inputs, new_yaml_version


def test_snapshot_material_access_preserves_shared_versions_and_is_read_only(
    tmp_path: Path,
) -> None:
    settings, database = full_inputs(tmp_path)
    new_yaml_version(
        settings, "adapters.screening", lambda c: c.update(thinking_level="high")
    )
    snapshot = compile_config(settings, database)
    loaded = load_config_snapshot(database, snapshot.snapshot_id)
    assert snapshot.materials == loaded.materials
    materials = loaded.materials
    profile_key = (MaterialKind.PROFILE, "profile", "profile-v1")
    profile = materials[profile_key]
    assert json.loads(profile.config_json) == {
        "version": "profile-v1",
        "background": "climate",
        "core_questions": "rain",
        "transferable_methods": "statistics",
        "available_data_and_tools": "reanalysis",
        "theory_and_cognitive_interests": "mechanisms",
        "constraints_and_exclusions": "none",
    }
    assert {key[2] for key in materials if key[0] is MaterialKind.ADAPTER} == {
        "pi-v1",
        "pi-v2",
    }
    selections = loaded.adapter_selections
    with pytest.raises(TypeError):
        materials[profile_key] = profile  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        profile.version = "changed"  # type: ignore[misc]
    with pytest.raises(TypeError):
        selections["screening"] = "pi-v1"  # type: ignore[index]
    assert selections == {
        "screening": "pi-v2",
        "reuse_assessment": "pi-v1",
        "reading": "pi-v1",
    }
    detached = json.loads(profile.config_json)
    detached["background"] = "changed"
    assert loaded.materials[profile_key] == profile
    assert "climate" not in repr(materials)
    assert load_config_snapshot(database, snapshot.snapshot_id) == snapshot


def test_diff_categories_are_controlled_for_materials_and_selected_adapter_slots(
    tmp_path: Path,
) -> None:
    settings, database = full_inputs(tmp_path)
    before = compile_config(settings, database)
    new_yaml_version(settings, "profile", lambda c: c.update(background="new context"))
    new_yaml_version(
        settings, "adapters.reading", lambda c: c.update(thinking_level="high")
    )
    after = compile_config(settings, database)
    result = diff_config_snapshots(database, before.snapshot_id, after.snapshot_id)
    assert {change.category for change in result.identity_changes} == {
        ConfigCategory.PROFILE,
        ConfigCategory.ADAPTER_READING,
    }
    assert all(
        isinstance(change.category, ConfigCategory)
        for change in result.identity_changes
    )
    assert {change.category.value for change in result.identity_changes} == {
        "profile.profile",
        "adapters.reading",
    }
