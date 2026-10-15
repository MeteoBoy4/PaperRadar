"""#27 真实安装入口: 发现、便捷比较与只读中文交互。"""

import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from paper_radar.config import compile_config
from tests.config_projection_support import empty_inputs, full_inputs, new_yaml_version
from tests.config_snapshot_support import (
    checkpoint,
    database_damage,
    insert_index_records,
)
from tests.config_test_support import run_cli


def test_list_empty_database_succeeds(tmp_path: Path) -> None:
    _, database = empty_inputs(tmp_path)
    result = run_cli(
        tmp_path, "config", "snapshots", "list", "--database", str(database)
    )
    assert result.returncode == 0, result.stderr
    assert "暂无已保存快照" in result.stdout


def test_cli_full_prefix_and_mixed_references_produce_identical_diff(
    tmp_path: Path,
) -> None:
    settings, database = full_inputs(tmp_path)
    before = compile_config(settings, database)
    new_yaml_version(
        settings, "profile", lambda c: c.update(background="PRIVATE_PROFILE_MARKER")
    )
    after = compile_config(settings, database)
    full = run_cli(
        tmp_path,
        "config",
        "diff",
        before.snapshot_id,
        after.snapshot_id,
        "--database",
        str(database),
    )
    assert full.returncode == 0, full.stderr
    assert "是否涉及校准：是" in full.stdout
    for before_ref, after_ref in (
        (before.snapshot_id[:8], after.snapshot_id[:8]),
        (before.snapshot_id, after.snapshot_id[:12]),
        (before.snapshot_id[:16], after.snapshot_id),
    ):
        short = run_cli(
            tmp_path,
            "config",
            "diff",
            before_ref,
            after_ref,
            "--database",
            str(database),
        )
        assert (short.returncode, short.stdout, short.stderr) == (
            full.returncode,
            full.stdout,
            full.stderr,
        )


def test_listing_displays_copyable_references_audit_metadata_and_no_content(
    tmp_path: Path,
) -> None:
    settings, database = full_inputs(tmp_path)
    saved = compile_config(settings, database)
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE runtime_config_snapshots SET created_at = ''")
    for folder in ("config", "prompts", "contracts"):
        shutil.rmtree(tmp_path / folder)
    checkpoint(database)
    original = database.read_bytes()
    result = run_cli(
        tmp_path, "config", "snapshots", "list", "--database", str(database)
    )
    assert result.returncode == 0, result.stderr
    assert saved.snapshot_id in result.stdout and saved.snapshot_id[:8] in result.stdout
    assert "未记录" in result.stdout and "未验证完整性" in result.stdout
    assert "profile.profile：profile-v1" in result.stdout
    assert "adapter.pi-rpc：pi-v1" in result.stdout
    for marker in ("climate", "Boundary prompt", "Frozen effective Pi system prompt"):
        assert marker not in result.stdout + result.stderr
    assert database.read_bytes() == original
    assert (
        run_cli(
            tmp_path, "config", "snapshots", "list", "--database", str(database)
        ).stdout
        == result.stdout
    )
    identical = run_cli(
        tmp_path,
        "config",
        "diff",
        saved.snapshot_id[:8],
        saved.snapshot_id[:16],
        "--database",
        str(database),
    )
    assert identical.returncode == 0, identical.stderr
    assert "无差异" in identical.stdout
    assert database.read_bytes() == original


