"""冻结契约快照的只读漂移检查。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from paper_radar.contracts.schema import (
    ContractName,
    ContractSelectionError,
    ContractVersion,
    FrozenContract,
    build_selected_contract,
)
from paper_radar.contracts.snapshot import (
    SnapshotInspection,
    SnapshotPathError,
    SnapshotPathProblem,
    inspect_frozen_snapshot,
    resolve_snapshot_directory,
)


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


class ContractCheckError(ValueError):
    """冻结契约检查未通过。消息为脱敏的中文操作指引。"""

    def __init__(
        self,
        category: ContractCheckErrorCategory,
        message_zh: str,
    ) -> None:
        self.category = category
        super().__init__(message_zh)


@dataclass(frozen=True, slots=True)
class ContractCheckResult:
    """一致快照的契约身份和磁盘位置。"""

    name: ContractName
    version: ContractVersion
    snapshot_dir: Path
    schema_sha256: str


_PATH_FAILURE_CATEGORIES: dict[SnapshotPathProblem, ContractCheckErrorCategory] = {
    SnapshotPathProblem.INVALID_TARGET: ContractCheckErrorCategory.INVALID_TARGET,
    SnapshotPathProblem.PATH_ESCAPE: ContractCheckErrorCategory.PATH_ESCAPE,
}


def _identity(contract: FrozenContract) -> str:
    return f"{contract.name.value} {contract.version.value}"


def _snapshot_failure(
    inspection: SnapshotInspection,
    contract: FrozenContract,
    snapshot_dir: Path,
) -> tuple[ContractCheckErrorCategory, str]:
    identity = _identity(contract)
    if inspection is SnapshotInspection.ABSENT:
        return (
            ContractCheckErrorCategory.MISSING_SNAPSHOT,
            f"契约 {identity} 的冻结快照缺失：{snapshot_dir}；"
            "请确认 --target、--contract 和 --version，并先运行 contracts export。",
        )
    if inspection is SnapshotInspection.INCOMPLETE:
        return (
            ContractCheckErrorCategory.MISSING_SNAPSHOT,
            f"契约 {identity} 的冻结快照不完整（缺少 "
            f"{contract.schema_filename} 或 {contract.manifest_filename}）："
            f"{snapshot_dir}；请从版本控制恢复完整快照，不要手工补齐。",
        )
    if inspection is SnapshotInspection.UNREADABLE:
        return (
            ContractCheckErrorCategory.UNREADABLE_SNAPSHOT,
            f"契约 {identity} 的冻结快照不可读取：{snapshot_dir}；"
            "请检查文件权限和文件系统状态后重试。",
        )
    if inspection is SnapshotInspection.DAMAGED:
        return (
            ContractCheckErrorCategory.DAMAGED_SNAPSHOT,
            f"契约 {identity} 的冻结快照损坏或格式不规范：{snapshot_dir}；"
            "请从版本控制恢复该快照；契约变化应新建版本。",
        )
    if inspection is SnapshotInspection.VERSION_MISMATCH:
        return (
            ContractCheckErrorCategory.VERSION_MISMATCH,
            f"冻结快照的契约或版本信息与所选身份 {identity} 不一致：{snapshot_dir}；"
            "请核对 --contract 与 --version。",
        )
    if inspection is SnapshotInspection.CONTENT_DRIFT:
        return (
            ContractCheckErrorCategory.CONTENT_DRIFT,
            f"契约 {identity} 的冻结快照与当前权威 Schema 不一致（内容漂移）："
            f"{snapshot_dir}；若契约确已变化，请新建版本并导出新快照；"
            "否则恢复该快照。",
        )
    raise ValueError(f"一致状态不是失败：{inspection.value}")


def check_frozen_contract(
    name: ContractName | str,
    version: ContractVersion | str,
    target: Path | str,
) -> ContractCheckResult:
    """只读比较一份显式选择的冻结快照与当前权威定义。"""
    try:
        contract = build_selected_contract(name, version)
    except ContractSelectionError as error:
        raise ContractCheckError(
            ContractCheckErrorCategory.INVALID_SELECTION, str(error)
        ) from error

    identity = _identity(contract)
    root = Path(target)
    if os.path.lexists(root) and not root.is_dir():
        raise ContractCheckError(
            ContractCheckErrorCategory.INVALID_TARGET,
            f"契约 {identity} 的目标路径不是可访问目录；"
            "请把 --target 指向包含契约快照的目录。",
        )

    try:
        snapshot_dir = resolve_snapshot_directory(target, contract)
    except SnapshotPathError as error:
        raise ContractCheckError(
            _PATH_FAILURE_CATEGORIES[error.problem],
            f"契约 {identity} 检查失败：{error}",
        ) from error

    inspection = inspect_frozen_snapshot(snapshot_dir, contract)
    if inspection is not SnapshotInspection.MATCHED:
        category, message = _snapshot_failure(inspection, contract, snapshot_dir)
        raise ContractCheckError(category, message)

    return ContractCheckResult(
        name=contract.name,
        version=contract.version,
        snapshot_dir=snapshot_dir,
        schema_sha256=contract.schema_sha256,
    )
