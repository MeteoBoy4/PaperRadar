"""隔离恢复目标保护、来源拒绝与真实文件系统失败。"""

import shutil
from pathlib import Path

import pytest

from paper_radar.backup import (
    BackupReason,
    RestoreError,
    RestoreReason,
    create_backup,
    restore_backup,
)
from tests.backup_support import populated, tree


@pytest.mark.parametrize(
    "state",
    ["nonempty", "file", "symlink", "dangling", "same", "nested", "alias_nested"],
)
def test_unsafe_targets_cannot_change_batch_or_existing_user_data(
    tmp_path: Path, state: str
) -> None:
    database, data_root, _ = populated(tmp_path / "source")
    batch = create_backup(database, data_root, tmp_path / "backups")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "SECRET-user-file").write_bytes(b"SECRET keep")
    target = tmp_path / "target"
    if state == "nonempty":
        shutil.copytree(outside, target)
    elif state == "file":
        target.write_bytes(b"SECRET existing file")
    elif state == "symlink":
        target.symlink_to(outside)
    elif state == "dangling":
        target.symlink_to(tmp_path / "missing")
    elif state == "same":
        target = batch.batch_dir
    elif state == "nested":
        target = batch.batch_dir / "new"
    elif state == "alias_nested":
        alias = tmp_path / "alias"
        alias.symlink_to(batch.batch_dir)
        target = alias / "new"
    original = tree(batch.batch_dir)
    outside_before = tree(outside)
    before = target.read_bytes() if state == "file" else None
    with pytest.raises(RestoreError) as failure:
        restore_backup(batch.batch_dir, target)
    assert failure.value.reason in {
        RestoreReason.TARGET_NOT_EMPTY,
        RestoreReason.TARGET_UNAVAILABLE,
        RestoreReason.TARGET_OVERLAP,
    }
    assert tree(batch.batch_dir) == original
    assert tree(outside) == outside_before
    if state == "file":
        assert target.read_bytes() == before
    if state == "nonempty":
        assert tree(target) == outside_before
    assert not list(tmp_path.glob(".restore-staging-*"))


@pytest.mark.parametrize(
    "damage",
    [
        "staging",
        "renamed",
        "missing",
        "hash",
        "file",
        "wal",
        "shm",
        "journal",
        "extra_directory",
    ],
)
def test_restore_reuses_strict_batch_rejection_before_creating_any_copy(
    tmp_path: Path, damage: str
) -> None:
    database, data_root, _ = populated(tmp_path / "source")
    batch = create_backup(database, data_root, tmp_path / "backups")
    source = batch.batch_dir
    if damage == "staging":
        source = source.rename(source.with_name(".staging-" + source.name))
    elif damage == "renamed":
        source = source.rename(source.with_name("20260101T000000Z-00000000"))
    elif damage == "missing":
        (source / batch.manifest.blobs[0].path).unlink()
    elif damage == "hash":
        blob = source / batch.manifest.blobs[0].path
        blob.chmod(0o600)
        blob.write_bytes(b"X" * blob.stat().st_size)
        blob.chmod(0o400)
    elif damage == "extra_directory":
        (source / ".staging-extra").mkdir(mode=0o700)
    else:
        name = {
            "file": "SECRET-extra",
            "wal": "database.sqlite3-wal",
            "shm": "database.sqlite3-shm",
            "journal": "database.sqlite3-journal",
        }[damage]
        (source / name).write_bytes(b"SECRET-extra")
    before = tree(source)
    with pytest.raises(RestoreError) as failure:
        restore_backup(source, tmp_path / "target")
    assert isinstance(failure.value.reason, BackupReason)
    assert tree(source) == before
    assert not (tmp_path / "target").exists()
    assert not list(tmp_path.glob(".restore-staging-*"))


