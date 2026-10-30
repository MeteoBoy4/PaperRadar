"""doctor 的独立公共 CLI 证据。不加入历史固定分母。"""

from pathlib import Path

from typer.testing import CliRunner

from paper_radar.cli import app
from paper_radar.storage.database import upgrade_database


def test_basic_current_database_passes_readonly(tmp_path: Path) -> None:
    database = tmp_path / "current.sqlite3"
    upgrade_database(database)
    before = database.read_bytes()
    result = CliRunner().invoke(
        app, ["doctor", "--scope", "basic", "--database", str(database)]
    )
    assert result.exit_code == 0, result.output
    assert "scope=basic result=passed" in result.output
    assert "check=database result=passed reason=current_revision" in result.output
    assert "0 不代表任何阶段可运行。" in result.output
    assert database.read_bytes() == before


def test_config_missing_stages_passes_without_persisting_snapshot(
    tmp_path: Path,
) -> None:
    database = tmp_path / "current.sqlite3"
    upgrade_database(database)
    settings = tmp_path / "settings.yaml"
    settings.write_text("profile: null\n")
    result = CliRunner().invoke(
        app,
        [
            "doctor",
            "--scope",
            "config",
            "--database",
            str(database),
            "--settings",
            str(settings),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "scope=config result=passed" in result.output
    for stage in ("boundary", "value", "reuse", "extraction", "read", "suggestion"):
        assert f"stage={stage} result=missing reason=" in result.output
    assert "Profile/模型未配置，不能校准" in result.output
    assert "0 不代表任何阶段可运行。" in result.output
    import sqlite3

    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT count(*) FROM runtime_config_snapshots"
        ).fetchone() == (0,)


def test_missing_database_category_uses_controlled_state(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app, ["doctor", "--scope", "basic", "--database", str(tmp_path / "missing")]
    )
    assert result.exit_code == 2
    assert (
        "category=basic 基础工程 readiness result=missing reason=database_missing"
        in result.output
    )
    assert "check=database result=missing reason=database_missing" in result.output
    assert not tuple(tmp_path.iterdir())


def test_basic_reports_unselected_stage_configuration(tmp_path: Path) -> None:
    database = tmp_path / "current.sqlite3"
    upgrade_database(database)
    result = CliRunner().invoke(
        app, ["doctor", "--scope", "basic", "--database", str(database)]
    )
    assert result.exit_code == 0
    for stage in ("boundary", "value", "reuse", "extraction", "read", "suggestion"):
        assert (
            f"stage={stage} result=missing reason=configuration_unselected"
            in result.stdout
        )


def test_invalid_selection_keeps_basic_passed(tmp_path: Path) -> None:
    database = tmp_path / "current.sqlite3"
    upgrade_database(database)
    result = CliRunner().invoke(
        app,
        [
            "doctor",
            "--scope",
            "config",
            "--database",
            str(database),
            "--settings",
            str(tmp_path / "absent.yaml"),
        ],
    )
    assert result.exit_code == 2
    assert "scope=config result=failed" in result.stdout
    assert (
        "category=basic 基础工程 readiness result=passed reason=required_checks_passed"
        in result.stdout
    )
    assert (
        "check=selection result=invalid reason=selected_file_unreadable"
        in result.stdout
    )


def test_outbound_categories_follow_stage_data_boundary(tmp_path: Path) -> None:
    from tests.config_test_support import boundary_inputs

    settings, database = boundary_inputs(tmp_path)
    result = CliRunner().invoke(
        app,
        [
            "doctor",
            "--scope",
            "config",
            "--database",
            str(database),
            "--settings",
            str(settings),
        ],
    )
    assert result.exit_code == 0
    assert "实际执行时，以下数据会离开本机" in result.stdout
    lines = {
        line.split()[0]: line
        for line in result.stdout.splitlines()
        if line.startswith("outbound_stage=")
    }
    assert (
        "外发数据类别=Profile,合法结构化来源或正文的 availability/methods/data 摘录"
        in lines["outbound_stage=reuse"]
    )
    assert (
        "外发数据类别=Profile,论文元数据,合法正文提取物" in lines["outbound_stage=read"]
    )


def test_database_directory_is_invalid_not_missing(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app, ["doctor", "--scope", "basic", "--database", str(tmp_path)]
    )
    assert result.exit_code == 2
    assert "check=database result=invalid reason=database_unreadable" in result.stdout
