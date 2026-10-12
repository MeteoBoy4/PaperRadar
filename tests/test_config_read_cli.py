"""真实 CLI 的 Read 配置缺项、版本切换与脱敏帮助。"""

from pathlib import Path

import pytest

from paper_radar.config import compile_config, load_config_snapshot, upgrade_database
from tests.config_read_support import read_inputs
from tests.config_test_support import run_cli


@pytest.mark.parametrize(
    ("model", "status", "reason"),
    [
        ("null", "unconfigured", "read_model"),
        (
            "{provider: provider-a, model: REQUIRED_FOR_READ, protocol: prompt_only}",
            "placeholder",
            "read_model_placeholder",
        ),
        (
            "{provider: provider-a, model: read-model, protocol: prompt_only}",
            "configured",
            None,
        ),
    ],
)
@pytest.mark.parametrize("command", ["check", "compile"])
def test_cli_reports_read_model_state_without_claiming_read_ready(
    tmp_path: Path, model: str, status: str, reason: str | None, command: str
) -> None:
    settings, db = read_inputs(tmp_path)
    path = settings.parent / "models/models-v1.yaml"
    path.write_text(path.read_text().split("reading:")[0] + f"reading: {model}\n")
    result = run_cli(
        tmp_path, "config", command, "--settings", str(settings), "--database", str(db)
    )
    assert result.returncode == 0, result.stderr
    assert f"models.reading：{status}" in result.stdout
    assert "read：not_ready" in result.stdout
    assert "read_contract" in result.stdout
    assert "boundary：ready" in result.stdout
    if reason:
        assert reason in result.stdout
    assert "Synthetic Read business prompt" not in result.stdout + result.stderr


def test_cli_compiles_new_read_version_and_old_materials_remain_readable(
    tmp_path: Path,
) -> None:
    settings, db = read_inputs(tmp_path)
    saved = compile_config(settings, db)
    (tmp_path / "prompts/reading/v2.md").write_bytes(b"New private Read prompt\n")
    settings.write_text(settings.read_text().replace("  reading: v1", "  reading: v2"))
    result = run_cli(
        tmp_path,
        "config",
        "compile",
        "--settings",
        str(settings),
        "--database",
        str(db),
    )
    assert result.returncode == 0, result.stderr
    assert saved.snapshot_id not in result.stdout
    assert "New private Read prompt" not in result.stdout + result.stderr
    assert "read_contract" in result.stdout
    assert load_config_snapshot(db, saved.snapshot_id) == saved


def test_committed_read_example_reports_only_missing_authoritative_contract(
    tmp_path: Path,
) -> None:
    settings = (
        Path(__file__).resolve().parents[1] / "examples/config/settings-read.yaml"
    )
    db = tmp_path / "db.sqlite3"
    upgrade_database(db)
    result = run_cli(
        tmp_path,
        "config",
        "compile",
        "--settings",
        str(settings),
        "--database",
        str(db),
    )
    assert result.returncode == 0, result.stderr
    assert "read：not_ready；缺项：read_contract" in result.stdout
    assert "boundary：ready" in result.stdout


@pytest.mark.parametrize("command", ["check", "compile"])
@pytest.mark.parametrize("selection", ["read", "prompt", "contract"])
def test_cli_read_errors_are_actionable_without_exposing_input(
    tmp_path: Path, command: str, selection: str
) -> None:
    settings, db = read_inputs(tmp_path)
    if selection == "read":
        (settings.parent / "read/read-v1.yaml").write_text(
            "version: read-v1\nchunking_version: PRIVATE_MARKER\n"
        )
        field = "read.chunking_version"
    elif selection == "prompt":
        (tmp_path / "prompts/reading/v1.md").write_bytes(b"\xffPRIVATE_MARKER")
        field = "prompts.reading"
    else:
        settings.write_text("contracts:\n  reading: PRIVATE_MARKER\n")
        field = "settings.contracts.reading"
    result = run_cli(
        tmp_path, "config", command, "--settings", str(settings), "--database", str(db)
    )
    assert result.returncode == 2
    assert field in result.stderr
    assert "请" in result.stderr
    assert "PRIVATE_MARKER" not in result.stdout + result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize(
    "args", [(), ("config",), ("config", "check"), ("config", "compile")]
)
def test_help_with_read_support_has_no_external_io(
    tmp_path: Path, args: tuple[str, ...]
) -> None:
    result = run_cli(tmp_path, *args, "--help", help_only=True)
    assert result.returncode == 0, result.stderr
    if args == ("config",):
        assert "Read" in result.stdout
        assert "chunking" in result.stdout
        assert "权威" in result.stdout
    assert not list(tmp_path.iterdir())
