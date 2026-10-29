"""备份清单 v1 的纯格式、闭包身份和汇总规则。"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from paper_radar.storage.artifact_contract import (
    ArtifactMember,
    ArtifactRecord,
    BlobRecord,
    artifact_manifest,
    blob_relative_path,
    require_sha256,
)
from paper_radar.storage.errors import StorageError

BACKUP_FORMAT_VERSION = 1
BACKUP_DATABASE_REVISION = "feed02_title_language"
DATABASE_FILE = "database.sqlite3"
MANIFEST_FILE = "manifest.json"
BATCH_ID = re.compile(r"[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}\Z")


class BackupReason(StrEnum):
    BATCH_UNAVAILABLE = "batch_unavailable"
    NOT_PUBLISHED = "not_published"
    INVALID_MANIFEST = "invalid_manifest"
    UNSUPPORTED_FORMAT = "unsupported_format"
    UNSUPPORTED_REVISION = "unsupported_revision"
    UPGRADE_REQUIRED = "upgrade_required"
    UNSAFE_PATH = "unsafe_path"
    UNEXPECTED_ENTRY = "unexpected_entry"
    FILE_MISSING = "file_missing"
    FILE_CORRUPT = "file_corrupt"
    DATABASE_INVALID = "database_invalid"
    REGISTRATION_INVALID = "registration_invalid"
    CONFIG_INVALID = "config_invalid"
    SUPPLY_INVALID = "supply_invalid"
    OUTPUT_INVALID = "output_invalid"
    BATCH_EXISTS = "batch_exists"
    INTERRUPTED = "interrupted"
    COPY_FAILED = "copy_failed"
    PUBLICATION_FAILED = "publication_failed"


_GUIDANCE = {
    BackupReason.SUPPLY_INVALID: (
        "固定供给事实无法完整回放；请检查材料和 D5 引用，不会安装或联网。"
    ),
    BackupReason.INTERRUPTED: "备份操作中断；请重新创建或校验完整批次。",
    BackupReason.BATCH_UNAVAILABLE: "批次目录无法读取；请检查已发布批次的位置和权限。",
    BackupReason.NOT_PUBLISHED: "目录不是已发布备份批次；请使用完成批次目录。",
    BackupReason.INVALID_MANIFEST: "备份清单无效或与登记不符；请保留原批次并重新备份。",
    BackupReason.UNSUPPORTED_FORMAT: "备份格式不受支持；请使用匹配版本的程序。",
    BackupReason.UNSUPPORTED_REVISION: "数据库版本不受支持；请使用匹配版本的程序。",
    BackupReason.UPGRADE_REQUIRED: (
        "数据库为已知旧版本；请先运行 paper-radar db upgrade。"
    ),
    BackupReason.UNSAFE_PATH: "受控路径或权限不安全；请检查符号链接和属主访问权限。",
    BackupReason.UNEXPECTED_ENTRY: "批次包含清单外条目；请保留原批次并检查完整性。",
    BackupReason.FILE_MISSING: "批次成员缺失；请检查完整批次，校验不会补写文件。",
    BackupReason.FILE_CORRUPT: "成员长度、SHA-256 或权限不符；请检查原数据或完整批次。",
    BackupReason.DATABASE_INVALID: "数据库完整性或外键校验失败；请检查数据库。",
    BackupReason.REGISTRATION_INVALID: "制品登记闭包损坏；请检查原数据或完整批次。",
    BackupReason.CONFIG_INVALID: (
        "历史配置无法完整回放；请检查配置登记，不会读取配置树。"
    ),
    BackupReason.OUTPUT_INVALID: (
        "输出根不可用；请提供可写目录，避开本数据根的 blobs 和 tmp。"
    ),
    BackupReason.BATCH_EXISTS: "批次位置已存在；不会覆盖，请重新创建新批次。",
    BackupReason.COPY_FAILED: "备份复制失败；请检查空间、文件和权限后重试。",
    BackupReason.PUBLICATION_FAILED: (
        "批次发布失败；需要同文件系统原子不覆盖目录发布支持。"
    ),
}


class BackupError(Exception):
    def __init__(self, reason: BackupReason) -> None:
        self.reason = reason
        super().__init__(_GUIDANCE[reason])


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class FileEntry(_StrictModel):
    path: str
    sha256: str
    size_bytes: int = Field(ge=0)

    @model_validator(mode="after")
    def identity(self) -> Self:
        require_sha256(self.sha256)
        return self


class BackupArtifact(_StrictModel):
    artifact_id: str
    kind: str
    format_version: int
    members: tuple[ArtifactMember, ...]
    created_at: str

    @model_validator(mode="after")
    def identity(self) -> Self:
        manifest = artifact_manifest(self.kind, self.members)
        if self.format_version != 1 or self.artifact_id != manifest.artifact_id:
            raise ValueError("制品身份或格式不一致")
        if tuple(sorted(self.members, key=lambda member: member.role)) != self.members:
            raise ValueError("成员次序不规范")
        audit = datetime.fromisoformat(self.created_at)
        if audit.tzinfo is None:
            raise ValueError("审计时间缺时区")
        return self


class KindCount(_StrictModel):
    artifacts: int = Field(ge=0)
    members: int = Field(ge=0)
    size_bytes: int = Field(ge=0)


class Counts(_StrictModel):
    blobs: int = Field(ge=0)
    artifacts: int = Field(ge=0)
    config_snapshots: int = Field(ge=0)
    blob_bytes: int = Field(ge=0)
    by_kind: dict[str, KindCount]


class CodeIdentity(_StrictModel):
    package_version: str
    migration_revision: str
    backup_format_version: int
    artifact_format_version: int
    blob_layout_version: int
    sqlite_version: str
    git_commit: Literal[None]


class BackupManifest(_StrictModel):
    format_version: int
    batch_id: str
    created_at: str
    database_revision: str
    artifact_format_version: int
    blob_layout_version: int
    database: FileEntry
    blobs: tuple[FileEntry, ...]
    artifacts: tuple[BackupArtifact, ...]
    snapshot_ids: tuple[str, ...]
    counts: Counts
    code: CodeIdentity

    @model_validator(mode="after")
    def structure(self) -> Self:
        if (
            self.format_version != BACKUP_FORMAT_VERSION
            or self.artifact_format_version != 1
            or self.blob_layout_version != 1
            or self.code.backup_format_version != self.format_version
            or self.code.artifact_format_version != self.artifact_format_version
            or self.code.blob_layout_version != self.blob_layout_version
        ):
            raise BackupError(BackupReason.UNSUPPORTED_FORMAT)
        if not BATCH_ID.fullmatch(self.batch_id):
            raise ValueError("批次 ID 不规范")
        if (
            re.fullmatch(
                r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z",
                self.created_at,
            )
            is None
        ):
            raise ValueError("审计时间不是规范 UTC ISO 8601")
        datetime.strptime(self.created_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        if self.database.path != DATABASE_FILE:
            raise ValueError("数据库位置不规范")
        if self.database_revision != self.code.migration_revision:
            raise ValueError("代码 revision 不符")
        for blob in self.blobs:
            if blob.path != blob_relative_path(blob.sha256):
                raise ValueError("内容对象位置不规范")
        if (
            tuple(sorted(self.blobs, key=lambda blob: blob.sha256)) != self.blobs
            or len({blob.sha256 for blob in self.blobs}) != len(self.blobs)
            or tuple(sorted(self.artifacts, key=lambda item: item.artifact_id))
            != self.artifacts
            or len({item.artifact_id for item in self.artifacts}) != len(self.artifacts)
            or tuple(sorted(set(self.snapshot_ids))) != self.snapshot_ids
        ):
            raise ValueError("清单重复或排序不规范")
        for snapshot_id in self.snapshot_ids:
            require_sha256(snapshot_id)
        return self

    @property
    def canonical_bytes(self) -> bytes:
        return (
            json.dumps(
                self.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_bytes).hexdigest()


@dataclass(frozen=True, slots=True)
class BackupResult:
    batch_dir: Path
    manifest_sha256: str
    manifest: BackupManifest


def artifact_entry(record: ArtifactRecord) -> BackupArtifact:
    return BackupArtifact(
        artifact_id=record.artifact_id,
        kind=record.kind,
        format_version=record.format_version,
        members=record.members,
        created_at=record.created_at,
    )


def blob_entry(record: BlobRecord) -> FileEntry:
    return FileEntry(
        path=record.relative_path, sha256=record.sha256, size_bytes=record.size_bytes
    )


def counts_for(
    blobs: tuple[FileEntry, ...],
    artifacts: tuple[BackupArtifact, ...],
    snapshot_ids: tuple[str, ...],
) -> Counts:
    by_kind: dict[str, KindCount] = {}
    for kind in sorted({item.kind for item in artifacts}):
        selected = tuple(item for item in artifacts if item.kind == kind)
        by_kind[kind] = KindCount(
            artifacts=len(selected),
            members=sum(len(item.members) for item in selected),
            size_bytes=sum(m.size_bytes for item in selected for m in item.members),
        )
    return Counts(
        blobs=len(blobs),
        artifacts=len(artifacts),
        config_snapshots=len(snapshot_ids),
        blob_bytes=sum(blob.size_bytes for blob in blobs),
        by_kind=by_kind,
    )


def parse_manifest(raw: bytes) -> BackupManifest:
    def unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("重复清单键")
            result[key] = value
        return result

    try:
        json.loads(raw, object_pairs_hook=unique_pairs)
        value = BackupManifest.model_validate_json(raw)
        if value.canonical_bytes != raw:
            raise ValueError("清单字节不规范")
        return value
    except BackupError:
        raise
    except (ValueError, StorageError):
        raise BackupError(BackupReason.INVALID_MANIFEST) from None
