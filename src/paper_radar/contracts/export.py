"""冻结契约的不可覆盖文件系统导出。"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from paper_radar.contracts.schema import (
    ContractName,
    ContractVersion,
    FrozenContract,
    _canonical_json_bytes,
    build_frozen_contract,
)


class ExportOutcome(StrEnum):
    """契约导出的可观察结果。"""

    CREATED = "created"
    UNCHANGED = "unchanged"


@dataclass(frozen=True, slots=True)
class ContractExportResult:
    """成功导出的契约身份和磁盘位置。"""

    outcome: ExportOutcome
    snapshot_dir: Path
    schema_sha256: str


class ContractExportErrorCategory(StrEnum):
    """契约导出的稳定失败类别。"""

    INVALID_SELECTION = "invalid_selection"
    DAMAGED_SNAPSHOT = "damaged_snapshot"
    VERSION_MISMATCH = "version_mismatch"
    CONTENT_CONFLICT = "content_conflict"
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


def _snapshot_directory(root: Path, contract: FrozenContract) -> Path:
    snapshot_dir = root.joinpath(*contract.snapshot_parts)
    if not snapshot_dir.resolve(strict=False).is_relative_to(root):
        raise ContractExportError(
            ContractExportErrorCategory.PATH_ESCAPE,
            "导出路径超出目标目录。",
        )
    return snapshot_dir


def _existing_snapshot_is_unchanged(
    snapshot_dir: Path,
    contract: FrozenContract,
) -> bool:
    schema_path = snapshot_dir / contract.schema_filename
    manifest_path = snapshot_dir / contract.manifest_filename
    try:
        schema_bytes = schema_path.read_bytes()
        manifest_bytes = manifest_path.read_bytes()
    except OSError as error:
        raise ContractExportError(
            ContractExportErrorCategory.DAMAGED_SNAPSHOT,
            "既有冻结契约损坏或不完整，拒绝覆盖；请恢复原快照，契约变化应新建版本。",
        ) from error

    try:
        schema = json.loads(schema_bytes)
        manifest = json.loads(manifest_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ContractExportError(
            ContractExportErrorCategory.DAMAGED_SNAPSHOT,
            "既有冻结契约损坏或不完整，拒绝覆盖；请恢复原快照，契约变化应新建版本。",
        ) from error

    if (
        not isinstance(schema, dict)
        or not isinstance(manifest, dict)
        or _canonical_json_bytes(schema) != schema_bytes
        or _canonical_json_bytes(manifest) != manifest_bytes
        or set(manifest)
        != {
            "contract",
            "format_version",
            "schema_file",
            "schema_sha256",
            "version",
        }
        or manifest.get("format_version") != 1
        or manifest.get("schema_file") != contract.schema_filename
        or not isinstance(manifest.get("schema_sha256"), str)
        or hashlib.sha256(schema_bytes).hexdigest() != manifest.get("schema_sha256")
    ):
        raise ContractExportError(
            ContractExportErrorCategory.DAMAGED_SNAPSHOT,
            "既有冻结契约损坏或不完整，拒绝覆盖；请恢复原快照，契约变化应新建版本。",
        )

    schema_identity = schema.get("x-paper-radar-contract")
    expected_identity = {
        "name": contract.name.value,
        "version": contract.version.value,
    }
    if (
        manifest.get("contract") != contract.name.value
        or manifest.get("version") != contract.version.value
        or schema_identity != expected_identity
    ):
        raise ContractExportError(
            ContractExportErrorCategory.VERSION_MISMATCH,
            "既有冻结契约的契约或版本信息不一致，拒绝覆盖；请核对选择，契约变化应新建版本。",
        )

    if schema_bytes != contract.schema_bytes:
        raise ContractExportError(
            ContractExportErrorCategory.CONTENT_CONFLICT,
            "同一声明版本已经存在不同内容，请新建版本。",
        )
    return True


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


def export_frozen_contract(
    name: ContractName | str,
    version: ContractVersion | str,
    target: Path | str,
) -> ContractExportResult:
    """把一份已实现契约安全导出到目标根目录。"""
    try:
        controlled_name = ContractName(name)
        controlled_version = ContractVersion(version)
        contract = build_frozen_contract(controlled_name, controlled_version)
    except (KeyError, ValueError) as error:
        raise ContractExportError(
            ContractExportErrorCategory.INVALID_SELECTION,
            "未知契约或无效声明版本。",
        ) from error

    root = Path(target).resolve(strict=False)
    snapshot_dir = _snapshot_directory(root, contract)
    if os.path.lexists(snapshot_dir):
        if _existing_snapshot_is_unchanged(snapshot_dir, contract):
            return ContractExportResult(
                outcome=ExportOutcome.UNCHANGED,
                snapshot_dir=snapshot_dir,
                schema_sha256=contract.schema_sha256,
            )
        raise AssertionError("既有快照检查必须返回未改变或抛出受控异常")

    try:
        _create_snapshot(snapshot_dir, contract)
    except OSError as error:
        raise ContractExportError(
            ContractExportErrorCategory.WRITE_FAILED,
            "冻结契约写入失败，未发布新快照。",
        ) from error

    return ContractExportResult(
        outcome=ExportOutcome.CREATED,
        snapshot_dir=snapshot_dir,
        schema_sha256=contract.schema_sha256,
    )
