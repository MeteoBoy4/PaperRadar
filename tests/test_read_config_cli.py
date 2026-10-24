"""Read 配置完整性和历史差异的真实中文 CLI。"""

from pathlib import Path

import pytest

from paper_radar.config import compile_config, upgrade_database
from tests.config_test_support import run_cli
from tests.read_config_support import read_contract_inputs


@pytest.mark.parametrize("command", ["check", "compile"])
def test_ready_read_example_reports_configuration_completeness(
    tmp_path: Path, command: str
) -> None:
    settings = (
        Path(__file__).resolve().parents[1] / "examples/config/settings-read-ready.yaml"
    )
    database = tmp_path / "database.sqlite3"
    upgrade_database(database)
    result = run_cli(
        tmp_path,
        "config",
        command,
        "--settings",
        str(settings),
        "--database",
        str(database),
    )
    assert result.returncode == 0, result.stderr
    assert "read：ready；缺项：" in result.stdout
    assert "adapters.reading：configured" in result.stdout
    assert "配置完整性不证明 Pi 执行就绪、校准通过或自动精读资格。" in result.stdout
    assert "Synthetic" not in result.stdout + result.stderr


def test_cli_diff_reports_read_contract_materials_and_read_only_semantics(
    tmp_path: Path,
) -> None:
    settings, database = read_contract_inputs(tmp_path)
    selected = settings.read_text()
    settings.write_text(selected.replace("  read: v1\n", ""))
    old = compile_config(settings, database)
    settings.write_text(selected)
    new = compile_config(settings, database)
    result = run_cli(
        tmp_path,
        "config",
        "diff",
        old.snapshot_id,
        new.snapshot_id,
        "--database",
        str(database),
    )
    assert result.returncode == 0, result.stderr
    assert "contract_schema.read" in result.stdout
    assert "contract_manifest.read" in result.stdout
    assert "受影响投影：read" in result.stdout
    assert "是否涉及校准：否" in result.stdout
    assert "Synthetic Read business prompt" not in result.stdout + result.stderr


@pytest.mark.parametrize("command", ["check", "compile"])
def test_cli_missing_selected_read_contract_returns_controlled_guidance(
    tmp_path: Path, command: str
) -> None:
    settings, database = read_contract_inputs(tmp_path)
    (tmp_path / "contracts/read/read/v1/manifest.json").unlink()
    result = run_cli(
        tmp_path,
        "config",
        command,
        "--settings",
        str(settings),
        "--database",
        str(database),
    )
    assert result.returncode == 2
    assert "contracts.read：missing_snapshot" in result.stderr
    assert "请" in result.stderr
    assert "Traceback" not in result.stderr
