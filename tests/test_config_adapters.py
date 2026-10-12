"""公共配置服务的 Pi 适配器配置与语义消费者。"""

import hashlib
import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from paper_radar.config import (
    StageName,
    check_config,
    compile_config,
    load_config_snapshot,
)
from tests.config_adapter_support import SYSTEM_PROMPT, adapter_inputs
from tests.config_test_support import boundary_inputs


def test_legacy_snapshot_keeps_identity_and_adapters_unconfigured(
    tmp_path: Path,
) -> None:
    settings, db = boundary_inputs(tmp_path)
    before = check_config(settings, db)
    # 从实现前 commit 9e12da9 的真实编译器取得。固定旧格式身份。
    assert before.snapshot_id == (
        "35942f627ddc5d4a7671de32ffebec1641f0a974784651d7102841e7e5fd57d3"
    )
    assert dict(before.adapters) == {
        "screening": None,
        "reuse_assessment": None,
        "reading": None,
    }
    settings.write_text(settings.read_text() + "adapters: {}\n")
    saved = compile_config(settings, db)
    assert saved.snapshot_id == before.snapshot_id
    assert load_config_snapshot(db, saved.snapshot_id) == before


def test_selected_adapters_freeze_effective_prompt_and_independent_slots(
    tmp_path: Path,
) -> None:
    settings, _, db = adapter_inputs(tmp_path)
    checked = check_config(settings, db)
    screening = checked.adapters["screening"]
    assert screening is not None
    assert screening.system_prompt_text == SYSTEM_PROMPT.decode()
    assert screening.thinking_level == "low"
    assert screening.policy.tools == ()
    # 根据手工审查的语义载荷固定。不调用生产函数构造期望。
    assert screening.payload_json == (
        '{"backend":"pi-rpc","format_version":1,"kind":"adapter_semantics",'
        '"policy":{"agent_retry":"disabled","compaction":"disabled",'
        '"extra_model_turns":"disabled","mcp":"disabled",'
        '"provider_retry":"disabled","resource_discovery":"disabled",'
        '"session":"ephemeral_per_attempt","session_persistence":"disabled",'
        '"summarization":"disabled","tools":[],"version":"bounded-rpc-v1"},'
        '"resources":[{"kind":"system_prompt","name":"pi-system",'
        '"sha256":"212c2cd595c12aaf7ca2a4b6783b3f43f85ce077745c2a55f4f18d6c07b9e2d1",'
        '"text":"Frozen effective Pi system prompt\\n"}],"thinking_level":"low"}'
    )
    assert screening.semantics_id == (
        "8f27d5f34c1d940ad3e95b8ab6de2f50eb2177e91ed63fd250d763b4f72ba6e8"
    )
    assert checked.adapters["reuse_assessment"] == screening
    assert checked.adapters["reading"] == screening
    saved = compile_config(settings, db)
    assert checked == saved
    assert load_config_snapshot(db, saved.snapshot_id) == saved


def test_adapter_configuration_is_separate_from_model_and_stage_completeness(
    tmp_path: Path,
) -> None:
    settings, _, db = adapter_inputs(tmp_path)
    configured = check_config(settings, db)
    assert dict(configured.adapter_slots) == {
        "screening": "configured",
        "reuse_assessment": "configured",
        "reading": "configured",
    }
    assert configured.adapter_dependencies == {
        "screening": (StageName.BOUNDARY, StageName.VALUE),
        "reuse_assessment": (StageName.REUSE,),
        "reading": (StageName.READ,),
    }
    assert configured.calibration_adapter_slots == ("screening", "reuse_assessment")
    assert configured.model_slots["reading"] == "unconfigured"
    assert configured.stages[StageName.READ].status == "not_ready"
    settings.write_text(settings.read_text().split("adapters:")[0])
    legacy = check_config(settings, db)
    assert legacy.stages == configured.stages
    assert set(legacy.adapter_slots.values()) == {"unconfigured"}


@pytest.mark.parametrize(
    ("slot", "consumers"),
    [
        ("screening", ("boundary", "value")),
        ("reuse_assessment", ("reuse",)),
        ("reading", ("read",)),
    ],
)
def test_only_selected_consumers_change_when_adapter_parameters_change(
    tmp_path: Path, slot: str, consumers: tuple[str, ...]
) -> None:
    settings, path, db = adapter_inputs(tmp_path)
    first = compile_config(settings, db)
    (path.parent / "pi-v2.yaml").write_text(
        path.read_text().replace("pi-v1", "pi-v2").replace("low", "high")
    )
    settings.write_text(
        settings.read_text().replace(f"{slot}: pi-v1", f"{slot}: pi-v2")
    )
    second = compile_config(settings, db)
    assert first.snapshot_id != second.snapshot_id
    for name in first.adapters:
        assert (first.adapters[name] != second.adapters[name]) == (name == slot)
    assert second.adapter_dependencies[slot] == consumers
    assert (slot in second.calibration_adapter_slots) == (slot != "reading")
    assert load_config_snapshot(db, first.snapshot_id) == first
    assert load_config_snapshot(db, second.snapshot_id) == second


