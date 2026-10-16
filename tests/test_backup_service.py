"""真实在线备份与公开只读校验边界。"""

import json
import re
import stat
from pathlib import Path

import pytest

from paper_radar.backup import create_backup, verify_backup
from paper_radar.config import load_config_snapshot
from paper_radar.storage.artifacts import ArtifactStore
from tests.backup_support import populated, tree


def test_backup_is_self_contained_deduplicated_and_verification_is_read_only(
    tmp_path: Path,
) -> None:
    database, data_root, snapshot_id = populated(tmp_path / "source")
    (data_root / "unregistered-secret").write_bytes(b"SECRET excluded")
    before = database.read_bytes()
    result = create_backup(database, data_root, tmp_path / "output")
    assert re.fullmatch(r"\d{8}T\d{6}Z-[0-9a-f]{8}", result.batch_dir.name)
    assert database.read_bytes() == before
    assert len(result.manifest.blobs) == 2
    assert len(result.manifest.artifacts) == 3
    assert result.manifest.snapshot_ids == (snapshot_id,)
    assert (result.batch_dir / "database.sqlite3").read_bytes()[18:20] == b"\x01\x01"
    assert all(
        stat.S_IMODE((result.batch_dir / blob.path).stat().st_mode) == 0o400
        for blob in result.manifest.blobs
    )
    original = tree(result.batch_dir)
    (tmp_path / "source").rename(tmp_path / "unavailable")
    assert verify_backup(result.batch_dir) == result
    assert tree(result.batch_dir) == original
    assert load_config_snapshot(result.batch_dir / "database.sqlite3", snapshot_id)
    store = ArtifactStore(result.batch_dir / "database.sqlite3", result.batch_dir)
    assert len(store.list_artifacts()) == 3
    manifest_bytes = (result.batch_dir / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    assert "SECRET" not in manifest_bytes.decode()
    assert str(tmp_path) not in manifest_bytes.decode()
    assert manifest["code"]["git_commit"] is None


def test_online_backup_preserves_wal_commits_and_fixes_its_own_closure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import shutil
    import sqlite3
    from contextlib import closing

    from paper_radar.backup import service

    database, data_root, snapshot_id = populated(tmp_path / "source")
    store = ArtifactStore(database, data_root)
    with closing(sqlite3.connect(database)) as writer:
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("SELECT count(*) FROM artifacts").fetchone()
        committed = store.publish_single("reference_tei", (b"WAL-only committed",))
        assert database.with_name(database.name + "-wal").stat().st_size > 0
        negative = tmp_path / "main-only.sqlite3"
        shutil.copyfile(database, negative)
        assert len(ArtifactStore(negative, data_root).list_artifacts()) == 3
        writer.execute("BEGIN IMMEDIATE")
        writer.execute(
            "UPDATE runtime_config_snapshots SET created_at='SECRET-uncommitted'"
        )
        result = create_backup(database, data_root, tmp_path / "output")
        assert committed.artifact_id in {
            a.artifact_id for a in result.manifest.artifacts
        }
        assert len(result.manifest.artifacts) == 4
        assert load_config_snapshot(result.batch_dir / "database.sqlite3", snapshot_id)
        writer.rollback()
        original = service._online_snapshot

        def commit_after_snapshot(source: Path, destination: Path) -> None:
            original(source, destination)
            store.publish_single("original_pdf", (b"later committed payload",))

        monkeypatch.setattr(service, "_online_snapshot", commit_after_snapshot)
        fixed = create_backup(database, data_root, tmp_path / "next")
        assert len(store.list_artifacts()) == 5
        assert len(fixed.manifest.artifacts) == 4
        assert verify_backup(fixed.batch_dir) == fixed


def test_backup_streams_read_only_source_objects_into_independent_private_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typing import IO, Any

    database, data_root, _ = populated(tmp_path / "source")
    source_blobs = tuple(
        path for path in (data_root / "blobs").rglob("*") if path.is_file()
    )
    for path in source_blobs:
        path.chmod(0o444)
    original_open = Path.open

    class BoundedRead:
        def __init__(self, stream: IO[Any]) -> None:
            self.stream = stream

        def __enter__(self) -> "BoundedRead":
            return self

        def __exit__(self, *args: object) -> None:
            self.stream.close()

        def read(self, size: int = -1) -> bytes:
            assert 0 < size <= 1024 * 1024, "必须分段读取内容对象"
            chunk = self.stream.read(size)
            assert isinstance(chunk, bytes)
            return chunk

    def bounded_open(path: Path, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        stream = original_open(path, mode, *args, **kwargs)
        if path in source_blobs and mode == "rb":
            return BoundedRead(stream)
        return stream

    monkeypatch.setattr(Path, "open", bounded_open)
    result = create_backup(database, data_root, tmp_path / "output")
    monkeypatch.undo()
    for entry in result.manifest.blobs:
        source = data_root / entry.path
        target = result.batch_dir / entry.path
        assert source.stat().st_ino != target.stat().st_ino
        assert stat.S_IMODE(target.stat().st_mode) == 0o400
    assert stat.S_IMODE(result.batch_dir.stat().st_mode) == 0o700
    assert verify_backup(result.batch_dir) == result


def test_safe_nested_output_excludes_unregistered_files_and_older_batches(
    tmp_path: Path,
) -> None:
    database, data_root, _ = populated(tmp_path / "source")
    for name in (
        "cache/http",
        "auth/token",
        "config/draft.yaml",
        "settings.yaml",
        "contracts/export",
        "reports/daily",
        "logs/run",
        "tmp/unregistered",
    ):
        path = data_root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"SECRET do not include")
    output = data_root / "backups"
    first = create_backup(database, data_root, output)
    second = create_backup(database, data_root, output)
    assert len(first.manifest.blobs) == len(second.manifest.blobs) == 2
    assert all(
        b"SECRET do not include" not in (second.batch_dir / entry.path).read_bytes()
        for entry in second.manifest.blobs
    )
    assert not (second.batch_dir / "backups").exists()
    assert verify_backup(first.batch_dir) == first
    assert verify_backup(second.batch_dir) == second


def test_audit_time_does_not_become_an_integrity_or_batch_identity_gate(
    tmp_path: Path,
) -> None:
    database, data_root, _ = populated(tmp_path / "source")
    result = create_backup(database, data_root, tmp_path / "output")
    value = json.loads((result.batch_dir / "manifest.json").read_bytes())
    value["created_at"] = "2000-01-01T00:00:00Z"
    (result.batch_dir / "manifest.json").write_bytes(
        (
            json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
        ).encode()
    )
    verified = verify_backup(result.batch_dir)
    assert verified.manifest.created_at == "2000-01-01T00:00:00Z"
    assert verified.manifest.batch_id == result.manifest.batch_id
