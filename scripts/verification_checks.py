"""验收共享原语; 不定义任何组的范围、失败原因或通过声明。"""

from __future__ import annotations

import importlib.metadata
import json
import sqlite3
import sys
import tempfile
from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from typing import Any

from scripts.offline_evidence import CheckStatus, file_sha256
from scripts.verification_identity import RunIdentity


class ReceiptCounter(StrEnum):
    COLLECTED = "collected"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    DESELECTED = "deselected"
    INCOMPLETE = "incomplete"


RECEIPT_COUNTERS = tuple(ReceiptCounter)


def environment_versions(dependencies: tuple[str, ...]) -> dict[str, Any]:
    """采集明确范围的实际版本; 缺项由调用组映射为自己的受控原因。"""
    versions: dict[str, str | None] = {}
    for name in dependencies:
        try:
            version = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            version = None
        versions[name] = (
            version if isinstance(version, str) and version.strip() else None
        )
    return {
        "python": sys.version.split()[0],
        "sqlite": sqlite3.sqlite_version,
        "dependencies": versions,
    }


def migrated_revision(*, temp_prefix: str) -> str | None:
    """在真实临时库迁移并核对唯一 head; 异常分类与登记版本由调用组维护。"""
    from paper_radar.storage.database import (
        DatabaseMode,
        current_revision,
        open_database,
        upgrade_database,
    )

    with tempfile.TemporaryDirectory(prefix=temp_prefix) as directory:
        database = Path(directory) / "acceptance.sqlite3"
        upgrade_database(database)
        engine = open_database(database, mode=DatabaseMode.READ_ONLY)
        try:
            with engine.connect() as connection:
                revisions = (
                    connection.exec_driver_sql(
                        "SELECT version_num FROM alembic_version"
                    )
                    .scalars()
                    .all()
                )
        finally:
            engine.dispose()
        if len(revisions) != 1 or revisions[0] != current_revision():
            return None
        return str(revisions[0])


def read_json(path: Path) -> dict[str, Any] | None:
    """读取对象型 JSON; 缺失、不可读及非对象均不提供可接受材料。"""
    try:
        value = json.loads(path.read_bytes())
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def same_run_document(
    path: Path, run_id: str, suffix: str, returned: Mapping[str, Any]
) -> bool:
    """核对同次文件名、内容身份以及写出器返回值。"""
    return (
        path.name == f"{run_id}{suffix}"
        and returned.get("run_id") == run_id
        and read_json(path) == returned
    )


def file_records(
    root: Path, required: tuple[tuple[str, str], ...]
) -> list[dict[str, Any]]:
    """按显式清单核对固定字节; 空清单是否允许由调用组决定。"""
    records = []
    for relative, expected in required:
        actual = file_sha256(root / relative)
        records.append(
            {
                "path": relative,
                "expected_sha256": expected,
                "actual_sha256": actual,
                "result": CheckStatus.PASSED.value
                if actual == expected
                else CheckStatus.FAILED.value,
            }
        )
    return records


def receipt_completed(receipt: Mapping[str, Any], run_id: str) -> bool:
    """回执头必须来自同次实际完成的成功执行; 布尔值不是退出码。"""
    return (
        receipt.get("format_version") == 1
        and receipt.get("run_id") == run_id
        and receipt.get("completed") is True
        and type(receipt.get("exit_code")) is int
        and receipt.get("exit_code") == 0
    )


def receipt_records(
    modules: Mapping[str, Any],
    expected_cases: Mapping[str, int | None],
) -> list[dict[str, Any]]:
    """核对显式模块计数; 只允许完整收集和通过, 其余计数必须为零。"""
    records = []
    for name in sorted(expected_cases):
        raw = modules.get(name)
        if not isinstance(raw, dict):
            raw = {}
        counts: dict[str, int | None] = {
            key: raw.get(key) if type(raw.get(key)) is int and raw[key] >= 0 else None
            for key in RECEIPT_COUNTERS
        }
        expected = expected_cases[name]
        expected_counts: dict[str, int | None] = {
            key: expected if key in ("collected", "passed") else 0
            for key in RECEIPT_COUNTERS
        }
        passed = type(expected) is int and expected > 0 and counts == expected_counts
        records.append(
            {
                "path": name,
                "expected_cases": expected,
                **counts,
                "result": CheckStatus.PASSED.value
                if passed
                else CheckStatus.FAILED.value,
            }
        )
    return records


def identity_matches(
    current: RunIdentity,
    evidence: Mapping[str, Any],
    *conclusions: Mapping[str, Any],
) -> bool:
    """运行身份完整且与证据及前置结论一致。#12 证据没有工作树哈希。"""
    return (
        current.code["commit"] is not None
        and current.code["dirty"] is not None
        and current.worktree_sha256 is not None
        and current.lockfile_sha256 is not None
        and evidence.get("code") == current.code
        and evidence.get("lockfile_sha256") == current.lockfile_sha256
        and all(
            conclusion.get("code") == current.code
            and conclusion.get("worktree_sha256") == current.worktree_sha256
            and conclusion.get("lockfile_sha256") == current.lockfile_sha256
            for conclusion in conclusions
        )
    )


def files_unchanged(bindings: tuple[tuple[Path, str | None], ...]) -> bool:
    """发布前复核已捕获的字节身份; 材料缺失的责任仍由各组判据承担。"""
    return all(file_sha256(path) == expected for path, expected in bindings)
