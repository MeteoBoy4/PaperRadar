"""并行切片组合:多个历史配置与非空共享内容闭包在新进程恢复。"""

import json
import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

from paper_radar.backup import create_backup, verify_backup
from paper_radar.config import compile_config
from paper_radar.storage.artifacts import ArtifactStore
from tests.config_projection_support import full_inputs
from tests.config_test_support import run_cli
from tests.restore_support import history_view


def test_multiple_snapshots_single_and_four_member_artifacts_survive_isolated_restore(
    tmp_path: Path,
) -> None:
    repo = Path(__file__).resolve().parents[1]
    fixture = json.loads(
        (repo / "tests/fixtures/a3_storage_recovery.json").read_bytes()
    )
    source = tmp_path / "source"
    settings, database = full_inputs(source)
    first = compile_config(settings, database)
    assert first.snapshot_id == fixture["first_snapshot_id"]
    profile = settings.parent / "profiles/profile-v1.yaml"
    profile.with_name("profile-v2.yaml").write_text(
        profile.read_text()
        .replace("version: profile-v1", "version: profile-v2")
        .replace("background: climate", "background: PRIVATE_A3_PROFILE"),
        encoding="utf-8",
    )
    settings.write_text(
        settings.read_text().replace("profile: profile-v1", "profile: profile-v2"),
        encoding="utf-8",
    )
    second = compile_config(settings, database)
    assert first.snapshot_id != second.snapshot_id
    data_root = source / "data"
    store = ArtifactStore(database, data_root)
    single = store.publish_single(
        "original_pdf", [fixture["members"]["document"].encode()]
    )
    extraction = store.publish_artifact(
        "extraction",
        {role: [text.encode()] for role, text in fixture["members"].items()},
    )
    assert len(extraction.members) == 4
    assert len({member.sha256 for member in extraction.members}) == 3
    assert single.members[0].sha256 in {member.sha256 for member in extraction.members}
    expected = history_view(database, data_root)
    assert len(expected["snapshots"]) == len(expected["artifacts"]) == 2
    expectation = tmp_path / "expected.json"
    expectation.write_text(json.dumps(expected), encoding="utf-8")
    backup = create_backup(database, data_root, tmp_path / "backups")
    assert len(backup.manifest.blobs) == 3
    assert verify_backup(backup.batch_dir) == backup
    source.rename(tmp_path / "source-unavailable")
    assert not database.exists() and not data_root.exists() and not settings.exists()
    restored = tmp_path / "restored"
    completed = run_cli(
        tmp_path, "restore", "verify", str(backup.batch_dir), "--target", str(restored)
    )
    assert completed.returncode == 0, completed.stderr
    target_db = restored / "database.sqlite3"
    listed = run_cli(
        tmp_path, "config", "snapshots", "list", "--database", str(target_db)
    )
    compared = run_cli(
        tmp_path,
        "config",
        "diff",
        first.snapshot_id,
        second.snapshot_id,
        "--database",
        str(target_db),
    )
    assert listed.returncode == compared.returncode == 0
    assert first.snapshot_id in listed.stdout and second.snapshot_id in listed.stdout
    replayed = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.restore_process.query",
            str(restored),
            str(expectation),
        ],
        cwd=tmp_path,
        env={
            "PATH": os.environ["PATH"],
            "PYTHONPATH": os.pathsep.join(
                (str(repo), str(repo / "tests/deny_network"))
            ),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert replayed.returncode == 0, replayed.stderr
    assert (
        "PRIVATE_"
        not in completed.stdout
        + completed.stderr
        + listed.stdout
        + listed.stderr
        + compared.stdout
        + compared.stderr
        + replayed.stdout
        + replayed.stderr
    )
    assert target_db.read_bytes()[18:20] == b"\x01\x01"
    upgraded = run_cli(tmp_path, "db", "upgrade", "--database", str(target_db))
    assert upgraded.returncode == 0, upgraded.stderr
    with closing(sqlite3.connect(target_db)) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone() == ("wal",)
    assert history_view(target_db, restored) == expected
    assert (backup.batch_dir / "database.sqlite3").read_bytes()[18:20] == b"\x01\x01"
