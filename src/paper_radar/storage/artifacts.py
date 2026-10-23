"""不可变制品公共服务;文件先完整发布,再原子登记。"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path

from paper_radar.storage.artifact_contract import (
    KIND_ROLES,
    ArtifactError,
    ArtifactMember,
    ArtifactReason,
    ArtifactRecord,
    BlobRecord,
    artifact_manifest,
)
from paper_radar.storage.artifact_repository import (
    check_blob_registration,
    list_registrations,
    read_registration,
    save_registration,
)
from paper_radar.storage.blob_store import BlobStore
from paper_radar.storage.database import (
    DatabaseMode,
    open_database,
    require_current_revision,
)


class ArtifactStore:
    """database 与 data_root 无包含关系要求。构造不创建文件或打开数据库。"""

    def __init__(self, database: Path, data_root: Path) -> None:
        self.database = database
        self.blobs = BlobStore(data_root)

    def publish_single(
        self, kind: str, chunks: Iterable[bytes], *, expected_sha256: str | None = None
    ) -> ArtifactRecord:
        return self.publish_artifact(
            kind,
            {"payload": chunks},
            expected_sha256={"payload": expected_sha256}
            if expected_sha256 is not None
            else None,
        )

    def prepare_publish(self) -> None:
        """驱动领取前检查可预见的发布路径/权限错误,不登记制品。"""
        self.blobs.prepare_publish()

    def publish_artifact(
        self,
        kind: str,
        members: Mapping[str, Iterable[bytes]],
        *,
        expected_sha256: Mapping[str, str] | None = None,
    ) -> ArtifactRecord:
        roles = tuple(members)
        if (
            kind not in KIND_ROLES
            or len(roles) != len(set(roles))
            or set(roles) != set(KIND_ROLES[kind])
        ):
            raise ArtifactError(
                ArtifactReason.INVALID_MANIFEST,
                "制品必须提供已开放种类的完整且不重复的角色集合",
            )
        if expected_sha256 is not None and not set(expected_sha256) <= set(members):
            raise ArtifactError(ArtifactReason.INVALID_MANIFEST, "预期哈希包含未知角色")
        engine = open_database(self.database, mode=DatabaseMode.READ_WRITE)
        try:
            require_current_revision(engine)

            def check_existing(blob: BlobRecord) -> None:
                if check_blob_registration(engine, blob):
                    self.blobs.verify(blob)

            published = tuple(
                self.blobs.publish(
                    members[role],
                    (expected_sha256 or {}).get(role),
                    check_registration=check_existing,
                )
                for role in sorted(roles)
            )
            identities = tuple(
                ArtifactMember(
                    role=role, sha256=blob.sha256, size_bytes=blob.size_bytes
                )
                for role, blob in zip(sorted(roles), published, strict=True)
            )
            artifact_manifest(kind, identities)
            return save_registration(engine, kind, identities, published)
        finally:
            engine.dispose()

    def get_artifact(self, artifact_id: str) -> ArtifactRecord:
        """完整校验登记身份;不读取成员内容。"""
        return self.artifact_blobs(artifact_id)[0]

    def artifact_blobs(
        self, artifact_id: str
    ) -> tuple[ArtifactRecord, tuple[BlobRecord, ...]]:
        engine = open_database(self.database, mode=DatabaseMode.READ_ONLY)
        try:
            require_current_revision(engine)
            return read_registration(engine, artifact_id)
        finally:
            engine.dispose()

    def list_artifacts(self) -> tuple[ArtifactRecord, ...]:
        """同一数据库视图内校验全部登记闭包,不扫描磁盘猜事实。"""
        engine = open_database(self.database, mode=DatabaseMode.READ_ONLY)
        try:
            require_current_revision(engine)
            return tuple(record for record, _ in list_registrations(engine))
        finally:
            engine.dispose()

    def verified_blob_path(self, blob: BlobRecord) -> Path:
        """备份用完整性边界:全量校验后给出受控推导路径;不是流式读取 API。"""
        return self.blobs.verify(blob)

    def read_artifact(self, artifact_id: str) -> dict[str, bytes]:
        record, blobs = self.artifact_blobs(artifact_id)
        return {
            member.role: self.blobs.read(blob)
            for member, blob in zip(record.members, blobs, strict=True)
        }
