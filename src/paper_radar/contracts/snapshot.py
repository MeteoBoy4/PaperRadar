"""冻结契约快照的只读状态检查与目标路径解析。"""

from __future__ import annotations

import errno
import hashlib
import json
import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import NoReturn

from paper_radar.contracts.errors import (
    ContractCheckErrorCategory,
    ContractExportErrorCategory,
)
from paper_radar.contracts.schema import (
    _MANIFEST_FORMAT_VERSION,
    FrozenContract,
    _canonical_json_bytes,
    _ManifestField,
)


class _SnapshotInspection(StrEnum):
    """既有快照相对当前权威定义的稳定只读状态。"""

    ABSENT = "absent"
    INACCESSIBLE = "inaccessible"
    INVALID_PATH = "invalid_path"
    INCOMPLETE = "incomplete"
    UNREADABLE = "unreadable"
    DAMAGED = "damaged"
    VERSION_MISMATCH = "version_mismatch"
    CONTENT_DRIFT = "content_drift"
    MATCHED = "matched"


class _SnapshotPathProblem(StrEnum):
    """无法为所选契约构造目标快照路径的原因。"""

    INVALID_TARGET = "invalid_target"
    PATH_ESCAPE = "path_escape"


class _SnapshotPathError(ValueError):
    """目标路径无法解析。消息为脱敏的中文操作指引。"""

    def __init__(self, problem: _SnapshotPathProblem, message_zh: str) -> None:
        self.problem = problem
        super().__init__(message_zh)


class _UnavailableFile(Exception):
    """必需快照文件缺失或不可读取。"""

    def __init__(self, inspection: _SnapshotInspection) -> None:
        self.inspection = inspection
        super().__init__(inspection.value)


def _resolve_snapshot_directory(target: Path | str, contract: FrozenContract) -> Path:
    """把受控契约身份映射到目标根目录内的快照路径。不创建任何目录。"""
    try:
        root = Path(target).resolve(strict=False)
        snapshot_dir = root.joinpath(*contract.snapshot_parts)
        resolved_snapshot = snapshot_dir.resolve(strict=False)
    except (OSError, RuntimeError) as error:
        raise _SnapshotPathError(
            _SnapshotPathProblem.INVALID_TARGET,
            "目标目录无法解析；请检查访问权限和符号链接循环。",
        ) from error
    if not resolved_snapshot.is_relative_to(root):
        raise _SnapshotPathError(
            _SnapshotPathProblem.PATH_ESCAPE,
            "受控快照路径超出目标目录；请移除目标内指向外部的符号链接。",
        )
    return snapshot_dir


