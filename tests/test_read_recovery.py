"""Read 配置与候选原始字节的非空隔离恢复。"""

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from paper_radar.backup import (
    BackupError,
    BackupReason,
    RestoreError,
    create_backup,
    restore_backup,
    verify_backup,
)
from paper_radar.config import list_config_snapshots, load_config_snapshot
from paper_radar.storage.artifact_contract import ArtifactError, ArtifactReason
from paper_radar.storage.artifacts import ArtifactStore
from tests.backup_support import tree
from tests.read_recovery_support import archive, recover_in_new_process


def test_read_history_replays_after_original_paths_are_blocked_and_restore_moves(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    data = archive(tmp_path / "original")
    result = recover_in_new_process(data, tmp_path)
    assert result == {
        "cases": 4,
        "snapshots": 2,
        "original_paths_blocked": True,
        "read_only": True,
        "relocated": True,
        "no_business_facts": True,
        "restored_policy_rejections": True,
    }
    output = capsys.readouterr()
    assert "PRIVATE_" not in output.out + output.err + caplog.text


def test_saved_and_loaded_read_snapshots_hide_profile_and_prompt_in_repr(
    tmp_path: Path,
) -> None:
    data = archive(tmp_path / "original")
    for summary in list_config_snapshots(data.database):
        snapshot = load_config_snapshot(data.database, summary.snapshot_id)
        assert "PRIVATE_PROFILE" in snapshot.payload_json
        assert "PRIVATE_READING_PROMPT" in snapshot.payload_json
        assert "PRIVATE_" not in repr(snapshot) + str(snapshot)


def _rehash_database(batch: Path) -> None:
    manifest = batch / "manifest.json"
    value = json.loads(manifest.read_bytes())
    raw = (batch / "database.sqlite3").read_bytes()
    value["database"].update(
        sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw)
    )
    manifest.write_bytes(
        (
            json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
        ).encode()
    )


@pytest.mark.parametrize("kind", ["contract_schema", "contract_manifest"])
@pytest.mark.parametrize("damage", ["bytes", "reference"])
def test_read_backup_rejects_corrupt_registered_contracts_and_missing_references(
    tmp_path: Path, kind: str, damage: str
) -> None:
    data = archive(tmp_path / "original")
    batch = create_backup(data.database, data.data_root, tmp_path / "backups")
    source = tree(data.data_root)
    with sqlite3.connect(batch.batch_dir / "database.sqlite3") as connection:
        if damage == "bytes":
            connection.execute(
                "UPDATE config_versions SET raw_content=? WHERE kind=? AND name='read'",
                (b"PRIVATE_CORRUPT_CONTRACT", kind),
            )
        else:
            connection.execute(
                "DELETE FROM snapshot_version_refs WHERE kind=? AND name='read'",
                (kind,),
            )
    # 外层数据库文件完整性重新成立,必须由历史配置闭包拒绝。
    _rehash_database(batch.batch_dir)
    before = tree(batch.batch_dir)
    with pytest.raises(BackupError) as rejected:
        verify_backup(batch.batch_dir)
    assert rejected.value.reason is BackupReason.CONFIG_INVALID
    target = tmp_path / "restored"
    with pytest.raises(RestoreError) as restore_rejected:
        restore_backup(batch.batch_dir, target)
    assert restore_rejected.value.reason is BackupReason.CONFIG_INVALID
    assert "PRIVATE_" not in repr(rejected.value) + str(restore_rejected.value)
    assert not target.exists()
    assert tree(batch.batch_dir) == before
    assert tree(data.data_root) == source


@pytest.mark.parametrize(
    ("damage", "reason"),
    [("missing", BackupReason.FILE_MISSING), ("bytes", BackupReason.FILE_CORRUPT)],
)
def test_read_response_blob_corruption_is_rejected_before_restore(
    tmp_path: Path, damage: str, reason: BackupReason
) -> None:
    data = archive(tmp_path / "original")
    batch = create_backup(data.database, data.data_root, tmp_path / "backups")
    original = tree(data.data_root)
    blob = batch.batch_dir / batch.manifest.blobs[0].path
    if damage == "missing":
        blob.unlink()
    else:
        blob.chmod(0o600)
        blob.write_bytes(b"!" * blob.stat().st_size)
        blob.chmod(0o400)
    before = tree(batch.batch_dir)
    with pytest.raises(BackupError) as rejected:
        verify_backup(batch.batch_dir)
    assert rejected.value.reason is reason
    with pytest.raises(RestoreError) as restore_rejected:
        restore_backup(batch.batch_dir, tmp_path / "restored")
    assert restore_rejected.value.reason is reason
    assert tree(batch.batch_dir) == before
    assert tree(data.data_root) == original


def test_damaged_restored_response_does_not_modify_backup_or_source(
    tmp_path: Path,
) -> None:
    data = archive(tmp_path / "original")
    batch = create_backup(data.database, data.data_root, tmp_path / "backups")
    target = tmp_path / "restored"
    restore_backup(batch.batch_dir, target)
    source, backup = tree(data.data_root), tree(batch.batch_dir)
    store = ArtifactStore(target / "database.sqlite3", target)
    artifact_id = data.artifacts["zh-reduce"]
    _, blobs = store.artifact_blobs(artifact_id)
    path = store.verified_blob_path(blobs[0])
    path.chmod(0o600)
    path.write_bytes(b"!" * blobs[0].size_bytes)
    path.chmod(0o400)
    with pytest.raises(ArtifactError) as rejected:
        store.read_artifact(artifact_id)
    assert rejected.value.reason is ArtifactReason.BLOB_CORRUPT
    assert "PRIVATE_" not in str(rejected.value) + repr(rejected.value)
    assert verify_backup(batch.batch_dir).manifest_sha256 == batch.manifest_sha256
    assert tree(batch.batch_dir) == backup
    assert tree(data.data_root) == source


@pytest.mark.parametrize(
    ("revision", "reason"),
    [
        ("a201_profile_snapshot", BackupReason.UNSUPPORTED_REVISION),
        ("unknown", BackupReason.UNSUPPORTED_REVISION),
    ],
)
def test_read_materials_do_not_relax_backup_revision_admission(
    tmp_path: Path, revision: str, reason: BackupReason
) -> None:
    data = archive(tmp_path / "original")
    batch = create_backup(data.database, data.data_root, tmp_path / "backups")
    with sqlite3.connect(batch.batch_dir / "database.sqlite3") as connection:
        connection.execute("UPDATE alembic_version SET version_num=?", (revision,))
    _rehash_database(batch.batch_dir)
    before = tree(batch.batch_dir)
    with pytest.raises(BackupError) as rejected:
        verify_backup(batch.batch_dir)
    assert rejected.value.reason is reason
    assert tree(batch.batch_dir) == before
