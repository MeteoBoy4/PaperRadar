"""models-v2 的公开编译/回放与阶段消费者。"""

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from paper_radar.config import (
    ConfigError,
    StageName,
    compile_config,
    load_config_snapshot,
    project_config,
)
from tests.config_adapter_support import adapter_inputs


def v2_inputs(root: Path, slot: dict[str, object]) -> tuple[Path, Path]:
    settings, adapter, database = adapter_inputs(root)
    adapter.write_text(adapter.read_text().replace("1.1.0", "1.4.0"))
    models = settings.parent / "models/models-v1.yaml"
    content = yaml.safe_load(models.read_text())
    content["format_version"] = 2
    for name in ("screening", "reuse_assessment", "reading"):
        if content[name] is not None:
            content[name].pop("temperature", None)
            content[name].pop("top_p", None)
            content[name].update(slot)
    models.write_text(yaml.safe_dump(content))
    return settings, database


def test_provider_default_roundtrips_without_invented_parameters(
    tmp_path: Path,
) -> None:
    settings, database = v2_inputs(tmp_path, {"sampling": "provider_default"})
    snapshot = compile_config(settings, database)
    assert load_config_snapshot(database, snapshot.snapshot_id) == snapshot
    model = json.loads(
        project_config(snapshot).projections[StageName.BOUNDARY].payload_json
    )["components"]["model"]
    assert model["sampling"] == "provider_default"
    assert "temperature" not in model and "top_p" not in model


@pytest.mark.parametrize(
    "slot",
    [
        {},
        {"sampling": "unknown"},
        {"sampling": "explicit"},
        {"sampling": "explicit", "temperature": 0.2},
        {"sampling": "explicit", "temperature": 0.2, "top_p": None},
        {"sampling": "explicit", "temperature": -1, "top_p": 1.0},
        {"sampling": "provider_default", "temperature": 0.0},
        {"sampling": "provider_default", "temperature": None},
        {"sampling": "provider_default", "top_p": 1.0},
        {"sampling": "provider_default", "extra": "sensitive-sentinel"},
    ],
)
def test_invalid_v2_never_falls_back_to_legacy(
    tmp_path: Path, slot: dict[str, object]
) -> None:
    settings, database = v2_inputs(tmp_path, slot)
    with pytest.raises(ConfigError, match=r"models.screening"):
        compile_config(settings, database)


@pytest.mark.parametrize("marker", [None, True, 2.0, 1, "2"])
def test_format_marker_requires_strict_integer_two(
    tmp_path: Path, marker: object
) -> None:
    settings, database = v2_inputs(tmp_path, {"sampling": "provider_default"})
    path = settings.parent / "models/models-v1.yaml"
    content = yaml.safe_load(path.read_text())
    content["format_version"] = marker
    path.write_text(yaml.safe_dump(content))
    with pytest.raises(ConfigError, match=r"models.format_version"):
        compile_config(settings, database)


def test_explicit_v2_compiles_both_parameters(tmp_path: Path) -> None:
    settings, database = v2_inputs(
        tmp_path, {"sampling": "explicit", "temperature": 0.3, "top_p": 0.7}
    )
    snapshot = compile_config(settings, database)
    model = json.loads(
        project_config(snapshot).projections[StageName.BOUNDARY].payload_json
    )["components"]["model"]
    assert model["sampling"] == "explicit"
    assert (model["temperature"], model["top_p"]) == (0.3, 0.7)


@pytest.mark.parametrize(
    ("slot", "expected", "calibration"),
    [
        ("screening", ("boundary", "value"), True),
        ("reuse_assessment", ("reuse",), True),
        ("reading", ("read",), False),
    ],
)
def test_sampling_changes_only_actual_consumers(
    tmp_path: Path, slot: str, expected: tuple[str, ...], calibration: bool
) -> None:
    from paper_radar.config import diff_config_snapshots
    from tests.config_projection_support import full_inputs, new_yaml_version

    settings, database = full_inputs(tmp_path)
    path = settings.parent / "models/models-v1.yaml"
    content = yaml.safe_load(path.read_text())
    content["format_version"] = 2
    for name in ("screening", "reuse_assessment", "reading"):
        content[name].update(sampling="explicit", temperature=0.0, top_p=1.0)
    path.write_text(yaml.safe_dump(content))
    before = compile_config(settings, database)

    def use_default(config: dict[str, Any]) -> None:
        config[slot]["sampling"] = "provider_default"
        del config[slot]["temperature"], config[slot]["top_p"]

    new_yaml_version(settings, "models", use_default)
    after = compile_config(settings, database)
    diff = diff_config_snapshots(database, before.snapshot_id, after.snapshot_id)
    assert tuple(item.stage.value for item in diff.projection_changes) == expected
    assert diff.calibration_changed is calibration
