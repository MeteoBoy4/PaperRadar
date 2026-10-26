"""创建失败与碰撞不发布半批次,也不影响旧完成批次。"""

import errno
import sqlite3
from pathlib import Path

import pytest

from paper_radar.backup import BackupError, create_backup, service, verify_backup
from paper_radar.backup.files import publish_directory
from tests.backup_support import populated, tree


@pytest.mark.parametrize(
    "point",
    [
        "copy",
        "partial_copy",
        "space",
        "snapshot",
        "verify",
        "publish",
        "interrupt",
        "publish_interrupt",
    ],
)
def test_failures_clean_only_their_own_staging_and_keep_old_batches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, point: str
) -> None:
    database, root, _ = populated(tmp_path / "source")
    old = create_backup(database, root, tmp_path / "output")
    before = tree(old.batch_dir)
    unrelated = tmp_path / "output/.staging-unrelated"
    unrelated.mkdir()
    (unrelated / "owner").write_bytes(b"other process")
    original_snapshot = service._online_snapshot
    from paper_radar.backup.files import copy_file as original_copy

    copied = 0

    def fail(*args: object, **kwargs: object) -> None:
        if point.endswith("interrupt"):
            raise KeyboardInterrupt
        raise OSError(errno.ENOSPC if point == "space" else errno.EIO, "SECRET failure")

    def fail_after_snapshot(source: Path, destination: Path) -> None:
        original_snapshot(source, destination)
        fail()

    def partial_copy(
        source: Path, destination: Path, entry: object, *, mode: int
    ) -> None:
        nonlocal copied
        if copied:
            fail()
        from paper_radar.backup.manifest import FileEntry

        assert isinstance(entry, FileEntry)
        original_copy(source, destination, entry, mode=mode)
        copied += 1

    target = {
        "copy": "copy_file",
        "partial_copy": "copy_file",
        "space": "copy_file",
        "interrupt": "copy_file",
        "snapshot": "_online_snapshot",
        "verify": "verify_contents",
        "publish": "publish_directory",
        "publish_interrupt": "publish_directory",
    }[point]
    monkeypatch.setattr(
        service,
        target,
        fail_after_snapshot
        if point == "snapshot"
        else partial_copy
        if point == "partial_copy"
        else fail,
    )
    with pytest.raises(
        KeyboardInterrupt if point.endswith("interrupt") else BackupError
    ):
        create_backup(database, root, tmp_path / "output")
    monkeypatch.undo()
    if point == "partial_copy":
        assert copied == 1
    assert {path.name for path in (tmp_path / "output").iterdir()} == {
        old.batch_dir.name,
        unrelated.name,
    }
    assert (unrelated / "owner").read_bytes() == b"other process"
    assert verify_backup(old.batch_dir) == old
    assert tree(old.batch_dir) == before
    assert create_backup(database, root, tmp_path / "output")


@pytest.mark.parametrize("location", ["batch", "staging", "publish_race"])
def test_preoccupied_empty_directories_are_never_replaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, location: str
) -> None:
    database, root, _ = populated(tmp_path / "source")
    batch_id = "20261017T000000Z-1234abcd"
    monkeypatch.setattr(
        service, "_batch_identity", lambda: (batch_id, "2026-10-17T00:00:00Z")
    )
    output = tmp_path / "output"
    output.mkdir()
    occupied = output / (f".staging-{batch_id}" if location == "staging" else batch_id)
    if location != "publish_race":
        occupied.mkdir(mode=0o700)
    else:
        original = publish_directory

        def occupy_before_publish(staging: Path, destination: Path) -> None:
            destination.mkdir(mode=0o700)
            original(staging, destination)

        monkeypatch.setattr(service, "publish_directory", occupy_before_publish)
    with pytest.raises(BackupError) as failure:
        create_backup(database, root, output)
    assert failure.value.reason.value == "batch_exists"
    assert occupied.is_dir()
    assert not list(occupied.iterdir())
    assert list(output.iterdir()) == [occupied]


@pytest.mark.parametrize(
    "kind",
    [
        "controlled_blobs",
        "controlled_tmp",
        "output_file",
        "missing_db",
        "old_db",
        "unknown_db",
        "source_missing",
        "source_corrupt",
        "source_writable",
        "config_corrupt",
    ],
)
def test_bad_sources_and_outputs_fail_without_publishing(
    tmp_path: Path, kind: str
) -> None:
    database, root, _ = populated(tmp_path / "source")
    output = tmp_path / "output"
    blob = next(path for path in (root / "blobs").rglob("*") if path.is_file())
    if kind == "controlled_blobs":
        output = root / "blobs/nested"
    elif kind == "controlled_tmp":
        output = root / "tmp/nested"
    elif kind == "output_file":
        output.write_bytes(b"SECRET occupied")
    elif kind == "missing_db":
        database = tmp_path / "absent.sqlite3"
    elif kind in {"old_db", "unknown_db", "config_corrupt"}:
        with sqlite3.connect(database) as connection:
            if kind == "config_corrupt":
                connection.execute(
                    "UPDATE runtime_config_snapshots SET payload_json='{}'"
                )
            else:
                connection.execute(
                    "UPDATE alembic_version SET version_num=?",
                    ("a201_profile_snapshot" if kind == "old_db" else "unknown",),
                )
    elif kind == "source_missing":
        blob.unlink()
    elif kind == "source_corrupt":
        blob.chmod(0o600)
        blob.write_bytes(b"!" * blob.stat().st_size)
        blob.chmod(0o400)
    elif kind == "source_writable":
        blob.chmod(0o600)
    with pytest.raises(BackupError) as failure:
        create_backup(database, root, output)
    assert "SECRET" not in str(failure.value)
    if kind == "old_db":
        assert failure.value.reason.value == "upgrade_required"
    if output.is_dir():
        assert not list(output.iterdir())


def test_unregistered_future_package_head_is_not_implicitly_a_supported_backup_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import shutil

    from paper_radar.storage import database as storage_database

    database, root, _ = populated(tmp_path / "source")
    migrations = tmp_path / "migrations"
    shutil.copytree(Path(storage_database.__file__).parent / "migrations", migrations)
    (migrations / "versions/future.py").write_text(
        "revision='future'\ndown_revision='a1001_fixture_audit'\n"
        "def upgrade(): pass\ndef downgrade(): pass\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(storage_database, "_MIGRATIONS", migrations)
    storage_database.upgrade_database(database)
    with pytest.raises(BackupError) as failure:
        create_backup(database, root, tmp_path / "output")
    assert failure.value.reason.value == "unsupported_revision"
    assert not (tmp_path / "output").exists()
