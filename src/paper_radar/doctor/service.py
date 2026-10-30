"""复用存储权威。诊断不运行程序或写入事实。"""

import stat
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from paper_radar.storage.database import (
    DatabaseMode,
    current_revision,
    open_database,
    require_current_revision,
)
from paper_radar.storage.errors import StorageError, StorageReason


class Result(StrEnum):
    MISSING = "missing"
    INVALID = "invalid"
    PASSED = "passed"
    NOT_ASSESSED = "not_assessed"


@dataclass(frozen=True)
class Check:
    name: str
    result: Result
    reason: str
    next_step: str


def basic_checks(database: Path) -> tuple[Check, ...]:
    try:
        current_revision()
    except StorageError as error:
        return (Check("package", Result.INVALID, error.reason.value, str(error)),)
    checks = [Check("package", Result.PASSED, "head_readable", "随包迁移可读。")]
    try:
        try:
            mode = database.stat().st_mode
        except FileNotFoundError:
            pass  # 缺失仍由存储权威产生受控原因。
        else:
            if not stat.S_ISREG(mode):
                raise OSError
        engine = open_database(database, mode=DatabaseMode.READ_ONLY)
        try:
            require_current_revision(engine)
        finally:
            engine.dispose()
    except OSError:
        checks.append(
            Check(
                "database",
                Result.INVALID,
                StorageReason.DATABASE_UNREADABLE.value,
                "数据库路径无法读取；请检查文件类型和读取权限。",
            )
        )
    except StorageError as error:
        result = (
            Result.MISSING
            if error.reason
            in {
                StorageReason.DATABASE_MISSING,
                StorageReason.DATABASE_UNINITIALIZED,
                StorageReason.UPGRADE_REQUIRED,
            }
            else Result.INVALID
        )
        checks.append(Check("database", result, error.reason.value, str(error)))
    else:
        checks.append(
            Check("database", Result.PASSED, "current_revision", "无需升级。")
        )
    return tuple(checks)
