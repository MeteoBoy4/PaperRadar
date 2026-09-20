"""冻结契约快照的只读状态检查与目标路径解析。"""

from __future__ import annotations

import errno
import hashlib
import json
import os
from enum import StrEnum
from pathlib import Path
from typing import NoReturn

from paper_radar.contracts.schema import (
    _MANIFEST_FORMAT_VERSION,
    FrozenContract,
    _canonical_json_bytes,
    _ManifestField,
)


class SnapshotInspection(StrEnum):
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


class SnapshotPathProblem(StrEnum):
    """无法为所选契约构造目标快照路径的原因。"""

    INVALID_TARGET = "invalid_target"
    PATH_ESCAPE = "path_escape"


class SnapshotPathError(ValueError):
    """目标路径无法解析。消息为脱敏的中文操作指引。"""

    def __init__(self, problem: SnapshotPathProblem, message_zh: str) -> None:
        self.problem = problem
        super().__init__(message_zh)


class _UnavailableFile(Exception):
    """必需快照文件缺失或不可读取。"""

    def __init__(self, inspection: SnapshotInspection) -> None:
        self.inspection = inspection
        super().__init__(inspection.value)


def resolve_snapshot_directory(target: Path | str, contract: FrozenContract) -> Path:
    """把受控契约身份映射到目标根目录内的快照路径。不创建任何目录。"""
    try:
        root = Path(target).resolve(strict=False)
        snapshot_dir = root.joinpath(*contract.snapshot_parts)
        resolved_snapshot = snapshot_dir.resolve(strict=False)
    except (OSError, RuntimeError) as error:
        raise SnapshotPathError(
            SnapshotPathProblem.INVALID_TARGET,
            "目标目录无法解析；请检查访问权限和符号链接循环。",
        ) from error
    if not resolved_snapshot.is_relative_to(root):
        raise SnapshotPathError(
            SnapshotPathProblem.PATH_ESCAPE,
            "受控快照路径超出目标目录；请移除目标内指向外部的符号链接。",
        )
    return snapshot_dir


def _read_required_file(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except FileNotFoundError as error:
        raise _UnavailableFile(SnapshotInspection.INCOMPLETE) from error
    except OSError as error:
        raise _UnavailableFile(SnapshotInspection.UNREADABLE) from error


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


def _probe_snapshot_directory(snapshot_dir: Path) -> SnapshotInspection | None:
    """区分真正缺失、权限拒绝与无法解析的路径。返回非 None 表示无法继续。"""
    try:
        os.lstat(snapshot_dir)
    except FileNotFoundError:
        return SnapshotInspection.ABSENT
    except PermissionError:
        return SnapshotInspection.INACCESSIBLE
    except OSError as error:
        if error.errno in (errno.ELOOP, errno.ENOTDIR):
            return SnapshotInspection.INVALID_PATH
        return SnapshotInspection.INACCESSIBLE
    return None


def inspect_frozen_snapshot(
    snapshot_dir: Path,
    contract: FrozenContract,
) -> SnapshotInspection:
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
        return SnapshotInspection.DAMAGED

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
        return SnapshotInspection.DAMAGED

    expected_identity = {
        "name": contract.name.value,
        "version": contract.version.value,
    }
    if (
        manifest.get(_ManifestField.CONTRACT.value) != contract.name.value
        or manifest.get(_ManifestField.VERSION.value) != contract.version.value
        or schema.get("x-paper-radar-contract") != expected_identity
    ):
        return SnapshotInspection.VERSION_MISMATCH

    if schema_bytes != contract.schema_bytes:
        return SnapshotInspection.CONTENT_DRIFT

    return SnapshotInspection.MATCHED
