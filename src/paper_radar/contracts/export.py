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
from typing import Literal

from paper_radar.contracts.errors import (
    ContractExportError,
    ContractExportErrorCategory,
)
from paper_radar.contracts.schema import (
    ContractName,
    ContractSelectionError,
    ContractVersion,
    FrozenContract,
    build_selected_contract,
    select_contracts,
)
from paper_radar.contracts.snapshot import (
    ExportBlocked,
    ExportReady,
    ExportRelation,
    verdict_for_export,
)


class ExportOutcome(StrEnum):
    """契约导出的可观察结果。"""

    CREATED = "created"
    UNCHANGED = "unchanged"
    FAILED = "failed"
    NOT_ATTEMPTED = "not_attempted"


@dataclass(frozen=True, slots=True)
class ContractExportResult:
    """成功导出的契约身份和磁盘位置。"""

    name: ContractName
    version: ContractVersion
    outcome: Literal[ExportOutcome.CREATED, ExportOutcome.UNCHANGED]
    snapshot_dir: Path
    schema_sha256: str


@dataclass(frozen=True, slots=True)
class ContractExportItemResult:
    """批量导出中一份契约的完整结果。"""

    name: ContractName
    version: ContractVersion
    outcome: ExportOutcome
    error_category: ContractExportErrorCategory | None
    message_zh: str
    snapshot_dir: Path | None
    schema_sha256: str | None


@dataclass(frozen=True, slots=True)
class ContractBatchExportResult:
    """按声明顺序排列的逐份导出结果。"""

    items: tuple[ContractExportItemResult, ...]

    @property
    def passed(self) -> bool:
        return bool(self.items) and all(
            item.outcome in (ExportOutcome.CREATED, ExportOutcome.UNCHANGED)
            for item in self.items
        )


_OUTCOME_MESSAGES_ZH = {
    ExportOutcome.CREATED: "已创建冻结契约",
    ExportOutcome.UNCHANGED: "冻结契约内容一致，未改写",
    ExportOutcome.NOT_ATTEMPTED: "批量导出已停止；修复上述问题后原命令重跑即可补齐。",
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


def _successful_result(
    contract: FrozenContract,
    outcome: Literal[ExportOutcome.CREATED, ExportOutcome.UNCHANGED],
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


def _export_ready_contract(
    contract: FrozenContract, ready: ExportReady
) -> ContractExportResult:
    if ready.relation is ExportRelation.MATCHED:
        return _successful_result(contract, ExportOutcome.UNCHANGED, ready.snapshot_dir)
    return _publish_prepared_contract(contract, ready.snapshot_dir)


def _completed_item(result: ContractExportResult) -> ContractExportItemResult:
    return ContractExportItemResult(
        name=result.name,
        version=result.version,
        outcome=result.outcome,
        error_category=None,
        message_zh=_OUTCOME_MESSAGES_ZH[result.outcome],
        snapshot_dir=result.snapshot_dir,
        schema_sha256=result.schema_sha256,
    )


def _failed_item(
    contract: FrozenContract,
    category: ContractExportErrorCategory,
    guidance_zh: str,
) -> ContractExportItemResult:
    return ContractExportItemResult(
        name=contract.name,
        version=contract.version,
        outcome=ExportOutcome.FAILED,
        error_category=category,
        message_zh=guidance_zh,
        snapshot_dir=None,
        schema_sha256=None,
    )


def _not_attempted_item(contract: FrozenContract) -> ContractExportItemResult:
    return ContractExportItemResult(
        name=contract.name,
        version=contract.version,
        outcome=ExportOutcome.NOT_ATTEMPTED,
        error_category=None,
        message_zh=_OUTCOME_MESSAGES_ZH[ExportOutcome.NOT_ATTEMPTED],
        snapshot_dir=None,
        schema_sha256=None,
    )


def export_frozen_contract(
    name: ContractName | str,
    version: ContractVersion | str,
    target: Path | str,
) -> ContractExportResult:
    """安全导出一份已实现契约到目标根目录。"""
    try:
        contract = build_selected_contract(name, version)
    except ContractSelectionError as error:
        raise ContractExportError(
            ContractExportErrorCategory.INVALID_SELECTION, str(error)
        ) from error
    verdict = verdict_for_export(target, contract)
    if isinstance(verdict, ExportBlocked):
        raise ContractExportError(verdict.category, verdict.guidance_zh)
    return _export_ready_contract(contract, verdict)


def export_frozen_contracts(
    names: Iterable[ContractName | str],
    version: ContractVersion | str,
    target: Path | str,
) -> ContractBatchExportResult:
    """预检后按声明顺序导出多份契约且不承诺跨快照事务。"""
    contracts = _select_contracts(names, version)
    prepared: list[tuple[FrozenContract, ExportReady]] = []
    items_by_name: dict[ContractName, ContractExportItemResult] = {}
    preflight_failed = False

    for contract in contracts:
        verdict = verdict_for_export(target, contract)
        if isinstance(verdict, ExportBlocked):
            items_by_name[contract.name] = _failed_item(
                contract, verdict.category, verdict.guidance_zh
            )
            preflight_failed = True
            continue
        if verdict.relation is ExportRelation.MATCHED:
            items_by_name[contract.name] = _completed_item(
                _export_ready_contract(contract, verdict)
            )
        else:
            prepared.append((contract, verdict))

    publish_stopped = preflight_failed
    for contract, ready in prepared:
        if publish_stopped:
            items_by_name[contract.name] = _not_attempted_item(contract)
            continue
        try:
            items_by_name[contract.name] = _completed_item(
                _export_ready_contract(contract, ready)
            )
        except ContractExportError as error:
            items_by_name[contract.name] = _failed_item(
                contract, error.category, str(error)
            )
            publish_stopped = True

    return ContractBatchExportResult(
        items=tuple(items_by_name[contract.name] for contract in contracts)
    )
