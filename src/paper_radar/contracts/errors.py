"""冻结契约导出与检查的公开失败词汇。"""

from __future__ import annotations

from enum import StrEnum


class ContractExportErrorCategory(StrEnum):
    """契约导出的稳定失败类别。"""

    INVALID_SELECTION = "invalid_selection"
    DAMAGED_SNAPSHOT = "damaged_snapshot"
    VERSION_MISMATCH = "version_mismatch"
    CONTENT_CONFLICT = "content_conflict"
    INVALID_TARGET = "invalid_target"
    PATH_ESCAPE = "path_escape"
    WRITE_FAILED = "write_failed"


class ContractCheckErrorCategory(StrEnum):
    """契约只读检查的稳定失败类别。"""

    INVALID_SELECTION = "invalid_selection"
    MISSING_SNAPSHOT = "missing_snapshot"
    UNREADABLE_SNAPSHOT = "unreadable_snapshot"
    DAMAGED_SNAPSHOT = "damaged_snapshot"
    VERSION_MISMATCH = "version_mismatch"
    CONTENT_DRIFT = "content_drift"
    INVALID_TARGET = "invalid_target"
    PATH_ESCAPE = "path_escape"


class ContractExportError(ValueError):
    """无法安全完成契约导出。消息不包含底层异常或文件内容。"""

    def __init__(
        self,
        category: ContractExportErrorCategory,
        message_zh: str,
    ) -> None:
        self.category = category
        super().__init__(message_zh)


class ContractCheckError(ValueError):
    """冻结契约检查未通过。消息为脱敏的中文操作指引。"""

    def __init__(
        self,
        category: ContractCheckErrorCategory,
        message_zh: str,
    ) -> None:
        self.category = category
        super().__init__(message_zh)
