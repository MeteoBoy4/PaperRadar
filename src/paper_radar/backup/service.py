"""在线固定数据库后复制完整登记闭包,再原子发布自包含批次。"""

from __future__ import annotations

import importlib.metadata
import os
import secrets
import shutil
import sqlite3
import stat
from contextlib import closing, suppress
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

from pydantic import ValidationError

from paper_radar.backup.files import (
    controlled_path,
    copy_file,
    file_entry,
    mkdir_private,
    publish_directory,
    read_manifest,
    sync_directory,
    verify_file,
    verify_tree,
)
from paper_radar.backup.manifest import (
    BACKUP_DATABASE_REVISION,
    BACKUP_FORMAT_VERSION,
    BATCH_ID,
    DATABASE_FILE,
    MANIFEST_FILE,
    BackupArtifact,
    BackupError,
    BackupManifest,
    BackupReason,
    BackupResult,
    CodeIdentity,
    FileEntry,
    artifact_entry,
    blob_entry,
    counts_for,
    parse_manifest,
)
from paper_radar.config import ConfigError, list_config_snapshots, load_config_snapshot
from paper_radar.storage.artifact_contract import (
    ARTIFACT_FORMAT_VERSION,
    BLOB_LAYOUT_VERSION,
    ArtifactReason,
    BlobRecord,
)
from paper_radar.storage.artifacts import ArtifactStore
from paper_radar.storage.database import (
    DatabaseMode,
    current_revision,
    open_database,
    require_current_revision,
)
from paper_radar.storage.errors import StorageError, StorageReason

# SQLite 文件头偏移 18/19 分别为写/读格式版本;1 表示 rollback,2 表示 WAL。
_SQLITE_WRITE_VERSION_OFFSET = 18
_SQLITE_READ_VERSION_OFFSET = 19
_SQLITE_HEADER_PREFIX_SIZE = _SQLITE_READ_VERSION_OFFSET + 1
_SQLITE_ROLLBACK_VERSIONS = b"\x01\x01"


def _storage_failure(error: StorageError) -> BackupError:
    reasons = {
        StorageReason.UPGRADE_REQUIRED: BackupReason.UPGRADE_REQUIRED,
        StorageReason.UNKNOWN_REVISION: BackupReason.UNSUPPORTED_REVISION,
        StorageReason.PACKAGE_MIGRATIONS_INVALID: BackupReason.UNSUPPORTED_REVISION,
        StorageReason.DATABASE_MISSING: BackupReason.FILE_MISSING,
        StorageReason.DATABASE_UNINITIALIZED: BackupReason.DATABASE_INVALID,
        StorageReason.DATABASE_REVISION_CORRUPT: BackupReason.DATABASE_INVALID,
        StorageReason.DATABASE_UNREADABLE: BackupReason.DATABASE_INVALID,
        ArtifactReason.BLOB_MISSING: BackupReason.FILE_MISSING,
        ArtifactReason.BLOB_CORRUPT: BackupReason.FILE_CORRUPT,
        ArtifactReason.UNSAFE_PATH: BackupReason.UNSAFE_PATH,
    }
    return BackupError(reasons.get(error.reason, BackupReason.REGISTRATION_INVALID))


def _require_head(database: Path) -> None:
    if current_revision() != BACKUP_DATABASE_REVISION:
        raise BackupError(BackupReason.UNSUPPORTED_REVISION)
    engine = open_database(database, mode=DatabaseMode.READ_ONLY)
    try:
        require_current_revision(engine)
    finally:
        engine.dispose()


def _database_integrity(database: Path) -> None:
    with database.open("rb") as stream:
        if (
            stream.read(_SQLITE_HEADER_PREFIX_SIZE)[
                _SQLITE_WRITE_VERSION_OFFSET : _SQLITE_READ_VERSION_OFFSET + 1
            ]
            != _SQLITE_ROLLBACK_VERSIONS
        ):
            raise BackupError(BackupReason.DATABASE_INVALID)
    uri = f"file:{quote(str(database.resolve()))}?mode=ro"
    try:
        with closing(sqlite3.connect(uri, uri=True)) as connection:
            connection.execute("PRAGMA query_only=ON")
            if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise BackupError(BackupReason.DATABASE_INVALID)
            if connection.execute("PRAGMA foreign_key_check").fetchall():
                raise BackupError(BackupReason.DATABASE_INVALID)
        try:
            _require_head(database)
        except StorageError as error:
            if error.reason == StorageReason.UPGRADE_REQUIRED:
                raise BackupError(BackupReason.UNSUPPORTED_REVISION) from None
            raise
    except sqlite3.Error:
        raise BackupError(BackupReason.DATABASE_INVALID) from None