def _read_required_file(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except FileNotFoundError as error:
        raise _UnavailableFile(_SnapshotInspection.INCOMPLETE) from error
    except OSError as error:
        raise _UnavailableFile(_SnapshotInspection.UNREADABLE) from error


def _reject_json_constant(constant: str) -> NoReturn:
    raise ValueError(f"JSON 不接受常量：{constant}")


# 上限固定且远低于解释器整数转换的最小阈值。
# 因此整数位数判定不依赖 PYTHONINTMAXSTRDIGITS。
_MAX_JSON_INTEGER_DIGITS = 100


def _parse_json_integer(literal: str) -> int:
    digits = literal[1:] if literal.startswith("-") else literal
    if len(digits) > _MAX_JSON_INTEGER_DIGITS:
        raise ValueError("冻结契约不接受超长整数")
    return int(literal)


def _probe_snapshot_directory(snapshot_dir: Path) -> _SnapshotInspection | None:
    """区分真正缺失、权限拒绝与无法解析的路径。返回非 None 表示无法继续。"""
    try:
        os.lstat(snapshot_dir)
    except FileNotFoundError:
        return _SnapshotInspection.ABSENT
    except PermissionError:
        return _SnapshotInspection.INACCESSIBLE
    except OSError as error:
        if error.errno in (errno.ELOOP, errno.ENOTDIR):
            return _SnapshotInspection.INVALID_PATH
        return _SnapshotInspection.INACCESSIBLE
    return None


def _inspect_frozen_snapshot(
    snapshot_dir: Path,
    contract: FrozenContract,
) -> _SnapshotInspection:
    """只读判定一份既有快照与当前权威定义的关系。从不修复或改写文件。"""
    probe_result = _probe_snapshot_directory(snapshot_dir)
    if probe_result is not None:
        return probe_result

    try:
        schema_bytes = _read_required_file(snapshot_dir / contract.schema_filename)
        manifest_bytes = _read_required_file(snapshot_dir / contract.manifest_filename)
    except _UnavailableFile as unavailable:
        return unavailable.inspection

    try:
        schema = json.loads(
            schema_bytes,
            parse_constant=_reject_json_constant,
            parse_int=_parse_json_integer,
        )
        manifest = json.loads(
            manifest_bytes,
            parse_constant=_reject_json_constant,
            parse_int=_parse_json_integer,
        )
        schema_canonical = _canonical_json_bytes(schema)
        manifest_canonical = _canonical_json_bytes(manifest)
    except (ValueError, RecursionError):
        # 不完整编码、超长整数、非标准常量和过深嵌套都算损坏。不向外泄漏异常。
        return _SnapshotInspection.DAMAGED

    if (
        not isinstance(schema, dict)
        or not isinstance(manifest, dict)
        or schema_canonical != schema_bytes
        or manifest_canonical != manifest_bytes
        or set(manifest) != {field.value for field in _ManifestField}
        or manifest.get(_ManifestField.FORMAT_VERSION.value) != _MANIFEST_FORMAT_VERSION
        or manifest.get(_ManifestField.SCHEMA_FILE.value) != contract.schema_filename
        or not isinstance(manifest.get(_ManifestField.SCHEMA_SHA256.value), str)
        or hashlib.sha256(schema_bytes).hexdigest()
        != manifest.get(_ManifestField.SCHEMA_SHA256.value)
    ):
        return _SnapshotInspection.DAMAGED

    expected_identity = {
        "name": contract.name.value,
        "version": contract.version.value,
    }
    if (
        manifest.get(_ManifestField.CONTRACT.value) != contract.name.value
        or manifest.get(_ManifestField.VERSION.value) != contract.version.value
        or schema.get("x-paper-radar-contract") != expected_identity
    ):
        return _SnapshotInspection.VERSION_MISMATCH

    if schema_bytes != contract.schema_bytes:
        return _SnapshotInspection.CONTENT_DRIFT

    return _SnapshotInspection.MATCHED


class ExportRelation(StrEnum):
    MATCHED = "matched"
    ABSENT = "absent"


@dataclass(frozen=True, slots=True)
class ExportReady:
    relation: ExportRelation
    snapshot_dir: Path


@dataclass(frozen=True, slots=True)
class ExportBlocked:
    category: ContractExportErrorCategory
    guidance_zh: str


@dataclass(frozen=True, slots=True)
class CheckReady:
    snapshot_dir: Path


@dataclass(frozen=True, slots=True)
class CheckBlocked:
    category: ContractCheckErrorCategory
    guidance_zh: str


@dataclass(frozen=True, slots=True)
class _PathFailureCategories:
    export: ContractExportErrorCategory
    check: ContractCheckErrorCategory


_PATH_FAILURE_CATEGORIES: dict[_SnapshotPathProblem, _PathFailureCategories] = {
    _SnapshotPathProblem.INVALID_TARGET: _PathFailureCategories(
        export=ContractExportErrorCategory.INVALID_TARGET,
        check=ContractCheckErrorCategory.INVALID_TARGET,
    ),
    _SnapshotPathProblem.PATH_ESCAPE: _PathFailureCategories(
        export=ContractExportErrorCategory.PATH_ESCAPE,
        check=ContractCheckErrorCategory.PATH_ESCAPE,
    ),
}

_DAMAGED_SNAPSHOT_FAILURE = (
    ContractExportErrorCategory.DAMAGED_SNAPSHOT,
    "既有冻结契约损坏或不完整，拒绝覆盖；请恢复原快照，契约变化应新建版本。",
)

_EXISTING_SNAPSHOT_FAILURES: dict[
    _SnapshotInspection, tuple[ContractExportErrorCategory, str]
] = {
    _SnapshotInspection.INACCESSIBLE: (
        ContractExportErrorCategory.WRITE_FAILED,
        "目标目录不可访问；请检查目录权限后重试。",
    ),
    _SnapshotInspection.INVALID_PATH: (
        ContractExportErrorCategory.INVALID_TARGET,
        "目标路径包含非目录项或符号链接循环；请选择有效的目标目录。",
    ),
    _SnapshotInspection.INCOMPLETE: _DAMAGED_SNAPSHOT_FAILURE,
    _SnapshotInspection.UNREADABLE: _DAMAGED_SNAPSHOT_FAILURE,
    _SnapshotInspection.DAMAGED: _DAMAGED_SNAPSHOT_FAILURE,
    _SnapshotInspection.VERSION_MISMATCH: (
        ContractExportErrorCategory.VERSION_MISMATCH,
        "既有冻结契约的契约或版本信息不一致，拒绝覆盖；请核对选择，契约变化应新建版本。",
    ),
    _SnapshotInspection.CONTENT_DRIFT: (
        ContractExportErrorCategory.CONTENT_CONFLICT,
        "同一声明版本已经存在不同内容，请新建版本。",
    ),
}


def _identity(contract: FrozenContract) -> str:
    return f"{contract.name.value} {contract.version.value}"


def _check_snapshot_failure(
    inspection: _SnapshotInspection,
    contract: FrozenContract,
    snapshot_dir: Path,
) -> tuple[ContractCheckErrorCategory, str]:
    identity = _identity(contract)
    if inspection is _SnapshotInspection.ABSENT:
        return (
            ContractCheckErrorCategory.MISSING_SNAPSHOT,
            f"契约 {identity} 的冻结快照缺失：{snapshot_dir}；"
            "请确认 --target、--contract 和 --version，并先运行 contracts export。",
        )
    if inspection is _SnapshotInspection.INCOMPLETE:
        return (
            ContractCheckErrorCategory.MISSING_SNAPSHOT,
            f"契约 {identity} 的冻结快照不完整（缺少 "
            f"{contract.schema_filename} 或 {contract.manifest_filename}）："
            f"{snapshot_dir}；请从版本控制恢复完整快照，不要手工补齐。",
        )
    if inspection is _SnapshotInspection.INVALID_PATH:
        return (
            ContractCheckErrorCategory.INVALID_TARGET,
            f"契约 {identity} 的目标快照路径无法解析（存在符号链接循环或非目录组件）："
            f"{snapshot_dir}；请核对 --target 后重试。",
        )
    if inspection is _SnapshotInspection.INACCESSIBLE:
        return (
            ContractCheckErrorCategory.UNREADABLE_SNAPSHOT,
            f"契约 {identity} 的冻结快照路径不可读取：{snapshot_dir}；"
            "请检查目录权限和文件系统状态后重试。",
        )
    if inspection is _SnapshotInspection.UNREADABLE:
        return (
            ContractCheckErrorCategory.UNREADABLE_SNAPSHOT,
            f"契约 {identity} 的冻结快照不可读取：{snapshot_dir}；"
            "请检查文件权限和文件系统状态后重试。",
        )
    if inspection is _SnapshotInspection.DAMAGED:
        return (
            ContractCheckErrorCategory.DAMAGED_SNAPSHOT,
            f"契约 {identity} 的冻结快照损坏或格式不规范：{snapshot_dir}；"
            "请从版本控制恢复该快照；契约变化应新建版本。",
        )
    if inspection is _SnapshotInspection.VERSION_MISMATCH:
        return (
            ContractCheckErrorCategory.VERSION_MISMATCH,
            f"冻结快照的契约或版本信息与所选身份 {identity} 不一致：{snapshot_dir}；"
            "请核对 --contract 与 --version。",
        )
    return (
        ContractCheckErrorCategory.CONTENT_DRIFT,
        f"契约 {identity} 的冻结快照与当前权威 Schema 不一致（内容漂移）："
        f"{snapshot_dir}；若契约确已变化，请新建版本并导出新快照；"
        "否则恢复该快照。",
    )


def verdict_for_export(
    target: Path | str, contract: FrozenContract
) -> ExportReady | ExportBlocked:
    """只读判定导出能否复用快照或发布新快照。"""
    try:
        snapshot_dir = _resolve_snapshot_directory(target, contract)
    except _SnapshotPathError as error:
        return ExportBlocked(_PATH_FAILURE_CATEGORIES[error.problem].export, str(error))

    inspection = _inspect_frozen_snapshot(snapshot_dir, contract)
    if inspection is _SnapshotInspection.MATCHED:
        return ExportReady(ExportRelation.MATCHED, snapshot_dir)
    if inspection is _SnapshotInspection.ABSENT:
        return ExportReady(ExportRelation.ABSENT, snapshot_dir)
    category, guidance = _EXISTING_SNAPSHOT_FAILURES[inspection]
    return ExportBlocked(category, guidance)


def verdict_for_check(
    target: Path | str, contract: FrozenContract
) -> CheckReady | CheckBlocked:
    """只读判定既有快照是否与当前权威定义一致。"""
    identity = _identity(contract)
    root = Path(target)
    if os.path.lexists(root) and not root.is_dir():
        return CheckBlocked(
            ContractCheckErrorCategory.INVALID_TARGET,
            f"契约 {identity} 的目标路径不是可访问目录；"
            "请把 --target 指向包含契约快照的目录。",
        )
    try:
        snapshot_dir = _resolve_snapshot_directory(target, contract)
    except _SnapshotPathError as error:
        return CheckBlocked(
            _PATH_FAILURE_CATEGORIES[error.problem].check,
            f"契约 {identity} 检查失败：{error}",
        )

    inspection = _inspect_frozen_snapshot(snapshot_dir, contract)
    if inspection is _SnapshotInspection.MATCHED:
        return CheckReady(snapshot_dir)
    category, guidance = _check_snapshot_failure(inspection, contract, snapshot_dir)
    return CheckBlocked(category, guidance)
