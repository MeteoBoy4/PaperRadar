"""隔离恢复的纯结果与受控原因,不加载数据库或文件服务。"""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from paper_radar.backup.manifest import BackupError, BackupManifest, BackupReason


class RestoreReason(StrEnum):
    TARGET_UNAVAILABLE = "target_unavailable"
    TARGET_NOT_EMPTY = "target_not_empty"
    TARGET_OVERLAP = "target_overlap"
    PARENT_UNAVAILABLE = "parent_unavailable"
    COPY_FAILED = "restore_copy_failed"
    PUBLICATION_FAILED = "restore_publication_failed"
    INTERRUPTED = "restore_interrupted"


_GUIDANCE = {
    RestoreReason.TARGET_UNAVAILABLE: (
        "恢复目标不可用或为符号链接；请选择普通空目录或不存在的位置。"
    ),
    RestoreReason.TARGET_NOT_EMPTY: "恢复目标不是空目录；不会覆盖，请选择新的空目标。",
    RestoreReason.TARGET_OVERLAP: "恢复目标与备份批次重叠；请选择批次目录以外的位置。",
    RestoreReason.PARENT_UNAVAILABLE: "目标父目录不存在或不可用；请先创建可写父目录。",
    RestoreReason.COPY_FAILED: "恢复复制失败；请检查空间和权限，再向合适目标重试。",
    RestoreReason.PUBLICATION_FAILED: (
        "恢复发布失败；请检查同文件系统目录重命名支持和目标状态。"
    ),
    RestoreReason.INTERRUPTED: "恢复操作中断；请检查目标状态，未发布残留由人工处理。",
}


class RestoreError(Exception):
    def __init__(self, reason: RestoreReason | BackupReason) -> None:
        self.reason = reason
        message = (
            str(BackupError(reason))
            if isinstance(reason, BackupReason)
            else _GUIDANCE[reason]
        )
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class RestoreResult:
    target_dir: Path
    manifest_sha256: str
    manifest: BackupManifest
