"""恢复后的独立字节、可重定位闭包和历史回放。"""

from pathlib import Path

import pytest

from paper_radar.backup import create_backup, restore_backup
from paper_radar.storage.artifacts import ArtifactStore
from tests.backup_support import populated, tree


def test_restore_publishes_an_independent_complete_private_copy(tmp_path: Path) -> None:
    database, data_root, _ = populated(tmp_path / "source")
    batch = create_backup(database, data_root, tmp_path / "backups")
    before = tree(batch.batch_dir)
    target = tmp_path / "restored"
    result = restore_backup(batch.batch_dir, target)
    assert result.target_dir == target.resolve()
    assert result.manifest_sha256 == batch.manifest_sha256
    assert tree(target) == before
    assert tree(batch.batch_dir) == before
    store = ArtifactStore(target / "database.sqlite3", target)
    for artifact in store.list_artifacts():
        assert store.read_artifact(artifact.artifact_id)
    for relative in before:
        copied = target / relative
        if copied.is_file():
            assert copied.stat().st_ino != (batch.batch_dir / relative).stat().st_ino


@pytest.mark.parametrize("existing", [False, True])
def test_restore_accepts_missing_or_empty_target_and_rejects_missing_parent(
    tmp_path: Path, existing: bool
) -> None:
    from paper_radar.backup import RestoreError, RestoreReason

    database, data_root, _ = populated(tmp_path / "source")
    batch = create_backup(database, data_root, tmp_path / "backups")
    target = tmp_path / "restored"
    if existing:
        target.mkdir()
    restored = restore_backup(batch.batch_dir, target)
    assert restored.target_dir.stat().st_mode & 0o777 == 0o700
    assert all(p.stat().st_mode & 0o077 == 0 for p in target.rglob("*") if p.is_dir())
    with pytest.raises(RestoreError) as failure:
        restore_backup(batch.batch_dir, tmp_path / "missing/target")
    assert failure.value.reason == RestoreReason.PARENT_UNAVAILABLE
    assert not (tmp_path / "missing").exists()


