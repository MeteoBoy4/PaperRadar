"""冻结契约的不可覆盖文件系统导出。"""

from __future__ import annotations

import errno
import os
import shutil
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from paper_radar.contracts.schema import (
    ContractName,
    ContractSelectionError,
    ContractVersion,
    FrozenContract,
    select_contracts,
)
from paper_radar.contracts.snapshot import (
    SnapshotInspection,
    SnapshotPathError,
    SnapshotPathProblem,
    inspect_frozen_snapshot,
    resolve_snapshot_directory,
)


class ExportOutcome(StrEnum):
    """契约导出的可观察结果。"""

    CREATED = "created"
    UNCHANGED = "unchanged"


@dataclass(frozen=True, slots=True)
class ContractExportResult:
    """成功导出的契约身份和磁盘位置。"""

    name: ContractName
    version: ContractVersion
    outcome: ExportOutcome
    snapshot_dir: Path
    schema_sha256: str


class ContractExportErrorCategory(StrEnum):
    """契约导出的稳定失败类别。"""

    INVALID_SELECTION = "invalid_selection"
    DAMAGED_SNAPSHOT = "damaged_snapshot"
    VERSION_MISMATCH = "version_mismatch"
    CONTENT_CONFLICT = "content_conflict"
    INVALID_TARGET = "invalid_target"
    PATH_ESCAPE = "path_escape"
    WRITE_FAILED = "write_failed"


class ContractExportError(ValueError):
    """无法安全完成契约导出。消息不包含底层异常或文件内容。"""

    def __init__(
        self,
        category: ContractExportErrorCategory,
        message_zh: str,
    ) -> None:
        self.category = category
        super().__init__(message_zh)


@dataclass(frozen=True, slots=True)
class ContractBatchExportFailure:
    """批量预检或发布中某一份契约的受控失败。"""

    name: ContractName
    category: ContractExportErrorCategory
    message_zh: str


class ContractBatchExportError(ContractExportError):
    """批量导出未完整成功并保留逐份报告所需的安全状态。"""

    def __init__(
        self,
        failures: tuple[ContractBatchExportFailure, ...],
        selected_names: tuple[ContractName, ...],
        version: ContractVersion,
        completed: tuple[ContractExportResult, ...],
    ) -> None:
        if not failures:
            raise ValueError("批量导出错误至少包含一项失败。")
        first_failure = failures[0]
        self.failures = failures
        self.selected_names = selected_names
        self.version = version
        self.completed = completed
        super().__init__(first_failure.category, first_failure.message_zh)


_DAMAGED_SNAPSHOT_FAILURE = (
    ContractExportErrorCategory.DAMAGED_SNAPSHOT,
    "既有冻结契约损坏或不完整，拒绝覆盖；请恢复原快照，契约变化应新建版本。",
)

_CREATION_ATTEMPT_INSPECTIONS = frozenset(
    {
        SnapshotInspection.ABSENT,
    }
)

_EXISTING_SNAPSHOT_FAILURES: dict[
    SnapshotInspection, tuple[ContractExportErrorCategory, str]
] = {
    SnapshotInspection.INACCESSIBLE: (
        ContractExportErrorCategory.WRITE_FAILED,
        "目标目录不可访问；请检查目录权限后重试。",
    ),
    SnapshotInspection.INVALID_PATH: (
        ContractExportErrorCategory.INVALID_TARGET,
        "目标路径包含非目录项或符号链接循环；请选择有效的目标目录。",
    ),
    SnapshotInspection.INCOMPLETE: _DAMAGED_SNAPSHOT_FAILURE,
    SnapshotInspection.UNREADABLE: _DAMAGED_SNAPSHOT_FAILURE,
    SnapshotInspection.DAMAGED: _DAMAGED_SNAPSHOT_FAILURE,
    SnapshotInspection.VERSION_MISMATCH: (
        ContractExportErrorCategory.VERSION_MISMATCH,
        "既有冻结契约的契约或版本信息不一致，拒绝覆盖；请核对选择，契约变化应新建版本。",
    ),
    SnapshotInspection.CONTENT_DRIFT: (
        ContractExportErrorCategory.CONTENT_CONFLICT,
        "同一声明版本已经存在不同内容，请新建版本。",
    ),
}

_PATH_FAILURE_CATEGORIES: dict[SnapshotPathProblem, ContractExportErrorCategory] = {
    SnapshotPathProblem.INVALID_TARGET: ContractExportErrorCategory.INVALID_TARGET,
    SnapshotPathProblem.PATH_ESCAPE: ContractExportErrorCategory.PATH_ESCAPE,
}