def _registered_contents(
    database: Path, data_root: Path
) -> tuple[tuple[FileEntry, ...], tuple[BackupArtifact, ...], tuple[str, ...]]:
    store = ArtifactStore(database, data_root)
    try:
        artifacts = tuple(
            sorted(
                (artifact_entry(record) for record in store.list_artifacts()),
                key=lambda record: record.artifact_id,
            )
        )
        blobs: dict[str, FileEntry] = {}
        for artifact in artifacts:
            _, registered = store.artifact_blobs(artifact.artifact_id)
            for blob in registered:
                blobs[blob.sha256] = blob_entry(blob)
    except (StorageError, ValidationError, ValueError):
        raise BackupError(BackupReason.REGISTRATION_INVALID) from None
    try:
        summaries = list_config_snapshots(database)
        snapshot_ids = tuple(sorted(summary.snapshot_id for summary in summaries))
        for snapshot_id in snapshot_ids:
            load_config_snapshot(database, snapshot_id)
    except (ConfigError, StorageError):
        raise BackupError(BackupReason.CONFIG_INVALID) from None
    from paper_radar.pi_supply import SupplyError, list_supplies

    try:
        list_supplies(database)
    except SupplyError:
        raise BackupError(BackupReason.SUPPLY_INVALID) from None
    return tuple(blobs[key] for key in sorted(blobs)), artifacts, snapshot_ids


def verify_contents(root: Path, manifest: BackupManifest) -> None:
    """供创建/恢复复用的完整内容校验;调用者另行保证发布位置语义。"""
    try:
        if (
            root.is_symlink()
            or not root.is_dir()
            or stat.S_IMODE(root.stat().st_mode) & 0o077
        ):
            raise BackupError(BackupReason.UNSAFE_PATH)
        if read_manifest(root) != manifest.canonical_bytes:
            raise BackupError(BackupReason.INVALID_MANIFEST)
        verify_tree(root, manifest)
        verify_file(root, manifest.database)
        for blob in manifest.blobs:
            verify_file(root, blob, blob=True)
        database = controlled_path(root, manifest.database.path)
        _database_integrity(database)
        if manifest.database_revision != BACKUP_DATABASE_REVISION:
            raise BackupError(BackupReason.UNSUPPORTED_REVISION)
        blobs, artifacts, snapshot_ids = _registered_contents(database, root)
        # 业务语义只在完整副本上解析,源材料仅供复制与字节完整性检查。
        from paper_radar.feed_ingestion import JGRFeed
        from paper_radar.feed_pipeline import PipelineError
        from paper_radar.fixture_audit import FixtureAudit, FixtureError
        from paper_radar.papers import PaperError, PaperFacts
        from paper_radar.screening_tasks import ScreeningTasks, TaskError

        try:
            PaperFacts(database, root).validate_all()
            JGRFeed(database, root).validate_all()
            ScreeningTasks(database, root).validate_all()
            FixtureAudit(database, root).validate_all()
            from paper_radar.feed_metadata import JGRMetadata
            from paper_radar.feed_pipeline import FeedPipeline, PipelineError

            JGRMetadata(database, root).validate_all()
            FeedPipeline(database, root).validate_all()
        except (PaperError, TaskError, FixtureError, PipelineError):
            raise BackupError(BackupReason.REGISTRATION_INVALID) from None
        if (
            blobs != manifest.blobs
            or artifacts != manifest.artifacts
            or snapshot_ids != manifest.snapshot_ids
            or counts_for(blobs, artifacts, snapshot_ids) != manifest.counts
        ):
            raise BackupError(BackupReason.INVALID_MANIFEST)
    except BackupError:
        raise
    except StorageError as error:
        raise _storage_failure(error) from None
    except (OSError, sqlite3.Error):
        raise BackupError(BackupReason.DATABASE_INVALID) from None


def verify_backup(batch_dir: Path) -> BackupResult:
    """只接受已发布批次,全量只读核对;不读取任何原目录。"""
    try:
        if batch_dir.is_symlink() or not batch_dir.is_dir():
            raise BackupError(BackupReason.BATCH_UNAVAILABLE)
        if BATCH_ID.fullmatch(batch_dir.name) is None:
            raise BackupError(BackupReason.NOT_PUBLISHED)
        raw = read_manifest(batch_dir)
        manifest = parse_manifest(raw)
        if batch_dir.name != manifest.batch_id:
            raise BackupError(BackupReason.NOT_PUBLISHED)
        verify_contents(batch_dir, manifest)
        return BackupResult(batch_dir.resolve(), manifest.sha256, manifest)
    except BackupError:
        raise
    except FileNotFoundError:
        raise BackupError(BackupReason.FILE_MISSING) from None
    except OSError:
        raise BackupError(BackupReason.BATCH_UNAVAILABLE) from None


