"""#23 的真实安装入口、中文帮助、退出码与只读承诺。"""

import json
import shutil
import sqlite3
from pathlib import Path

import pytest
import yaml

from paper_radar.config import compile_config
from tests.config_projection_support import empty_inputs, full_inputs, new_yaml_version
from tests.config_read_support import read_inputs
from tests.config_test_support import run_cli


def test_cli_reports_read_only_changes_without_calibration_changes(
    tmp_path: Path,
) -> None:
    settings, database = read_inputs(tmp_path)
    before = compile_config(settings, database)
    source = tmp_path / "prompts/reading/v1.md"
    (source.parent / "v2.md").write_text("PRIVATE_PROMPT_MARKER\n", encoding="utf-8")
    settings.write_text(settings.read_text().replace("  reading: v1", "  reading: v2"))
    after = compile_config(settings, database)
    args = (
        "config",
        "diff",
        before.snapshot_id,
        after.snapshot_id,
        "--database",
        str(database),
    )
    result = run_cli(tmp_path, *args)
    assert result.returncode == 0, result.stderr
    assert "prompt.reading" in result.stdout
    assert "v1" in result.stdout and "v2" in result.stdout
    assert "受影响投影：read" in result.stdout
    assert "是否涉及校准：否" in result.stdout
    assert "前基线" in result.stdout and "后基线" in result.stdout
    assert "PRIVATE_PROMPT_MARKER" not in result.stdout + result.stderr
    assert run_cli(tmp_path, *args).stdout == result.stdout


def test_cli_calibration_diff_succeeds_and_discloses_no_profile_or_prompt(
    tmp_path: Path,
) -> None:
    settings, database = full_inputs(tmp_path)
    selectors = yaml.safe_load(settings.read_text())
    selectors.pop("escalation")
    settings.write_text(yaml.safe_dump(selectors))
    before = compile_config(settings, database)
    selectors["escalation"] = "escalation-v1"
    settings.write_text(yaml.safe_dump(selectors))
    new_yaml_version(
        settings, "profile", lambda c: c.update(background="PRIVATE_PROFILE_MARKER")
    )
    after = compile_config(settings, database)
    payload = json.loads(after.payload_json)
    hashes = {entry["name"]: entry["raw_sha256"] for entry in payload["materials"]}
    for folder in ("config", "prompts", "contracts"):
        shutil.rmtree(tmp_path / folder)
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    original = database.read_bytes()
    result = run_cli(
        tmp_path,
        "config",
        "diff",
        before.snapshot_id,
        after.snapshot_id,
        "--database",
        str(database),
    )
    assert result.returncode == 0, result.stderr
    assert "是否涉及校准：是" in result.stdout
    assert "suggestion" in result.stdout and "未配置 → 已配置" in result.stdout
    assert hashes["profile"] in result.stdout and hashes["escalation"] in result.stdout
    for secret in (
        "PRIVATE_PROFILE_MARKER",
        "Boundary prompt",
        "Frozen effective Pi system prompt",
        "climate",
    ):
        assert secret not in result.stdout + result.stderr
    assert "minor" not in result.stdout and "major" not in result.stdout
    assert "calibration passed" not in result.stdout
    assert database.read_bytes() == original


def test_cli_identical_existing_id_has_no_difference(tmp_path: Path) -> None:
    settings, database = empty_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    result = run_cli(
        tmp_path,
        "config",
        "diff",
        snapshot.snapshot_id,
        snapshot.snapshot_id,
        "--database",
        str(database),
    )
    assert result.returncode == 0, result.stderr
    assert "无差异" in result.stdout and "受影响投影：无" in result.stdout
    assert "是否涉及校准：否" in result.stdout


@pytest.mark.parametrize(
    "kind",
    [
        "invalid_id",
        "uppercase_id",
        "missing_snapshot",
        "missing_database",
        "unknown_format",
        "damaged",
        "uninitialized",
        "future_revision",
    ],
)
def test_cli_errors_are_actionable_read_only_and_redacted(
    tmp_path: Path, kind: str
) -> None:
    settings, database = empty_inputs(tmp_path)
    snapshot = compile_config(settings, database)
    before_id = after_id = snapshot.snapshot_id
    if kind == "invalid_id":
        after_id = "PRIVATE_ID_MARKER"
    elif kind == "uppercase_id":
        after_id = after_id.upper()
    elif kind == "missing_snapshot":
        before_id = after_id = "0" * 64
    elif kind == "missing_database":
        database = tmp_path / "missing.sqlite3"
    else:
        with sqlite3.connect(database) as connection:
            if kind == "unknown_format":
                payload = json.loads(snapshot.payload_json)
                payload["format_version"] = 999
                connection.execute(
                    "UPDATE runtime_config_snapshots SET payload_json = ?",
                    (json.dumps(payload),),
                )
            elif kind == "damaged":
                connection.execute(
                    "UPDATE runtime_config_snapshots SET payload_json = ?",
                    ("PRIVATE_DAMAGE_MARKER",),
                )
            elif kind == "uninitialized":
                connection.execute("DROP TABLE alembic_version")
            else:
                connection.execute(
                    "UPDATE alembic_version SET version_num = 'PRIVATE_REVISION_MARKER'"
                )
        with sqlite3.connect(database) as connection:
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    original = database.read_bytes() if database.exists() else None
    result = run_cli(
        tmp_path, "config", "diff", before_id, after_id, "--database", str(database)
    )
    assert result.returncode == 2
    assert "配置比较失败" in result.stderr
    for secret in (
        "PRIVATE_ID_MARKER",
        "PRIVATE_DAMAGE_MARKER",
        "PRIVATE_REVISION_MARKER",
        "Traceback",
        "SELECT",
        "sqlalchemy",
    ):
        assert secret not in result.stdout + result.stderr
    assert (database.read_bytes() if database.exists() else None) == original


def test_diff_requires_an_explicit_database(tmp_path: Path) -> None:
    result = run_cli(tmp_path, "config", "diff", "0" * 64, "0" * 64)
    assert result.returncode == 2
    assert "必须显式提供 --database" in result.stderr
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "args",
    [
        ("0" * 64, "0" * 64, "--database", "missing.sqlite3", "PRIVATE_INPUT_MARKER"),
        (
            "0" * 64,
            "0" * 64,
            "--database",
            "missing.sqlite3",
            "--PRIVATE_OPTION_MARKER",
        ),
        ("0" * 64,),
        (),
        ("0" * 64, "0" * 64, "--database"),
    ],
)
def test_diff_parser_errors_are_chinese_and_never_echo_untrusted_input(
    tmp_path: Path, args: tuple[str, ...]
) -> None:
    result = run_cli(tmp_path, "config", "diff", *args)
    assert result.returncode == 2
    assert "配置比较参数错误" in result.stderr
    assert "paper-radar config diff --help" in result.stderr
    assert "PRIVATE_INPUT_MARKER" not in result.stdout + result.stderr
    assert "PRIVATE_OPTION_MARKER" not in result.stdout + result.stderr
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("args", [(), ("config",), ("config", "diff")])
def test_diff_help_works_with_all_external_io_denied(
    tmp_path: Path, args: tuple[str, ...]
) -> None:
    result = run_cli(tmp_path, *args, "--help", help_only=True)
    assert result.returncode == 0, result.stderr
    if args:
        assert "diff" in result.stdout
        assert "只读" in result.stdout and "数据库" in result.stdout
        assert "<before-id>" in result.stdout and "<after-id>" in result.stdout
    assert not list(tmp_path.iterdir())
