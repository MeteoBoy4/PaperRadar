"""A2-01 已安装 CLI、中文帮助与副作用。"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest


def _run(
    tmp_path: Path, *args: str, help_only: bool = False
) -> subprocess.CompletedProcess[str]:
    sentinel = "deny_external_io" if help_only else "deny_network"
    env = {
        "PATH": os.environ["PATH"],
        "PYTHONPATH": str(Path(__file__).parent / sentinel),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
    }
    return subprocess.run(
        [str(Path(sys.executable).with_name("paper-radar")), *args],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


@pytest.mark.parametrize(
    "args",
    [
        ("--help",),
        ("db", "--help"),
        ("db", "upgrade", "--help"),
        ("config", "--help"),
        ("config", "check", "--help"),
        ("config", "compile", "--help"),
    ],
)
def test_help_does_not_touch_database_or_network(
    tmp_path: Path, args: tuple[str, ...]
) -> None:
    result = _run(tmp_path, *args, help_only=True)
    assert result.returncode == 0, result.stderr
    assert "示例" in result.stdout
    assert not list(tmp_path.iterdir())


def test_installed_cli_upgrade_check_compile_from_other_directory(
    tmp_path: Path,
) -> None:
    folder = tmp_path / "config"
    (folder / "profiles").mkdir(parents=True)
    settings = folder / "settings.yaml"
    settings.write_text("profile: profile-v1\n", encoding="utf-8")
    (folder / "profiles/profile-v1.yaml").write_text(
        "version: profile-v1\nbackground: ...\n", encoding="utf-8"
    )
    db = tmp_path / "db.sqlite3"

    missing = _run(
        tmp_path, "config", "check", "--settings", str(settings), "--database", str(db)
    )
    assert missing.returncode == 2
    assert "数据库不存在" in missing.stderr
    assert not db.exists()
    upgraded = _run(tmp_path, "db", "upgrade", "--database", str(db))
    assert upgraded.returncode == 0, upgraded.stderr
    checked = _run(
        tmp_path, "config", "check", "--settings", str(settings), "--database", str(db)
    )
    assert checked.returncode == 0, checked.stderr
    assert "placeholder" in checked.stdout
    saved = _run(
        tmp_path,
        "config",
        "compile",
        "--settings",
        str(settings),
        "--database",
        str(db),
    )
    assert saved.returncode == 0, saved.stderr
    assert "快照身份" in saved.stdout


def test_cli_rejects_secret_without_echoing_it(tmp_path: Path) -> None:
    db = tmp_path / "db.sqlite3"
    assert _run(tmp_path, "db", "upgrade", "--database", str(db)).returncode == 0
    settings = tmp_path / "settings.yaml"
    settings.write_text("api_key: very-secret-value\n", encoding="utf-8")
    result = _run(
        tmp_path,
        "config",
        "compile",
        "--settings",
        str(settings),
        "--database",
        str(db),
    )
    assert result.returncode == 2
    assert "settings.api_key" in result.stderr
    assert "very-secret-value" not in result.stderr


def test_existing_uninitialized_database_returns_chinese_exit_two(
    tmp_path: Path,
) -> None:
    db = tmp_path / "uninitialized.sqlite3"
    with sqlite3.connect(db):
        pass
    settings = tmp_path / "settings.yaml"
    settings.write_text("profile: null\n", encoding="utf-8")
    result = _run(
        tmp_path,
        "config",
        "check",
        "--settings",
        str(settings),
        "--database",
        str(db),
    )
    assert result.returncode == 2
    assert "数据库未初始化" in result.stderr
    with sqlite3.connect(db) as connection:
        assert connection.execute("SELECT name FROM sqlite_master").fetchall() == []
