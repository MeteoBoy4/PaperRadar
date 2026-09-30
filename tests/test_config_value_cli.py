"""A2-03 真实安装 CLI 的就绪、版本与脱敏行为。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from tests.test_config_cli import _run
from tests.test_config_value import _value_inputs


@pytest.mark.parametrize(
    "topics",
    [
        "[]",
        "[{id: monsoon, name: N, description: D, enabled: false}]",
        "[{id: monsoon, name: N, description: D, enabled: true}]",
    ],
)
def test_cli_checks_and_saves_configured_topics(tmp_path: Path, topics: str) -> None:
    settings, db = _value_inputs(tmp_path, topics)
    args = ("--settings", str(settings), "--database", str(db))
    checked = _run(tmp_path, "config", "check", *args)
    assert checked.returncode == 0, checked.stderr
    assert "value：ready" in checked.stdout
    assert "boundary：ready" in checked.stdout
    assert "主题集合：configured" in checked.stdout
    with sqlite3.connect(db) as connection:
        assert connection.execute(
            "SELECT count(*) FROM config_versions"
        ).fetchone() == (0,)
    saved = _run(tmp_path, "config", "compile", *args)
    assert saved.returncode == 0, saved.stderr
    assert saved.stdout == checked.stdout


def test_cli_reports_missing_topics_and_independent_value_readiness(
    tmp_path: Path,
) -> None:
    settings, db = _value_inputs(tmp_path)
    args = ("--settings", str(settings), "--database", str(db))
    original = settings.read_text()
    settings.write_text(original.replace("topics: topics-v1\n", ""))
    missing = _run(tmp_path, "config", "check", *args)
    assert missing.returncode == 0, missing.stderr
    assert "主题集合：unconfigured" in missing.stdout
    assert "value：not_ready；缺项：topics" in missing.stdout
    assert "boundary：ready" in missing.stdout
    settings.write_text(original.replace("  boundary: v1\n", ""))
    ready = _run(tmp_path, "config", "check", *args)
    assert ready.returncode == 0, ready.stderr
    assert "value：ready" in ready.stdout
    assert "boundary：not_ready" in ready.stdout


def test_cli_topic_error_is_sanitized_and_new_version_preserves_old_snapshot(
    tmp_path: Path,
) -> None:
    settings, db = _value_inputs(tmp_path)
    args = ("--settings", str(settings), "--database", str(db))
    saved = _run(tmp_path, "config", "compile", *args)
    assert saved.returncode == 0, saved.stderr
    topics = tmp_path / "config/topics/topics-v1.yaml"
    original = topics.read_bytes()
    topics.write_bytes(original + b"api_key: secret-marker\n")
    invalid = _run(tmp_path, "config", "compile", *args)
    assert invalid.returncode == 2
    assert "topics.api_key" in invalid.stderr
    assert "secret-marker" not in invalid.stderr + invalid.stdout
    topics.write_bytes(original + b"# revised\n")
    conflict = _run(tmp_path, "config", "compile", *args)
    assert conflict.returncode == 2
    assert "声明版本已登记不同字节" in conflict.stderr
    newer = topics.parent / "topics-v2.yaml"
    newer.write_bytes(topics.read_bytes().replace(b"topics-v1", b"topics-v2"))
    settings.write_text(
        settings.read_text().replace("topics: topics-v1", "topics: topics-v2")
    )
    result = _run(tmp_path, "config", "compile", *args)
    assert result.returncode == 0, result.stderr
    assert result.stdout != saved.stdout
    with sqlite3.connect(db) as connection:
        assert connection.execute(
            "SELECT count(*) FROM runtime_config_snapshots"
        ).fetchone() == (2,)


@pytest.mark.parametrize(
    "args",
    [
        ("config", "--help"),
        ("config", "check", "--help"),
        ("config", "compile", "--help"),
    ],
)
def test_value_help_has_no_file_database_or_network_side_effects(
    tmp_path: Path, args: tuple[str, ...]
) -> None:
    result = _run(tmp_path, *args, help_only=True)
    assert result.returncode == 0, result.stderr
    assert "示例" in result.stdout
    assert not list(tmp_path.iterdir())