def _write_durable_file(path: Path, content: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_error(error: OSError) -> ContractExportError:
    category = ContractExportErrorCategory.WRITE_FAILED
    if error.errno == errno.ELOOP:
        return ContractExportError(
            ContractExportErrorCategory.INVALID_TARGET,
            "目标目录无法解析；请检查访问权限和符号链接循环。",
        )
    elif isinstance(error, PermissionError):
        guidance = "目标目录不可写；请检查目录权限后重试。"
    elif isinstance(error, NotADirectoryError):
        guidance = "目标路径包含非目录项；请选择有效的目标目录。"
    elif error.errno == errno.ENOSPC:
        guidance = "目标文件系统空间不足；请释放空间后重试。"
    elif error.errno == errno.EROFS:
        guidance = "目标文件系统只读；请选择可写目录。"
    else:
        guidance = "文件系统写入失败；请检查目标目录、可用空间和挂载状态后重试。"
    return ContractExportError(category, guidance)


def _create_snapshot(snapshot_dir: Path, contract: FrozenContract) -> None:
    snapshot_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(
        tempfile.mkdtemp(prefix=f".{contract.version.value}-", dir=snapshot_dir.parent)
    )
    try:
        _write_durable_file(
            staging_dir / contract.schema_filename,
            contract.schema_bytes,
        )
        _write_durable_file(
            staging_dir / contract.manifest_filename,
            contract.manifest_bytes,
        )
        _fsync_directory(staging_dir)
        os.replace(staging_dir, snapshot_dir)
        _fsync_directory(snapshot_dir.parent)
    finally:
        if staging_dir.exists():
            shutil.rmtree(staging_dir)


def _prepare_export(
    contract: FrozenContract,
    target: Path | str,
) -> tuple[Path, SnapshotInspection]:
    try:
        snapshot_dir = resolve_snapshot_directory(target, contract)
    except SnapshotPathError as error:
        raise ContractExportError(
            _PATH_FAILURE_CATEGORIES[error.problem], str(error)
        ) from error

    inspection = inspect_frozen_snapshot(snapshot_dir, contract)
    if inspection not in _CREATION_ATTEMPT_INSPECTIONS | {SnapshotInspection.MATCHED}:
        category, message = _EXISTING_SNAPSHOT_FAILURES[inspection]
        raise ContractExportError(category, message)
    return snapshot_dir, inspection


def _successful_result(
    contract: FrozenContract,
    outcome: ExportOutcome,
    snapshot_dir: Path,
) -> ContractExportResult:
    return ContractExportResult(
        name=contract.name,
        version=contract.version,
        outcome=outcome,
        snapshot_dir=snapshot_dir,
        schema_sha256=contract.schema_sha256,
    )


def _select_contracts(
    names: Iterable[ContractName | str],
    version: ContractVersion | str,
) -> tuple[FrozenContract, ...]:
    try:
        return select_contracts(names, version)
    except ContractSelectionError as error:
        raise ContractExportError(
            ContractExportErrorCategory.INVALID_SELECTION, str(error)
        ) from error


def _publish_prepared_contract(
    contract: FrozenContract,
    snapshot_dir: Path,
) -> ContractExportResult:
    try:
        _create_snapshot(snapshot_dir, contract)
    except OSError as error:
        raise _write_error(error) from error
    return _successful_result(contract, ExportOutcome.CREATED, snapshot_dir)


def export_frozen_contract(
    name: ContractName | str,
    version: ContractVersion | str,
    target: Path | str,
) -> ContractExportResult:
    """通过批量边界把一份已实现契约安全导出到目标根目录。"""
    try:
        return export_frozen_contracts((name,), version, target)[0]
    except ContractBatchExportError as error:
        raise ContractExportError(error.category, str(error)) from error


def _ordered_results(
    selected_names: tuple[ContractName, ...],
    results_by_name: dict[ContractName, ContractExportResult],
) -> tuple[ContractExportResult, ...]:
    return tuple(
        results_by_name[name] for name in selected_names if name in results_by_name
    )


def export_frozen_contracts(
    names: Iterable[ContractName | str],
    version: ContractVersion | str,
    target: Path | str,
) -> tuple[ContractExportResult, ...]:
    """预检后按声明顺序导出多份契约且不承诺跨快照事务。"""
    contracts = _select_contracts(names, version)
    selected_names = tuple(contract.name for contract in contracts)
    controlled_version = contracts[0].version
    prepared: list[tuple[FrozenContract, Path]] = []
    preflight_failures: list[ContractBatchExportFailure] = []
    results_by_name: dict[ContractName, ContractExportResult] = {}

    for contract in contracts:
        try:
            snapshot_dir, inspection = _prepare_export(contract, target)
        except ContractExportError as error:
            preflight_failures.append(
                ContractBatchExportFailure(
                    name=contract.name,
                    category=error.category,
                    message_zh=str(error),
                )
            )
            continue
        if inspection is SnapshotInspection.MATCHED:
            results_by_name[contract.name] = _successful_result(
                contract,
                ExportOutcome.UNCHANGED,
                snapshot_dir,
            )
        else:
            prepared.append((contract, snapshot_dir))

    if preflight_failures:
        raise ContractBatchExportError(
            failures=tuple(preflight_failures),
            selected_names=selected_names,
            version=controlled_version,
            completed=_ordered_results(selected_names, results_by_name),
        )

    for contract, snapshot_dir in prepared:
        try:
            results_by_name[contract.name] = _publish_prepared_contract(
                contract, snapshot_dir
            )
        except ContractExportError as error:
            raise ContractBatchExportError(
                failures=(
                    ContractBatchExportFailure(
                        name=contract.name,
                        category=error.category,
                        message_zh=str(error),
                    ),
                ),
                selected_names=selected_names,
                version=controlled_version,
                completed=_ordered_results(selected_names, results_by_name),
            ) from error

    return _ordered_results(selected_names, results_by_name)