@pytest.mark.parametrize(
    "damage", ["unknown_format", "payload", "material", "reference"]
)
def test_same_snapshot_different_prefixes_still_pass_through_integrity_validation(
    tmp_path: Path,
    damage: str,
) -> None:
    settings, database = full_inputs(tmp_path)
    saved = compile_config(settings, database)
    with sqlite3.connect(database) as connection:
        if damage == "unknown_format":
            payload = json.loads(saved.payload_json)
            payload["format_version"] = 999
            connection.execute(
                "UPDATE runtime_config_snapshots SET payload_json = ?",
                (json.dumps(payload),),
            )
        elif damage == "payload":
            connection.execute(
                "UPDATE runtime_config_snapshots SET payload_json = ?",
                ("PRIVATE_DAMAGE_MARKER",),
            )
        elif damage == "material":
            connection.execute(
                "UPDATE config_versions SET raw_content = ? WHERE kind = 'profile'",
                (b"PRIVATE_DAMAGE_MARKER",),
            )
        else:
            connection.execute(
                "DELETE FROM snapshot_version_refs WHERE kind = 'profile'"
            )
    checkpoint(database)
    original = database.read_bytes()
    result = run_cli(
        tmp_path,
        "config",
        "diff",
        saved.snapshot_id[:8],
        saved.snapshot_id[:16],
        "--database",
        str(database),
    )
    assert result.returncode == 2
    assert "配置比较失败" in result.stderr
    assert "PRIVATE_DAMAGE_MARKER" not in result.stderr + result.stdout
    assert database.read_bytes() == original


@pytest.mark.parametrize(
    "reference,reason",
    [
        ("12345678", "补充字符"),
        ("0" * 8, "未找到快照"),
        ("0" * 64, "未找到快照"),
        ("a" * 7, "8–63"),
        ("a" * 65, "8–63"),
        ("A" * 8, "8–63"),
        ("x" * 8, "8–63"),
        ("PRIVATE_INPUT_MARKER", "8–63"),
    ],
)
def test_reference_errors_are_read_only_and_actionable(
    tmp_path: Path, reference: str, reason: str
) -> None:
    _, database = empty_inputs(tmp_path)
    insert_index_records(
        database, [("12345678" + "a" * 56, ""), ("12345678" + "b" * 56, "")]
    )
    checkpoint(database)
    original = database.read_bytes()
    result = run_cli(
        tmp_path, "config", "diff", reference, "12345678a", "--database", str(database)
    )
    assert result.returncode == 2
    assert reason in result.stderr
    assert "PRIVATE_INPUT_MARKER" not in result.stderr + result.stdout
    assert database.read_bytes() == original


@pytest.mark.parametrize(
    "damage",
    [
        "missing_database",
        "uninitialized",
        "missing_revision",
        "old_revision",
        "future_revision",
        "missing_table",
    ],
)
def test_list_rejects_invalid_archives_without_repair(
    tmp_path: Path, damage: str
) -> None:
    _, database = empty_inputs(tmp_path)
    if damage == "missing_database":
        database = tmp_path / "missing.sqlite3"
    else:
        database_damage(database, damage)
    original = database.read_bytes() if database.exists() else None
    result = run_cli(
        tmp_path, "config", "snapshots", "list", "--database", str(database)
    )
    assert result.returncode == 2
    assert "快照列表失败" in result.stderr
    assert "PRIVATE_REVISION_MARKER" not in result.stderr
    assert (database.read_bytes() if database.exists() else None) == original


@pytest.mark.parametrize(
    "args",
    [
        (),
        ("--database",),
        ("--PRIVATE_OPTION_MARKER",),
        ("--database", "missing.sqlite3", "PRIVATE_INPUT_MARKER"),
    ],
)
def test_list_parser_errors_are_chinese_and_redacted(
    tmp_path: Path, args: tuple[str, ...]
) -> None:
    result = run_cli(tmp_path, "config", "snapshots", "list", *args)
    assert result.returncode == 2
    assert "快照列表参数错误" in result.stderr
    assert "必须显式提供 --database" in result.stderr
    assert "PRIVATE_INPUT_MARKER" not in result.stderr
    assert "PRIVATE_OPTION_MARKER" not in result.stderr
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "args",
    [
        (),
        ("config",),
        ("config", "snapshots"),
        ("config", "snapshots", "list"),
        ("config", "diff"),
    ],
)
def test_new_help_is_safe_with_all_external_io_denied(
    tmp_path: Path, args: tuple[str, ...]
) -> None:
    result = run_cli(tmp_path, *args, "--help", help_only=True)
    assert result.returncode == 0, result.stderr
    assert "快照" in result.stdout
    assert not list(tmp_path.iterdir())
