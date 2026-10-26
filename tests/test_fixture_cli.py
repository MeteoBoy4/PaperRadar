"""公共 fixture CLI 的登记和只读路径。"""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from paper_radar.cli import app
from paper_radar.storage.database import upgrade_database
from tests.fixture_registry_support import declaration_bytes


def test_cli_register_check_list_show_and_missing_source(tmp_path: Path) -> None:
    database = tmp_path / "facts.sqlite3"
    upgrade_database(database)
    source = tmp_path / "history.json"
    source.write_bytes(declaration_bytes())
    runner = CliRunner()
    common = ["--database", str(database), "--json"]
    registered = runner.invoke(
        app,
        [
            "fixture",
            "register",
            str(source),
            "--data-root",
            str(tmp_path / "data"),
            *common,
        ],
    )
    assert registered.exit_code == 0, registered.output
    record = json.loads(registered.output)["entries"][0]
    checked = runner.invoke(app, ["fixture", "check", str(source), *common])
    assert checked.exit_code == 0
    assert json.loads(checked.output)["status"] == "byte_verified"
    source.unlink()
    missing = runner.invoke(app, ["fixture", "check", str(source), *common])
    assert missing.exit_code == 1
    assert json.loads(missing.output)["status"] == "source_missing"
    listing = runner.invoke(app, ["fixture", "list", *common])
    assert listing.exit_code == 0
    assert json.loads(listing.output)[0]["record_id"] == record["record_id"]
    shown = runner.invoke(app, ["fixture", "show", record["record_id"], *common])
    assert shown.exit_code == 0
    assert json.loads(shown.output)["entry"]["expectations"]["publisher_count"] == 77


@pytest.mark.parametrize("command", [[], ["register"], ["check"], ["list"], ["show"]])
def test_fixture_help_has_no_business_side_effects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: list[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ["fixture", *command, "--help"])
    assert result.exit_code == 0
    assert "副作用" in result.output
    assert "示例" in result.output
    assert list(tmp_path.iterdir()) == []


def test_read_only_cli_never_creates_missing_database(tmp_path: Path) -> None:
    database = tmp_path / "missing.sqlite3"
    result = CliRunner().invoke(app, ["fixture", "list", "--database", str(database)])
    assert result.exit_code == 1
    assert "db upgrade" in result.output
    assert not database.exists()