def copy_verified_contents(result: BackupResult, destination: Path) -> None:
    """向私有空 staging 复制独立字节,供隔离恢复复用,不发布目标。"""
    current = verify_backup(result.batch_dir)
    if current != result:
        raise BackupError(BackupReason.INVALID_MANIFEST)
    if (
        destination.is_symlink()
        or not destination.is_dir()
        or any(destination.iterdir())
    ):
        raise BackupError(BackupReason.UNSAFE_PATH)
    for entry in (result.manifest.database, *result.manifest.blobs):
        copy_file(
            controlled_path(result.batch_dir, entry.path),
            controlled_path(destination, entry.path),
            entry,
            mode=0o600 if entry == result.manifest.database else 0o400,
        )
    _write_manifest(destination, result.manifest)
    verify_contents(destination, result.manifest)


def _write_manifest(root: Path, manifest: BackupManifest) -> None:
    descriptor = os.open(
        root / MANIFEST_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
    )
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(manifest.canonical_bytes)
        stream.flush()
        os.fsync(stream.fileno())
    sync_directory(root)


def _online_snapshot(source: Path, destination: Path) -> None:
    uri = f"file:{quote(str(source.resolve()))}?mode=ro"
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    with closing(sqlite3.connect(uri, uri=True, timeout=5)) as source_connection:
        source_connection.execute("PRAGMA query_only=ON")
        with closing(sqlite3.connect(destination)) as target:
            source_connection.backup(target, pages=256)
            if target.execute("PRAGMA journal_mode=DELETE").fetchone() != ("delete",):
                raise BackupError(BackupReason.DATABASE_INVALID)
    with destination.open("rb") as stream:
        os.fsync(stream.fileno())


def _batch_identity() -> tuple[str, str]:
    now = datetime.now(UTC).replace(microsecond=0)
    return f"{now:%Y%m%dT%H%M%SZ}-{secrets.token_hex(4)}", f"{now:%Y-%m-%dT%H:%M:%SZ}"


def create_backup(database: Path, data_root: Path, output: Path) -> BackupResult:
    """只读源库,固定快照之后按登记复制全量闭包,不扫描源根。"""
    staging: Path | None = None
    try:
        source_root = data_root.resolve()
        output_root = output.resolve()
        for excluded in (source_root / "blobs", source_root / "tmp"):
            if output_root == excluded or output_root.is_relative_to(excluded):
                raise BackupError(BackupReason.OUTPUT_INVALID)
        _require_head(database)
        if output.exists() and not output.is_dir():
            raise BackupError(BackupReason.OUTPUT_INVALID)
        mkdir_private(output_root)
        batch_id, created_at = _batch_identity()
        destination = output_root / batch_id
        if destination.exists() or destination.is_symlink():
            raise BackupError(BackupReason.BATCH_EXISTS)
        staging_path = output_root / f".staging-{batch_id}"
        try:
            staging_path.mkdir(mode=0o700)
        except FileExistsError:
            raise BackupError(BackupReason.BATCH_EXISTS) from None
        staging = staging_path
        snapshot = staging / DATABASE_FILE
        _online_snapshot(database, snapshot)
        _database_integrity(snapshot)
        blobs, artifacts, snapshot_ids = _registered_contents(snapshot, source_root)
        store = ArtifactStore(snapshot, source_root)
        for entry in blobs:
            source = store.verified_blob_path(
                BlobRecord(entry.sha256, entry.size_bytes, entry.path)
            )
            copy_file(source, controlled_path(staging, entry.path), entry, mode=0o400)
        revision = current_revision()
        manifest = BackupManifest(
            format_version=BACKUP_FORMAT_VERSION,
            batch_id=batch_id,
            created_at=created_at,
            database_revision=revision,
            artifact_format_version=ARTIFACT_FORMAT_VERSION,
            blob_layout_version=BLOB_LAYOUT_VERSION,
            database=file_entry(snapshot, DATABASE_FILE),
            blobs=blobs,
            artifacts=artifacts,
            snapshot_ids=snapshot_ids,
            counts=counts_for(blobs, artifacts, snapshot_ids),
            code=CodeIdentity(
                package_version=importlib.metadata.version("paper-radar"),
                migration_revision=revision,
                backup_format_version=BACKUP_FORMAT_VERSION,
                artifact_format_version=ARTIFACT_FORMAT_VERSION,
                blob_layout_version=BLOB_LAYOUT_VERSION,
                sqlite_version=sqlite3.sqlite_version,
                git_commit=None,
            ),
        )
        _write_manifest(staging, manifest)
        verify_contents(staging, manifest)
        publish_directory(staging, destination)
        staging = None
        return BackupResult(destination, manifest.sha256, manifest)
    except BackupError:
        raise
    except StorageError as error:
        raise _storage_failure(error) from None
    except (OSError, sqlite3.Error, ValueError, RuntimeError):
        raise BackupError(BackupReason.COPY_FAILED) from None
    finally:
        if staging is not None:
            with suppress(OSError):
                shutil.rmtree(staging)