def test_new_process_replays_old_facts_after_all_original_roots_and_copies_move(
    tmp_path: Path,
) -> None:
    import json
    import os
    import sqlite3
    import subprocess
    import sys
    from contextlib import closing

    from paper_radar.backup import verify_backup
    from paper_radar.config import compile_config
    from tests.config_projection_support import full_inputs
    from tests.config_test_support import run_cli
    from tests.restore_support import history_view

    source_root = tmp_path / "source"
    settings, database = full_inputs(source_root)
    first = compile_config(settings, database)
    assert (
        first.snapshot_id
        == "cc63bda022c43f5f20d139d3cbe8b882e245f97eea5484f1348beb7833f23b9d"
    )
    (settings.parent / "read/read-v2.yaml").write_text(
        "version: read-v2\nchunking_version: v1\n", encoding="utf-8"
    )
    settings.write_text(
        settings.read_text().replace("read: read-v1", "read: read-v2"), encoding="utf-8"
    )
    original_profile = settings.parent / "profiles/profile-v1.yaml"
    (settings.parent / "profiles/profile-v2.yaml").write_text(
        original_profile.read_text()
        .replace("version: profile-v1", "version: profile-v2")
        .replace("background: climate", "background: PRIVATE_PROFILE_BODY"),
        encoding="utf-8",
    )
    (source_root / "prompts/screening/boundary-v2.md").write_bytes(
        b"PRIVATE_PROMPT_BODY\n"
    )
    settings.write_text(
        settings.read_text()
        .replace("profile: profile-v1", "profile: profile-v2")
        .replace("prompts:\n  boundary: v1", "prompts:\n  boundary: v2"),
        encoding="utf-8",
    )
    second = compile_config(settings, database)
    assert first.snapshot_id != second.snapshot_id
    data_root = source_root / "data"
    store = ArtifactStore(database, data_root)
    store.publish_single("model_success_response", [b"PRIVATE_MODEL_RESPONSE"])
    store.publish_artifact(
        "extraction",
        {
            "manifest": [b"PRIVATE_MANIFEST"],
            "document": [b"PRIVATE_TEXT"],
            "reading": [b"PRIVATE_TEXT"],
            "evidence_map": [b"PRIVATE_EVIDENCE"],
        },
    )
    expected = history_view(database, data_root)
    assert len(expected["snapshots"]) == 2
    assert all(len(snapshot["projections"]) == 6 for snapshot in expected["snapshots"])
    expectation = tmp_path / "expected.json"
    expectation.write_text(json.dumps(expected), encoding="utf-8")
    original_files = tree(data_root)
    batch = create_backup(database, data_root, tmp_path / "backups")
    old_batch = tree(batch.batch_dir)
    moved_parent = tmp_path / "moved-backups"
    moved_parent.mkdir()
    moved_batch = batch.batch_dir.rename(moved_parent / batch.batch_dir.name)
    assert verify_backup(moved_batch).manifest_sha256 == batch.manifest_sha256
    unavailable = source_root.rename(tmp_path / "source-unavailable")
    assert not database.exists() and not data_root.exists() and not settings.exists()
    assert not (source_root / "prompts").exists()
    target = tmp_path / "restored"
    restored = run_cli(
        tmp_path, "restore", "verify", str(moved_batch), "--target", str(target)
    )
    assert restored.returncode == 0, restored.stderr
    assert "PRIVATE_" not in restored.stdout + restored.stderr
    verified_output = run_cli(tmp_path, "backup", "verify", str(moved_batch))
    assert verified_output.returncode == 0, verified_output.stderr
    assert restored.stdout == verified_output.stdout
    assert all(
        artifact.artifact_id not in restored.stdout
        for artifact in batch.manifest.artifacts
    )
    moved = target.rename(tmp_path / "relocated-restored")
    restored_db = moved / "database.sqlite3"
    assert restored_db.read_bytes() == (moved_batch / "database.sqlite3").read_bytes()
    assert restored_db.read_bytes()[18:20] == b"\x01\x01"
    listed = run_cli(
        tmp_path, "config", "snapshots", "list", "--database", str(restored_db)
    )
    assert listed.returncode == 0, listed.stderr
    assert first.snapshot_id in listed.stdout and second.snapshot_id in listed.stdout
    diff = run_cli(
        tmp_path,
        "config",
        "diff",
        first.snapshot_id,
        second.snapshot_id,
        "--database",
        str(restored_db),
    )
    assert diff.returncode == 0, diff.stderr
    assert "PRIVATE_" not in listed.stdout + listed.stderr + diff.stdout + diff.stderr
    repo = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.restore_process.query",
            str(moved),
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
    assert result.returncode == 0, result.stderr
    assert tree(moved) == old_batch
    assert restored_db.read_bytes()[18:20] == b"\x01\x01"
    upgraded = run_cli(tmp_path, "db", "upgrade", "--database", str(restored_db))
    assert upgraded.returncode == 0, upgraded.stderr
    assert "a401_pi_supply" in upgraded.stdout
    with closing(sqlite3.connect(restored_db)) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone() == ("wal",)
    assert history_view(restored_db, moved) == expected
    assert tree(moved_batch) == old_batch
    assert (moved_batch / "database.sqlite3").read_bytes()[18:20] == b"\x01\x01"
    copied = moved / batch.manifest.blobs[0].path
    assert (
        copied.stat().st_ino
        != (moved_batch / batch.manifest.blobs[0].path).stat().st_ino
    )
    assert (
        copied.stat().st_ino
        != (unavailable / "data" / batch.manifest.blobs[0].path).stat().st_ino
    )
    copied.chmod(0o600)
    copied.write_bytes(b"damaged restored bytes")
    copied.chmod(0o400)
    assert tree(moved_batch) == old_batch
    assert tree(unavailable / "data") == original_files
