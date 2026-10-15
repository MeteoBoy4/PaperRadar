"""快照发现与引用解析的公共查询服务。不改变 load/diff 的身份契约。"""

import re
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from paper_radar.config.adapters import ADAPTER_NAME, SYSTEM_PROMPT_NAME
from paper_radar.config.compile import MaterialKind
from paper_radar.config.errors import ConfigError
from paper_radar.config.schema import PromptName, valid_declared_version
from paper_radar.config.snapshot_summary import ConfigSnapshotSummary, SnapshotVersion
from paper_radar.contracts import ContractName
from paper_radar.storage.database import (
    DatabaseMode,
    open_database,
    require_current_revision,
)
from paper_radar.storage.errors import StorageError
from paper_radar.storage.snapshot_queries import read_snapshot_ids, read_snapshot_index

_FULL_ID = re.compile(r"[0-9a-f]{64}")
_REFERENCE = re.compile(r"[0-9a-f]{8,64}")


def _short_references(ids: tuple[str, ...]) -> dict[str, str]:
    """排序邻居足以确定全库最长共享前缀。64 位时展示权威 ID。"""
    if any(not isinstance(item, str) or not _FULL_ID.fullmatch(item) for item in ids):
        raise ConfigError("快照索引身份损坏；请检查数据库")
    ordered = sorted(ids)
    references: dict[str, str] = {}
    for index, snapshot_id in enumerate(ordered):
        length = 8
        for neighbor in (
            ordered[max(0, index - 1) : index] + ordered[index + 1 : index + 2]
        ):
            common = 0
            for left, right in zip(snapshot_id, neighbor, strict=True):
                if left != right:
                    break
                common += 1
            length = max(length, common + 1)
        references[snapshot_id] = snapshot_id[:length]
    return references


def _version(kind: str, name: str, version: str) -> SnapshotVersion:
    controlled_kind = MaterialKind(kind)
    allowed: tuple[str, ...]
    if controlled_kind is MaterialKind.ADAPTER:
        allowed = (ADAPTER_NAME,)
    elif controlled_kind is MaterialKind.PROMPT:
        allowed = (*PromptName, SYSTEM_PROMPT_NAME)
    elif controlled_kind in (
        MaterialKind.CONTRACT_SCHEMA,
        MaterialKind.CONTRACT_MANIFEST,
    ):
        allowed = tuple(ContractName)
    else:
        allowed = (controlled_kind.value,)
    if name not in allowed:
        raise ValueError
    return SnapshotVersion(controlled_kind, name, valid_declared_version(version))


def _created_at(value: str | None) -> datetime | None:
    if value is None or value == "":
        return None
    created_at = datetime.fromisoformat(value)
    if created_at.tzinfo is None:
        raise ValueError
    return created_at.astimezone(UTC)


def list_config_snapshots(database: Path) -> tuple[ConfigSnapshotSummary, ...]:
    """只发现保存记录。不宣称快照完整性或启用状态已验证。"""
    try:
        engine = open_database(database, mode=DatabaseMode.READ_ONLY)
        try:
            require_current_revision(engine)
            records = read_snapshot_index(engine)
        finally:
            engine.dispose()
    except StorageError as error:
        raise ConfigError(str(error)) from None
    except SQLAlchemyError:
        raise ConfigError("数据库读取失败；请检查数据库状态") from None
    references = _short_references(tuple(record.snapshot_id for record in records))
    try:
        summaries = [
            ConfigSnapshotSummary(
                record.snapshot_id,
                references[record.snapshot_id],
                _created_at(record.created_at),
                tuple(_version(*version) for version in record.versions),
            )
            for record in records
        ]
    except (ValueError, TypeError, OverflowError):
        raise ConfigError("快照审计元数据或版本摘要损坏；请检查数据库") from None
    # 稳定排序保留完整 ID 升序的同时间/未记录项。
    summaries.sort(key=lambda summary: summary.snapshot_id)
    summaries.sort(
        key=lambda summary: (
            summary.created_at is not None,
            summary.created_at or datetime.min.replace(tzinfo=UTC),
        ),
        reverse=True,
    )
    return tuple(summaries)


def resolve_config_snapshot_reference(database: Path, reference: str) -> str:
    """仅解析索引身份。候选内容的完整性仍必须由 load/diff 验证。"""
    if not _REFERENCE.fullmatch(reference):
        raise ConfigError(
            "快照引用须为 8–63 位小写十六进制前缀或完整 64 位小写 ID；"
            "请从 config snapshots list 复制，不使用名称或别名"
        )
    try:
        engine = open_database(database, mode=DatabaseMode.READ_ONLY)
        try:
            require_current_revision(engine)
            ids = read_snapshot_ids(engine)
        finally:
            engine.dispose()
    except StorageError as error:
        raise ConfigError(str(error)) from None
    except SQLAlchemyError:
        raise ConfigError("数据库读取失败；请检查数据库状态") from None
    matches = [
        snapshot_id
        for snapshot_id in ids
        if isinstance(snapshot_id, str)
        and (
            snapshot_id == reference
            if len(reference) == 64
            else snapshot_id.startswith(reference)
        )
    ]
    if not matches:
        raise ConfigError("未找到快照；请核对数据库路径并运行 config snapshots list")
    if len(matches) > 1:
        raise ConfigError("快照前缀存在歧义；请补充字符或使用完整 64 位 ID")
    snapshot_id = matches[0]
    if not isinstance(snapshot_id, str) or not _FULL_ID.fullmatch(snapshot_id):
        raise ConfigError("快照索引身份损坏；请检查数据库")
    return snapshot_id
