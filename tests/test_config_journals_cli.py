"""真实安装 CLI 的期刊配置与帮助行为。网络始终被拒绝。"""

from pathlib import Path

import pytest

from paper_radar.config import compile_config, load_config_snapshot, upgrade_database
from tests.config_journals_support import journal_inputs
from tests.config_test_support import run_cli


@pytest.mark.parametrize("command", ["check", "compile"])
def test_cli_reports_journals_without_revealing_materials(
    tmp_path: Path, command: str
) -> None:
    settings, database = journal_inputs(tmp_path)
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
    assert "期刊集合：configured" in result.stdout
    assert "boundary：ready" in result.stdout
    assert "value：ready" in result.stdout
    assert "read：not_ready" in result.stdout
    assert "同名期刊" not in result.stdout + result.stderr
    assert "2169-897X" not in result.stdout + result.stderr


@pytest.mark.parametrize(
    "args", [(), ("config",), ("config", "check"), ("config", "compile")]
)
def test_journals_help_has_no_file_or_database_io(
    tmp_path: Path, args: tuple[str, ...]
) -> None:
    result = run_cli(tmp_path, *args, "--help", help_only=True)
    assert result.returncode == 0, result.stderr
    if args == ("config",):
        assert "期刊" in result.stdout
        assert "ISSN" in result.stdout
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("command", ["check", "compile"])
@pytest.mark.parametrize("damage", ["conflict", "checksum", "version", "unknown"])
def test_cli_journal_failures_are_actionable_and_redacted(
    tmp_path: Path, command: str, damage: str
) -> None:
    settings, database = journal_inputs(tmp_path)
    path = settings.parent / "journals/journals-v1.yaml"
    contents = {
        "conflict": "version: journals-v1\njournals: ["
        "{issn_l: 1477870x, name: PRIVATE_MARKER, tier: normal},"
        "{issn_l: 1477-870X, name: PRIVATE_MARKER, tier: low}]\n",
        "checksum": "version: journals-v1\njournals: ["
        "{issn_l: 2169-8970, name: PRIVATE_MARKER, tier: normal}]\n",
        "version": "version: journals-v2\njournals: []\n",
        "unknown": "version: journals-v1\njournals: []\napi_key: PRIVATE_MARKER\n",
    }
    path.write_text(contents[damage])
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
    assert "journals" in result.stderr
    assert "请" in result.stderr
    assert "PRIVATE_MARKER" not in result.stdout + result.stderr
    assert "2169-8970" not in result.stdout + result.stderr
    assert "1477-870X" not in result.stdout + result.stderr
    assert "Traceback" not in result.stderr


def test_cli_repeated_compile_and_new_version_preserve_old_history(
    tmp_path: Path,
) -> None:
    settings, database = journal_inputs(tmp_path)
    saved = compile_config(settings, database)
    args = (
        "config",
        "compile",
        "--settings",
        str(settings),
        "--database",
        str(database),
    )
    for _ in range(2):
        result = run_cli(tmp_path, *args)
        assert result.returncode == 0, result.stderr
        assert saved.snapshot_id in result.stdout
    path = settings.parent / "journals/journals-v1.yaml"
    path.with_name("journals-v2.yaml").write_text(
        path.read_text()
        .replace("journals-v1", "journals-v2")
        .replace("preferred", "low")
    )
    settings.write_text(settings.read_text().replace("journals-v1", "journals-v2"))
    result = run_cli(tmp_path, *args)
    assert result.returncode == 0, result.stderr
    newer = compile_config(settings, database)
    assert newer.snapshot_id != saved.snapshot_id
    assert newer.snapshot_id in result.stdout
    assert load_config_snapshot(database, saved.snapshot_id) == saved


def test_committed_journals_example_registers_only_journal_facts(
    tmp_path: Path,
) -> None:
    settings = (
        Path(__file__).resolve().parents[1] / "examples/config/settings-journals.yaml"
    )
    database = tmp_path / "db.sqlite3"
    upgrade_database(database)
    result = run_cli(
        tmp_path,
        "config",
        "compile",
        "--settings",
        str(settings),
        "--database",
        str(database),
    )
    assert result.returncode == 0, result.stderr
    assert "期刊集合：configured" in result.stdout
    saved = compile_config(settings, database)
    assert len(saved.journals) == 4
    assert all(stage.status == "not_ready" for stage in saved.stages.values())
    assert load_config_snapshot(database, saved.snapshot_id) == saved
