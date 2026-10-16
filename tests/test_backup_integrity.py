"""损坏批次只读拒绝,包括与全量登记的双向匹配。"""

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from paper_radar.backup import BackupError, create_backup, verify_backup
from tests.backup_support import populated, tree


@pytest.mark.parametrize(
    "damage",
    [
        "missing_blob",
        "same_length_blob",
        "writable_blob",
        "missing_database",
        "database_bytes",
        "unknown_revision",
        "known_old_revision",
        "missing_member",
        "orphan_blob",
        "config_payload",
        "omitted_blob",
        "omitted_artifact",
        "omitted_snapshot",
        "forged_artifact",
        "format",
        "bool_format",
        "blob_layout",
        "wrong_count",
        "wrong_revision",
        "invalid_json",
        "duplicate_key",
        "absolute_path",
        "symlink_blob",
        "symlink_database",
    ],
)
def test_corrupt_batches_are_rejected_without_any_byte_or_entry_changes(
    tmp_path: Path, damage: str
) -> None:
    database, data_root, _ = populated(tmp_path / "source")
    result = create_backup(database, data_root, tmp_path / "output")
    batch = result.batch_dir
    manifest_path = batch / "manifest.json"
    value: dict[str, Any] = json.loads(manifest_path.read_bytes())
    blob = batch / result.manifest.blobs[0].path
    if damage == "missing_blob":
        blob.unlink()
    elif damage == "same_length_blob":
        blob.chmod(0o600)
        blob.write_bytes(b"!" * blob.stat().st_size)
        blob.chmod(0o400)
    elif damage == "writable_blob":
        blob.chmod(0o600)
    elif damage == "missing_database":
        (batch / "database.sqlite3").unlink()
    elif damage == "database_bytes":
        (batch / "database.sqlite3").write_bytes(b"not a database")
    elif damage in {
        "unknown_revision",
        "known_old_revision",
        "missing_member",
        "orphan_blob",
        "config_payload",
    }:
        with sqlite3.connect(batch / "database.sqlite3") as connection:
            if damage.endswith("revision"):
                revision = (
                    "unknown"
                    if damage == "unknown_revision"
                    else "a201_profile_snapshot"
                )
                connection.execute(
                    "UPDATE alembic_version SET version_num=?", (revision,)
                )
            elif damage == "missing_member":
                connection.execute(
                    "DELETE FROM artifact_members "
                    "WHERE rowid=(SELECT min(rowid) FROM artifact_members)"
                )
            elif damage == "orphan_blob":
                connection.execute(
                    "INSERT INTO content_objects"
                    "(sha256,size_bytes,relative_path,layout_version,created_at) "
                    "VALUES(?,0,?,1,'2026-10-17T00:00:00+00:00')",
                    ("0" * 64, "blobs/sha256/00/" + "0" * 64),
                )
            else:
                connection.execute(
                    "UPDATE runtime_config_snapshots SET payload_json='{}'"
                )
        raw = (batch / "database.sqlite3").read_bytes()
        value["database"].update(
            sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw)
        )
    elif damage == "omitted_blob":
        value["blobs"].pop()
    elif damage == "omitted_artifact":
        value["artifacts"].pop()
    elif damage == "omitted_snapshot":
        value["snapshot_ids"].clear()
    elif damage == "forged_artifact":
        value["artifacts"][0]["artifact_id"] = "0" * 64
    elif damage in ("format", "bool_format"):
        value["format_version"] = 2 if damage == "format" else True
    elif damage == "blob_layout":
        value["blob_layout_version"] = 2
    elif damage == "wrong_count":
        value["counts"]["artifacts"] += 1
    elif damage == "wrong_revision":
        value["database_revision"] = value["code"]["migration_revision"] = "unknown"
    elif damage == "absolute_path":
        value["blobs"][0]["path"] = str(tmp_path / "outside")
    elif damage.startswith("symlink"):
        selected = blob if damage == "symlink_blob" else batch / "database.sqlite3"
        outside = tmp_path / "external"
        selected.rename(outside)
        selected.symlink_to(outside)
    manifest_path.write_bytes(
        (
            json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
        ).encode()
    )
    if damage == "invalid_json":
        manifest_path.write_bytes(b"invalid")
    elif damage == "duplicate_key":
        raw = manifest_path.read_bytes()
        manifest_path.write_bytes(b'{"format_version":1,' + raw[1:])
    before = tree(batch)
    with pytest.raises(BackupError):
        verify_backup(batch)
    assert tree(batch) == before


@pytest.mark.parametrize(
    "extra",
    [
        "stray",
        "database.sqlite3-wal",
        "database.sqlite3-shm",
        "database.sqlite3-journal",
        ".staging-extra",
        "empty-directory",
    ],
)
def test_every_unlisted_entry_is_rejected_read_only(tmp_path: Path, extra: str) -> None:
    database, root, _ = populated(tmp_path / "source")
    result = create_backup(database, root, tmp_path / "output")
    if extra in {"empty-directory", ".staging-extra"}:
        (result.batch_dir / extra).mkdir(mode=0o700)
    else:
        (result.batch_dir / extra).write_bytes(b"SECRET unexpected")
    before = tree(result.batch_dir)
    with pytest.raises(BackupError) as failure:
        verify_backup(result.batch_dir)
    assert failure.value.reason.value == "unexpected_entry"
    assert tree(result.batch_dir) == before


def test_complete_staging_and_renamed_batch_cannot_be_accepted(tmp_path: Path) -> None:
    database, root, _ = populated(tmp_path / "source")
    result = create_backup(database, root, tmp_path / "output")
    staging = result.batch_dir.with_name(".staging-" + result.batch_dir.name)
    result.batch_dir.rename(staging)
    before = tree(staging)
    with pytest.raises(BackupError) as failure:
        verify_backup(staging)
    assert failure.value.reason.value == "not_published"
    renamed = staging.with_name("20260101T000000Z-00000000")
    staging.rename(renamed)
    with pytest.raises(BackupError) as failure:
        verify_backup(renamed)
    assert failure.value.reason.value == "not_published"
    assert tree(renamed) == before