@pytest.mark.parametrize("phase", ["copy", "verify", "publish", "interrupt"])
def test_controlled_failures_clean_only_own_staging_and_allow_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    phase: str,
) -> None:
    import os
    from typing import Any

    database, data_root, _ = populated(tmp_path / "source")
    batch = create_backup(database, data_root, tmp_path / "backups")
    original = tree(batch.batch_dir)
    target = tmp_path / "target"
    target.mkdir()
    target_inode = target.stat().st_ino
    abandoned = tmp_path / ".restore-staging-keep"
    abandoned.mkdir(mode=0o700)
    (abandoned / "keep").write_bytes(b"SECRET unrelated")
    opened = os.open
    read_bytes = Path.read_bytes

    def fail_copy(path: Any, *args: Any, **kwargs: Any) -> int:
        if ".restore-staging-" in str(path) and str(path).endswith("database.sqlite3"):
            if phase == "interrupt":
                raise KeyboardInterrupt("SECRET interrupt")
            raise OSError("SECRET copy failure")
        return opened(path, *args, **kwargs)

    def fail_publish(*args: Any, **kwargs: Any) -> None:
        raise OSError("SECRET publish failure")

    damaged = False

    def damage_copy(path: Path) -> bytes:
        nonlocal damaged
        if (
            ".restore-staging-" in str(path)
            and path.name == "manifest.json"
            and not damaged
        ):
            damaged = True
            blob = path.parent / batch.manifest.blobs[0].path
            blob.chmod(0o600)
            blob.write_bytes(b"X" * blob.stat().st_size)
            blob.chmod(0o400)
        return read_bytes(path)

    if phase in ("copy", "interrupt"):
        monkeypatch.setattr(os, "open", fail_copy)
    elif phase == "verify":
        monkeypatch.setattr(Path, "read_bytes", damage_copy)
    elif phase == "publish":
        monkeypatch.setattr(os, "rename", fail_publish)
    with pytest.raises(RestoreError) as failure:
        restore_backup(batch.batch_dir, target)
    assert "SECRET" not in str(failure.value) + caplog.text
    monkeypatch.undo()
    assert tree(batch.batch_dir) == original
    assert target.stat().st_ino == target_inode and not list(target.iterdir())
    assert list(tmp_path.glob(".restore-staging-*")) == [abandoned]
    assert (abandoned / "keep").read_bytes() == b"SECRET unrelated"
    assert (
        restore_backup(batch.batch_dir, target).manifest_sha256 == batch.manifest_sha256
    )


@pytest.mark.parametrize("phase", ["copy", "before_publish", "after_publish"])
def test_real_process_termination_never_publishes_partial_contents(
    tmp_path: Path, phase: str
) -> None:
    from paper_radar.backup import verify_contents
    from tests.restore_support import paused_restore

    database, data_root, _ = populated(tmp_path / "source")
    batch = create_backup(database, data_root, tmp_path / "backups")
    before = tree(batch.batch_dir)
    target = tmp_path / "restored"
    with paused_restore(batch.batch_dir, target, phase) as (process, _):
        process.kill()
        output, errors = process.communicate(timeout=15)
        assert process.returncode != 0
    assert "SECRET" not in output + errors
    assert tree(batch.batch_dir) == before
    remnants = list(tmp_path.glob(".restore-staging-*"))
    if phase == "after_publish":
        assert target.is_dir() and not remnants
        verify_contents(target, batch.manifest)
        with pytest.raises(RestoreError):
            restore_backup(batch.batch_dir, target)
    else:
        assert not target.exists() and len(remnants) == 1
        if phase == "copy":
            assert (remnants[0] / "database.sqlite3").is_file()
        else:
            verify_contents(remnants[0], batch.manifest)
    restored = restore_backup(batch.batch_dir, tmp_path / "retry")
    assert restored.manifest_sha256 == batch.manifest_sha256
    assert all(path.exists() for path in remnants)
    assert tree(batch.batch_dir) == before


@pytest.mark.parametrize("initially_empty", [False, True])
def test_target_claimed_at_the_final_rename_is_not_overwritten(
    tmp_path: Path, initially_empty: bool
) -> None:
    import os

    from tests.restore_support import paused_restore

    database, data_root, _ = populated(tmp_path / "source")
    batch = create_backup(database, data_root, tmp_path / "backups")
    before = tree(batch.batch_dir)
    target = tmp_path / "restored"
    if initially_empty:
        target.mkdir()
    with paused_restore(batch.batch_dir, target, "before_publish") as (
        process,
        release,
    ):
        target.mkdir(exist_ok=True)
        sentinel = target / "SECRET-concurrent-user-file"
        sentinel.write_bytes(b"SECRET preserve concurrent data")
        inode = target.stat().st_ino
        os.write(release, b"G")
        output, errors = process.communicate(timeout=15)
        assert process.returncode == 2
    assert "target_not_empty" in errors
    assert "SECRET" not in output + errors
    assert target.stat().st_ino == inode
    assert tree(target) == {sentinel.name: b"SECRET preserve concurrent data"}
    assert tree(batch.batch_dir) == before
    assert not list(tmp_path.glob(".restore-staging-*"))
