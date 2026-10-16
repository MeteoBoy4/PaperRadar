"""自包含备份创建与只读完整性校验;帮助导入不加载数据库模块。"""

from pathlib import Path

from paper_radar.backup.manifest import (
    BackupError,
    BackupManifest,
    BackupReason,
    BackupResult,
)

__all__ = [
    "BackupError",
    "BackupManifest",
    "BackupReason",
    "BackupResult",
    "copy_verified_contents",
    "create_backup",
    "verify_backup",
    "verify_contents",
]


def create_backup(database: Path, data_root: Path, output: Path) -> BackupResult:
    from paper_radar.backup.service import create_backup as create

    return create(database, data_root, output)


def verify_backup(batch_dir: Path) -> BackupResult:
    from paper_radar.backup.service import verify_backup as verify

    return verify(batch_dir)


def verify_contents(root: Path, manifest: BackupManifest) -> None:
    from paper_radar.backup.service import verify_contents as verify

    verify(root, manifest)


def copy_verified_contents(result: BackupResult, destination: Path) -> None:
    from paper_radar.backup.service import copy_verified_contents as copy

    copy(result, destination)
