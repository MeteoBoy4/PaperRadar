"""B-E16 独立 D1:真实 OS worker;仅自建 /tmp 合成,不是 CI/现场结论。"""

import json
from pathlib import Path

from tests.replay_support import cli, replay_args, restored_demo


def test_nested_restore_is_isolated_portable_and_repeatable(tmp_path: Path) -> None:
    restored, originals = restored_demo(tmp_path)
    before = (restored / "contents/database.sqlite3").read_bytes()
    first = cli(*replay_args(restored, originals))
    assert first.returncode == 0, first.stdout + first.stderr
    summary = json.loads(first.stdout)
    assert summary["isolation"] == "verified"
    assert summary["originals_denied"] == 6
    assert summary["descendant"] == "verified"
    assert summary["sockets_denied"] == 3
    assert summary["direct_connect_denied"] is True
    assert summary["reports"] == summary["analyses"] == summary["exposures"] == 0
    moved = restored.with_name("moved-session")
    restored.rename(moved)
    second = cli(*replay_args(moved, originals))
    assert second.returncode == 0, second.stdout + second.stderr
    assert json.loads(second.stdout) == summary
    assert (moved / "contents/database.sqlite3").read_bytes() == before
    assert not list(moved.rglob("*wal")) and not list(moved.rglob("*shm"))
    assert not (moved / "logs").exists()
    assert "PRIVATE_SYNTHETIC_CONTENT" not in first.stdout + first.stderr
    assert str(tmp_path) not in first.stdout + first.stderr


def test_replay_does_not_permanently_forbid_explicit_working_copy_upgrade(
    tmp_path: Path,
) -> None:
    import sqlite3

    restored, originals = restored_demo(tmp_path)
    result = cli(*replay_args(restored, originals))
    assert result.returncode == 0, result.stdout + result.stderr
    database = restored / "contents/database.sqlite3"
    upgraded = cli("db", "upgrade", "--database", str(database))
    assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone() == ("wal",)
