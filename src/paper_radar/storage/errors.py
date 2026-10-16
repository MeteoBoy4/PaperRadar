"""存储边界的受控错误。"""

from enum import StrEnum


class StorageReason(StrEnum):
    DATABASE_MISSING = "database_missing"
    DATABASE_UNINITIALIZED = "database_uninitialized"
    UPGRADE_REQUIRED = "upgrade_required"
    UNKNOWN_REVISION = "unknown_revision"
    PACKAGE_MIGRATIONS_INVALID = "package_migrations_invalid"
    DATABASE_REVISION_CORRUPT = "database_revision_corrupt"
    DATABASE_UNREADABLE = "database_unreadable"
    UPGRADE_FAILED = "upgrade_failed"
    WAL_UNAVAILABLE = "wal_unavailable"
    STORAGE_FAILED = "storage_failed"


class StorageError(Exception):
    """可由应用服务安全展示的存储错误。"""

    def __init__(
        self, message: str, *, reason: StorageReason = StorageReason.STORAGE_FAILED
    ) -> None:
        self.reason: StrEnum = reason
        super().__init__(message)
