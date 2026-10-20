"""在 A2 配置矩阵之上只核对投影传播与少量跨阶段隔离。"""

import json
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from paper_radar.config import (
    ConfigError,
    compile_config,
    load_config_snapshot,
    project_config,
)
from paper_radar.stage_inputs import build_stage_input, compare_stage_inputs
from tests.config_projection_support import full_inputs, new_yaml_version
from tests.stage_input_recovery_support import (
    rebuild_inputs,
    synthetic_members,
    synthetic_submission,
)


@pytest.mark.parametrize(
    ("mutation", "changed"),
    [
        ("boundary_prompt", {"boundary"}),
        ("topic", {"value"}),
        ("backend", {"extraction"}),
        ("reuse_thinking", {"structured", "body"}),
        ("read_model", set()),
        ("journal_tier", set()),
        ("pi_version", set()),
        ("adapter_version", set()),
        ("screening_thinking", {"boundary", "value"}),
    ],
)
def test_only_actual_stage_projection_changes_propagate_to_the_same_facts(
    tmp_path: Path, mutation: str, changed: set[str]
) -> None:
    settings, database = full_inputs(tmp_path)
    before = compile_config(settings, database)
    inputs = rebuild_inputs(before, synthetic_members(), synthetic_submission())
    if mutation == "boundary_prompt":
        prompt = tmp_path / "prompts/screening/boundary-v1.md"
        prompt.with_name("boundary-v2.md").write_bytes(b"Changed boundary prompt\n")
        settings.write_text(
            settings.read_text().replace("boundary: v1", "boundary: v2", 1)
        )
    elif mutation == "topic":
        new_yaml_version(
            settings, "topics", lambda c: c["topics"][0].update(name="Changed topic")
        )
    elif mutation == "backend":
        new_yaml_version(
            settings,
            "extraction",
            lambda c: c.update(pdf_backend="threaded_docling_parse"),
        )
    elif mutation == "read_model":
        new_yaml_version(
            settings,
            "models",
            lambda c: c["reading"].update(model="changed-read-model"),
        )
    elif mutation == "journal_tier":
        new_yaml_version(
            settings, "journals", lambda c: c["journals"][0].update(tier="low")
        )
    elif mutation in {"pi_version", "adapter_version"}:
        new_yaml_version(
            settings,
            "adapters.screening",
            lambda c: c.update(
                {mutation: "1.2.0" if mutation == "pi_version" else "transport-v2"}
            ),
        )
    else:
        slot = "reuse_assessment" if mutation == "reuse_thinking" else "screening"
        new_yaml_version(
            settings, f"adapters.{slot}", lambda c: c.update(thinking_level="high")
        )
    after = compile_config(settings, database)
    assert before.snapshot_id != after.snapshot_id
    projections_before = project_config(before).projections
    projections_after = project_config(after).projections
    database_before = database.read_bytes()
    for case, old in inputs.items():
        # 明确保留同一份旧来源。当前 extraction 变化不能暗中替换其引用。
        new = build_stage_input(after, old.stage, old.facts)
        projected_change = (
            projections_before[old.stage].projection_id
            != projections_after[old.stage].projection_id
        )
        assert (
            (new.fingerprint != old.fingerprint)
            == projected_change
            == (case in changed)
        )
        result = compare_stage_inputs(old, new)
        assert result.status == ("changed" if case in changed else "same")
        assert result.changed_components == (
            ("config_projection",) if projected_change else ()
        )
    assert database.read_bytes() == database_before
    if mutation in {"pi_version", "adapter_version"}:
        first = before.adapters["screening"]
        second = after.adapters["screening"]
        assert first is not None and second is not None
        assert first.semantics_id == second.semantics_id
        assert (settings.parent / "adapters/pi-v2.yaml").exists()


@pytest.mark.parametrize("category", ["profile", "extraction"])
def test_real_snapshot_declaration_renaming_and_comments_preserve_all_stage_inputs(
    tmp_path: Path, category: str
) -> None:
    settings, database = full_inputs(tmp_path)
    compiled = compile_config(settings, database)
    before = load_config_snapshot(database, compiled.snapshot_id)
    inputs = rebuild_inputs(before, synthetic_members(), synthetic_submission())
    path = new_yaml_version(settings, category, lambda content: None)
    path.write_text("# PRIVATE_DECLARATION_COMMENT\n" + path.read_text())
    compiled_after = compile_config(settings, database)
    after = load_config_snapshot(database, compiled_after.snapshot_id)
    assert before.snapshot_id != after.snapshot_id
    for old in inputs.values():
        new = build_stage_input(after, old.stage, old.facts)
        assert new.payload_bytes == old.payload_bytes
        assert new.fingerprint == old.fingerprint
        assert compare_stage_inputs(old, new).status == "same"


@pytest.mark.parametrize(
    ("contract", "selector", "changed"),
    [
        ("boundary", "boundary", {"boundary"}),
        ("value-prediction", "value_prediction", {"value"}),
        ("reuse-assessment", "reuse_assessment", {"structured", "body"}),
    ],
)
def test_future_authoritative_contract_fixture_changes_only_its_consumers(
    tmp_path: Path, contract: str, selector: str, changed: set[str]
) -> None:
    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    inputs = rebuild_inputs(snapshot, synthetic_members(), synthetic_submission())
    payload = json.loads(snapshot.payload_json)
    schema = next(
        entry["config"]
        for entry in payload["materials"]
        if entry["kind"] == "contract_schema" and entry["name"] == contract
    )
    schema["x-paper-radar-contract"]["version"] = "fixture-v2"
    # 沿用 A2 的纯投影 fixture; 不编译或登记伪生产版本。
    future = replace(snapshot, payload_json=json.dumps(payload))
    for case, old in inputs.items():
        new = build_stage_input(future, old.stage, old.facts)
        assert (new.fingerprint != old.fingerprint) == (case in changed)
        assert compare_stage_inputs(old, new).changed_components == (
            ("config_projection",) if case in changed else ()
        )
    selectors = yaml.safe_load(settings.read_text())
    selectors["contracts"][selector] = "fixture-v2"
    settings.write_text(yaml.safe_dump(selectors))
    with pytest.raises(ConfigError, match=rf"contracts\.{selector}"):
        compile_config(settings, database)
    assert load_config_snapshot(database, snapshot.snapshot_id) == snapshot
