"""复用备份校验与复制,向空隔离位置原子发布独立完整副本。"""

from __future__ import annotations

import errno
import os
import shutil
import tempfile
from contextlib import suppress
from pathlib import Path

from paper_radar.backup.files import sync_directory
from paper_radar.backup.manifest import BackupError
from paper_radar.backup.restore_contract import (
    RestoreError,
    RestoreReason,
    RestoreResult,
)
from paper_radar.backup.service import copy_verified_contents, verify_backup


def _require_empty_target(target: Path) -> None:
    if target.is_symlink():
        raise RestoreError(RestoreReason.TARGET_UNAVAILABLE)
    if target.exists():
        if not target.is_dir():
            raise RestoreError(RestoreReason.TARGET_UNAVAILABLE)
        if any(target.iterdir()):
            raise RestoreError(RestoreReason.TARGET_NOT_EMPTY)


def restore_backup(batch_dir: Path, target: Path) -> RestoreResult:
    """只消费已发布批次。父目录须存在;不升级、不激活、不续跑。"""
    staging: Path | None = None
    try:
        verified = verify_backup(batch_dir)
        # 不将目标自身符号链接隐藏在 resolve 内;父路径只解析一次。
        if target.is_symlink():
            raise RestoreError(RestoreReason.TARGET_UNAVAILABLE)
        destination = target.resolve()
        if (
            destination == verified.batch_dir
            or verified.batch_dir in destination.parents
        ):
            raise RestoreError(RestoreReason.TARGET_OVERLAP)
        parent = destination.parent
        if not parent.is_dir():
            raise RestoreError(RestoreReason.PARENT_UNAVAILABLE)
        _require_empty_target(destination)
        staging = Path(tempfile.mkdtemp(prefix=".restore-staging-", dir=parent))
        sync_directory(parent)
        copy_verified_contents(verified, staging)
        _require_empty_target(destination)
        try:
            # POSIX rename 可替换空目录,拒绝被并发占用的非空目录/文件/链接。
            os.rename(staging, destination)
        except OSError as error:
            if error.errno in (errno.EEXIST, errno.ENOTEMPTY):
                raise RestoreError(RestoreReason.TARGET_NOT_EMPTY) from None
            raise RestoreError(RestoreReason.PUBLICATION_FAILED) from None
        staging = None
        sync_directory(parent)
        return RestoreResult(destination, verified.manifest_sha256, verified.manifest)
    except RestoreError:
        raise
    except BackupError as error:
        raise RestoreError(error.reason) from None
    except KeyboardInterrupt:
        raise RestoreError(RestoreReason.INTERRUPTED) from None
    except (OSError, RuntimeError, ValueError):
        raise RestoreError(RestoreReason.COPY_FAILED) from None
    finally:
        if staging is not None:
            with suppress(OSError):
                shutil.rmtree(staging)
