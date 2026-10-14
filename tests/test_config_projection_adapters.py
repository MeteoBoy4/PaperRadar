"""adapter 的共享材料、单槽变化与执行审计隔离。"""

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from paper_radar.config import (
    StageName,
    compile_config,
    diff_config_snapshots,
    project_config,
)
from tests.config_projection_support import full_inputs, new_yaml_version


@pytest.mark.parametrize(
    ("slot", "expected"),
    [
        ("screening", ("boundary", "value")),
        ("reuse_assessment", ("reuse",)),
        ("reading", ("read",)),
    ],
)
@pytest.mark.parametrize("component", ["thinking_level", "system_prompt"])
def test_adapter_changes_affect_only_the_actual_slot_consumers(
    tmp_path: Path, slot: str, expected: tuple[str, ...], component: str
) -> None:
    settings, database = full_inputs(tmp_path)
    before = compile_config(settings, database)
    if component == "system_prompt":
        text = b"Changed effective system instruction\n"
        (settings.parent / "prompts/pi-system-v2.md").write_bytes(text)
        new_yaml_version(
            settings,
            f"adapters.{slot}",
            lambda content: content["resources"][0].update(
                version="v2", sha256=hashlib.sha256(text).hexdigest()
            ),
        )
    else:
        new_yaml_version(
            settings,
            f"adapters.{slot}",
            lambda content: content.update(thinking_level="high"),
        )
    after = compile_config(settings, database)
    result = diff_config_snapshots(database, before.snapshot_id, after.snapshot_id)
    assert tuple(change.stage.value for change in result.projection_changes) == expected
    assert result.calibration_changed == (slot != "reading")
    (change,) = result.identity_changes
    assert change.category == f"adapters.{slot}"
    assert change.before[0].version == "pi-v1"
    assert change.after[0].version == "pi-v2"
    adapter = after.adapters[slot]
    assert adapter is not None
    for stage in expected:
        components = json.loads(
            project_config(after).projections[StageName(stage)].payload_json
        )["components"]
        assert components["adapter"] == adapter.semantics_id


@pytest.mark.parametrize(
    ("field", "value"), [("pi_version", "1.2.0"), ("adapter_version", "transport-v2")]
)
def test_execution_audit_versions_never_become_stage_semantics(
    tmp_path: Path, field: str, value: str
) -> None:
    settings, database = full_inputs(tmp_path)
    before = compile_config(settings, database)
    new_yaml_version(
        settings, "adapters.screening", lambda content: content.update({field: value})
    )
    after = compile_config(settings, database)
    result = diff_config_snapshots(database, before.snapshot_id, after.snapshot_id)
    assert result.snapshot_changed and result.identity_changes
    assert not result.projection_changes and not result.calibration_changed


def test_swapping_selected_adapters_is_visible_even_with_identical_material_sets(
    tmp_path: Path,
) -> None:
    settings, database = full_inputs(tmp_path)
    new_yaml_version(
        settings,
        "adapters.reading",
        lambda content: content.update(thinking_level="high"),
    )
    before = compile_config(settings, database)
    selectors = yaml.safe_load(settings.read_text())
    selectors["adapters"].update(screening="pi-v2", reading="pi-v1")
    settings.write_text(yaml.safe_dump(selectors))
    after = compile_config(settings, database)
    result = diff_config_snapshots(database, before.snapshot_id, after.snapshot_id)
    assert tuple(change.stage.value for change in result.projection_changes) == (
        "boundary",
        "value",
        "read",
    )
    assert {change.category for change in result.identity_changes} == {
        "adapters.screening",
        "adapters.reading",
    }
    assert result.calibration_changed
