"""摘录/解析隔离与规范顺序。未来算法只进入纯投影 fixture。"""

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import yaml

from paper_radar.config import (
    ConfigError,
    StageName,
    compare_config_snapshots,
    compile_config,
    diff_config_snapshots,
    project_config,
)
from tests.config_projection_support import full_inputs, new_yaml_version


@pytest.mark.parametrize("component", ["backend", "model_hash", "formula"])
def test_extraction_changes_affect_extraction_and_baseline_only(
    tmp_path: Path, component: str
) -> None:
    settings, database = full_inputs(tmp_path)
    before = compile_config(settings, database)
    # 合法版本化材料分别验证后端、模型字节和解析策略。
    if component == "backend":
        new_yaml_version(
            settings,
            "extraction",
            lambda c: c.update(pdf_backend="threaded_docling_parse"),
        )
    elif component == "model_hash":
        new_yaml_version(
            settings,
            "extraction",
            lambda c: c["models"]["layout"]["files"][0].update(sha256="1" * 64),
        )
    else:

        def disable_formula(c: dict[str, Any]) -> None:
            c["models"].pop("formula")
            c["policy"] = {"do_formula_enrichment": False}

        new_yaml_version(settings, "extraction", disable_formula)
    after = compile_config(settings, database)
    result = diff_config_snapshots(database, before.snapshot_id, after.snapshot_id)
    assert tuple(change.stage.value for change in result.projection_changes) == (
        "extraction",
    )
    assert result.calibration_changed


def test_trigger_set_order_is_canonical_and_has_only_a_suggestion_consumer(
    tmp_path: Path,
) -> None:
    settings, database = full_inputs(tmp_path)
    before = compile_config(settings, database)
    path = new_yaml_version(
        settings,
        "escalation",
        lambda c: c.update(reuse_escalation_research_values=[2, 3]),
    )
    after = compile_config(settings, database)
    result = diff_config_snapshots(database, before.snapshot_id, after.snapshot_id)
    assert tuple(change.stage.value for change in result.projection_changes) == (
        "suggestion",
    )
    assert result.calibration_changed
    path.with_name("escalation-v3.yaml").write_text(
        path.read_text()
        .replace("version: escalation-v2", "version: escalation-v3")
        .replace("- 2\n- 3", "- 3\n- 2")
    )
    settings.write_text(settings.read_text().replace("escalation-v2", "escalation-v3"))
    reordered = compile_config(settings, database)
    unchanged = diff_config_snapshots(
        database, after.snapshot_id, reordered.snapshot_id
    )
    assert unchanged.snapshot_changed and not unchanged.projection_changes
    assert not unchanged.calibration_changed


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("normalization_version", ("extraction",)),
        ("excerpt_selector_version", ("reuse",)),
        ("suggestion_rule_version", ("suggestion",)),
        ("chunking_version", ("read",)),
    ],
)
def test_future_algorithm_semantics_are_isolated_in_pure_fixtures(
    tmp_path: Path, field: str, expected: tuple[str, ...]
) -> None:
    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    group = {"normalization_version": "extraction", "chunking_version": "read"}.get(
        field, "escalation"
    )
    semantics = getattr(snapshot, group)
    # dataclass fixture 不经编译或登记。不向任何生产受控 enum 添加假 v2。
    future = replace(snapshot, **{group: replace(semantics, **{field: "fixture-v2"})})
    result = compare_config_snapshots(snapshot, future)
    assert tuple(change.stage.value for change in result.projection_changes) == expected
    assert result.calibration_changed == (field != "chunking_version")
    assert not result.identity_changes
    new_yaml_version(settings, group, lambda c: c.update({field: "fixture-v2"}))
    with pytest.raises(ConfigError):
        compile_config(settings, database)


def test_ordered_excerpt_priority_preserves_order_in_a_pure_fixture(
    tmp_path: Path,
) -> None:
    settings, database = full_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    assert snapshot.escalation is not None
    future = replace(
        snapshot,
        escalation=replace(
            snapshot.escalation, excerpt_priority=("methods", "availability")
        ),
    )
    result = compare_config_snapshots(snapshot, future)
    assert tuple(change.stage.value for change in result.projection_changes) == (
        "reuse",
    )
    assert result.calibration_changed
    assert json.loads(project_config(future).projections[StageName.REUSE].payload_json)[
        "components"
    ]["excerpt_priority"] == ["methods", "availability"]
    new_yaml_version(
        settings,
        "escalation",
        lambda c: c.update(excerpt_priority=["methods", "availability"]),
    )
    with pytest.raises(ConfigError):
        compile_config(settings, database)


def test_topic_and_model_file_sets_are_sorted_and_empty_differs_from_missing(
    tmp_path: Path,
) -> None:
    settings, database = full_inputs(tmp_path)
    source = settings.parent / "topics/topics-v1.yaml"
    content = yaml.safe_load(source.read_text())
    content["topics"][1]["enabled"] = True
    source.write_text(yaml.safe_dump(content))
    before = compile_config(settings, database)
    new_yaml_version(settings, "topics", lambda c: c["topics"].reverse())
    new_yaml_version(
        settings, "extraction", lambda c: c["models"]["layout"]["files"].reverse()
    )
    after = compile_config(settings, database)
    result = diff_config_snapshots(database, before.snapshot_id, after.snapshot_id)
    assert result.snapshot_changed and not result.projection_changes
    assert not result.calibration_changed


def test_empty_and_all_disabled_topics_share_semantics(tmp_path: Path) -> None:
    settings, database = full_inputs(tmp_path)
    source = settings.parent / "topics/topics-v1.yaml"
    content = yaml.safe_load(source.read_text())
    for topic in content["topics"]:
        topic["enabled"] = False
    source.write_text(yaml.safe_dump(content))
    before = compile_config(settings, database)
    new_yaml_version(settings, "topics", lambda c: c.update(topics=[]))
    after = compile_config(settings, database)
    unchanged = diff_config_snapshots(database, before.snapshot_id, after.snapshot_id)
    assert not unchanged.projection_changes and not unchanged.calibration_changed
    selectors = yaml.safe_load(settings.read_text())
    selectors["topics"] = None
    settings.write_text(yaml.safe_dump(selectors))
    missing = compile_config(settings, database)
    result = diff_config_snapshots(database, after.snapshot_id, missing.snapshot_id)
    assert tuple(change.stage.value for change in result.projection_changes) == (
        "value",
    )
    assert result.calibration_changed
    assert missing.stages[StageName.VALUE].missing == ("topics",)
