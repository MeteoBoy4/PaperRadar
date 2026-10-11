"""Pi 目标协议示例的离线编译、版本保护与历史回放。"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from paper_radar.config import (
    ConfigError,
    check_config,
    compile_config,
    load_config_snapshot,
    upgrade_database,
)
from paper_radar.config.compile import StageName
from paper_radar.config.schema import ModelProtocol, Models


@pytest.fixture
def example_inputs(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "examples"
    shutil.copytree(Path(__file__).resolve().parents[1] / "examples", root)
    database = tmp_path / "db.sqlite3"
    upgrade_database(database)
    return root, database


def test_prompt_only_example_compiles_and_replays_without_source_files(
    example_inputs: tuple[Path, Path],
) -> None:
    root, database = example_inputs
    settings = root / "config/settings-pi.yaml"
    checked = check_config(settings, database)
    for stage in (
        StageName.BOUNDARY,
        StageName.VALUE,
        StageName.REUSE,
        StageName.SUGGESTION,
    ):
        assert checked.stages[stage].status == "ready"
    assert checked.stages[StageName.READ].status == "not_ready"
    assert checked.stages[StageName.EXTRACTION].status == "not_ready"

    payload = json.loads(checked.payload_json)
    entry = next(item for item in payload["materials"] if item["kind"] == "models")
    assert entry["version"] == "models-pi-v1"
    models = Models.model_validate(entry["config"])
    assert models.screening is not None
    assert models.reuse_assessment is not None
    assert models.screening.protocol is ModelProtocol.PROMPT_ONLY
    assert models.reuse_assessment.protocol is ModelProtocol.PROMPT_ONLY
    assert models.reading is None

    saved = compile_config(settings, database)
    assert saved == checked
    assert compile_config(settings, database) == saved
    shutil.rmtree(root)
    assert load_config_snapshot(database, saved.snapshot_id) == saved


@pytest.mark.parametrize("protocol", ["json_schema", "json_object"])
def test_prompt_only_selection_preserves_legacy_protocol_history(
    example_inputs: tuple[Path, Path], protocol: str
) -> None:
    root, database = example_inputs
    legacy_settings = root / "config/settings-value.yaml"
    legacy_models = root / "config/models/models-v1.yaml"
    legacy_raw = legacy_models.read_text().replace("json_schema", protocol)
    legacy_models.write_text(legacy_raw, encoding="utf-8")
    legacy = compile_config(legacy_settings, database)

    current = compile_config(root / "config/settings-pi.yaml", database)
    assert current.snapshot_id != legacy.snapshot_id
    assert legacy_models.read_text() == legacy_raw
    assert load_config_snapshot(database, legacy.snapshot_id) == legacy

    legacy_models.write_text(
        legacy_raw.replace(protocol, "prompt_only"), encoding="utf-8"
    )
    with pytest.raises(ConfigError, match="声明版本已登记不同字节"):
        compile_config(legacy_settings, database)
    assert load_config_snapshot(database, legacy.snapshot_id) == legacy
    assert load_config_snapshot(database, current.snapshot_id) == current
