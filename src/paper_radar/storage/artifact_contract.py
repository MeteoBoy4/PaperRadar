"""制品身份 Contract v1;纯确定性规则,不依赖文件系统或数据库。"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from paper_radar.storage.errors import StorageError

ARTIFACT_DOMAIN = "paper-radar.artifact"
ARTIFACT_FORMAT_VERSION = 1
BLOB_LAYOUT_VERSION = 1
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
KIND_ROLES = {
    "source_snapshot": ("payload",),
    "original_pdf": ("payload",),
    "model_success_response": ("payload",),
    "reference_tei": ("payload",),
    "extraction": ("document", "evidence_map", "manifest", "reading"),
}
SINGLE_FILE_KINDS = frozenset(KIND_ROLES) - {"extraction"}


class ArtifactReason(StrEnum):
    INVALID_MANIFEST = "invalid_manifest"
    INVALID_HASH = "invalid_hash"
    UNSAFE_PATH = "unsafe_path"
    BLOB_MISSING = "blob_missing"
    BLOB_CORRUPT = "blob_corrupt"
    HASH_MISMATCH = "hash_mismatch"
    PUBLICATION_FAILED = "publication_failed"
    ARTIFACT_MISSING = "artifact_missing"
    REGISTRATION_CORRUPT = "registration_corrupt"
    DATABASE_BUSY = "database_busy"
    DATABASE_FAILED = "database_failed"


class ArtifactError(StorageError):
    def __init__(self, reason: ArtifactReason, message: str) -> None:
        super().__init__(message)
        self.reason = reason


def require_sha256(value: str) -> str:
    if not isinstance(value, str) or SHA256.fullmatch(value) is None:
        raise ArtifactError(
            ArtifactReason.INVALID_HASH, "内容身份必须是完整 64 位小写 SHA-256"
        )
    return value


class ArtifactMember(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    role: str
    sha256: str
    size_bytes: int = Field(ge=0)

    @field_validator("sha256")
    @classmethod
    def valid_hash(cls, value: str) -> str:
        return require_sha256(value)


class ArtifactManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    domain: Literal["paper-radar.artifact"]
    format_version: Literal[1]
    kind: Literal[
        "source_snapshot",
        "original_pdf",
        "model_success_response",
        "reference_tei",
        "extraction",
    ]
    members: tuple[ArtifactMember, ...]

    @field_validator("format_version", mode="before")
    @classmethod
    def strict_version(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("格式版本必须是整数")
        return value

    @model_validator(mode="after")
    def exact_roles(self) -> Self:
        roles = tuple(member.role for member in self.members)
        if (
            len(set(roles)) != len(roles)
            or tuple(sorted(roles)) != KIND_ROLES[self.kind]
        ):
            raise ValueError("制品必须具有该种类的完整且不重复的角色集合")
        return self

    @property
    def canonical_json(self) -> str:
        payload = self.model_dump(mode="json")
        payload["members"] = sorted(
            payload["members"], key=lambda member: member["role"]
        )
        return json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )

    @property
    def artifact_id(self) -> str:
        return hashlib.sha256(self.canonical_json.encode("utf-8")).hexdigest()


def artifact_manifest(
    kind: str, members: tuple[ArtifactMember, ...]
) -> ArtifactManifest:
    try:
        return ArtifactManifest.model_validate(
            {
                "domain": ARTIFACT_DOMAIN,
                "format_version": ARTIFACT_FORMAT_VERSION,
                "kind": kind,
                "members": members,
            }
        )
    except ValidationError:
        raise ArtifactError(
            ArtifactReason.INVALID_MANIFEST, "制品种类、版本或成员集合不符合 Contract"
        ) from None


def blob_relative_path(sha256: str, layout_version: int = BLOB_LAYOUT_VERSION) -> str:
    require_sha256(sha256)
    if type(layout_version) is not int or layout_version != BLOB_LAYOUT_VERSION:
        raise ArtifactError(
            ArtifactReason.REGISTRATION_CORRUPT, "内容对象布局版本不受支持"
        )
    return f"blobs/sha256/{sha256[:2]}/{sha256}"


def media_type(kind: str, role: str) -> str:
    if kind not in KIND_ROLES or role not in KIND_ROLES[kind]:
        raise ArtifactError(ArtifactReason.INVALID_MANIFEST, "未知制品种类或角色")
    if kind == "original_pdf":
        return "application/pdf"
    if kind == "reference_tei":
        return "application/tei+xml"
    if kind == "extraction":
        return "text/markdown" if role == "reading" else "application/json"
    return "application/octet-stream"


@dataclass(frozen=True, slots=True)
class BlobRecord:
    sha256: str
    size_bytes: int
    relative_path: str
    layout_version: int = BLOB_LAYOUT_VERSION


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    artifact_id: str
    kind: str
    format_version: int
    members: tuple[ArtifactMember, ...]
    created_at: str