def test_shared_prompt_changes_follow_actual_consumers(tmp_path: Path) -> None:
    settings, path, db = adapter_inputs(tmp_path)
    first = compile_config(settings, db)
    # reading 保留原资源。screening/reuse 共享新系统指令。
    (settings.parent / "prompts/pi-system-v2.md").write_bytes(b"New system prompt\n")
    (path.parent / "pi-v2.yaml").write_text(
        path.read_text()
        .replace("version: pi-v1", "version: pi-v2")
        .replace("version: v1", "version: v2")
        .replace(
            "212c2cd595c12aaf7ca2a4b6783b3f43f85ce077745c2a55f4f18d6c07b9e2d1",
            "373122be9e3bc17657d9d300e89131e9ed013179bc459fe377cd1888a6895cad",
        )
    )
    settings.write_text(
        settings.read_text()
        .replace("screening: pi-v1", "screening: pi-v2")
        .replace("reuse_assessment: pi-v1", "reuse_assessment: pi-v2")
    )
    second = compile_config(settings, db)
    assert second.adapters["screening"] == second.adapters["reuse_assessment"]
    assert second.adapters["reading"] == first.adapters["reading"]
    assert second.adapters["screening"] != first.adapters["screening"]
    assert load_config_snapshot(db, second.snapshot_id) == second


def test_declaration_comments_and_transport_audit_do_not_change_semantics(
    tmp_path: Path,
) -> None:
    settings, path, db = adapter_inputs(tmp_path)
    first = compile_config(settings, db)
    (settings.parent / "prompts/pi-system-renamed.md").write_bytes(SYSTEM_PROMPT)
    (path.parent / "pi-v2.yaml").write_text(
        path.read_text()
        .replace("version: pi-v1", "version: pi-v2")
        .replace("version: v1", "version: renamed")
        .replace("transport-v1", "transport-v2")
        + "# YAML comment\n"
    )
    settings.write_text(settings.read_text().replace("pi-v1", "pi-v2"))
    second = compile_config(settings, db)
    assert second.snapshot_id != first.snapshot_id
    assert second.adapters == first.adapters
    old = first.adapters["screening"]
    new = second.adapters["screening"]
    assert old is not None and new is not None
    assert old.semantics_id == new.semantics_id
    assert load_config_snapshot(db, first.snapshot_id) == first
    assert load_config_snapshot(db, second.snapshot_id) == second


def test_adapter_semantics_and_dependencies_are_read_only(tmp_path: Path) -> None:
    settings, _, db = adapter_inputs(tmp_path)
    saved = check_config(settings, db)
    with pytest.raises(TypeError):
        saved.adapters["reading"] = None  # type: ignore[index]
    with pytest.raises(TypeError):
        saved.adapter_dependencies["reading"] = ()  # type: ignore[index]
    adapter = saved.adapters["screening"]
    assert adapter is not None
    with pytest.raises(FrozenInstanceError):
        adapter.system_prompt_text = "changed"  # type: ignore[misc]
    assert "Frozen effective" not in repr(adapter)
    assert json.loads(adapter.payload_json)["format_version"] == 1


def test_placeholder_system_prompt_can_be_saved_but_is_not_stage_ready(
    tmp_path: Path,
) -> None:
    settings, path, db = adapter_inputs(tmp_path)
    placeholder = b"...\n"
    (settings.parent / "prompts/pi-system-v1.md").write_bytes(placeholder)
    path.write_text(
        path.read_text().replace(
            "212c2cd595c12aaf7ca2a4b6783b3f43f85ce077745c2a55f4f18d6c07b9e2d1",
            hashlib.sha256(placeholder).hexdigest(),
        )
    )
    saved = compile_config(settings, db)
    assert set(saved.adapter_slots.values()) == {"placeholder"}
    for stage in (StageName.BOUNDARY, StageName.VALUE):
        assert saved.stages[stage].status == "not_ready"
        assert "screening_adapter_prompt_placeholder" in saved.stages[stage].missing
    assert load_config_snapshot(db, saved.snapshot_id) == saved
