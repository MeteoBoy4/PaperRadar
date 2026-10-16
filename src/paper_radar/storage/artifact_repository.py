"""制品登记的短事务与完整清单回放。"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import Connection, Engine, select
from sqlalchemy.exc import DBAPIError, SQLAlchemyError

from paper_radar.storage.artifact_contract import (
    ArtifactError,
    ArtifactMember,
    ArtifactReason,
    ArtifactRecord,
    BlobRecord,
    artifact_manifest,
    blob_relative_path,
    require_sha256,
)
from paper_radar.storage.schema import artifact_members, artifacts, content_objects


def _corrupt() -> ArtifactError:
    return ArtifactError(
        ArtifactReason.REGISTRATION_CORRUPT, "制品登记关系或身份损坏；不从来源修复历史"
    )


def _load(
    connection: Connection, artifact_id: str
) -> tuple[ArtifactRecord, tuple[BlobRecord, ...]]:
    require_sha256(artifact_id)
    row = (
        connection.execute(
            select(artifacts).where(artifacts.c.artifact_id == artifact_id)
        )
        .mappings()
        .first()
    )
    if row is None:
        raise ArtifactError(ArtifactReason.ARTIFACT_MISSING, "制品身份未登记")
    member_rows = (
        connection.execute(
            select(artifact_members)
            .where(artifact_members.c.artifact_id == artifact_id)
            .order_by(artifact_members.c.role)
        )
        .mappings()
        .all()
    )
    try:
        members = tuple(
            ArtifactMember(
                role=item["role"], sha256=item["sha256"], size_bytes=item["size_bytes"]
            )
            for item in member_rows
        )
        manifest = artifact_manifest(row["kind"], members)
        if (
            type(row["format_version"]) is not int
            or row["format_version"] != manifest.format_version
            or manifest.artifact_id != artifact_id
        ):
            raise _corrupt()
        blobs = []
        for member in members:
            blob = (
                connection.execute(
                    select(content_objects).where(
                        content_objects.c.sha256 == member.sha256
                    )
                )
                .mappings()
                .first()
            )
            if (
                blob is None
                or blob["size_bytes"] != member.size_bytes
                or type(blob["size_bytes"]) is not int
            ):
                raise _corrupt()
            if blob["relative_path"] != blob_relative_path(
                member.sha256, blob["layout_version"]
            ):
                raise _corrupt()
            blobs.append(
                BlobRecord(
                    member.sha256,
                    member.size_bytes,
                    blob["relative_path"],
                    blob["layout_version"],
                )
            )
        if not isinstance(row["created_at"], str):
            raise _corrupt()
        return ArtifactRecord(
            artifact_id,
            manifest.kind,
            manifest.format_version,
            members,
            row["created_at"],
        ), tuple(blobs)
    except (ValidationError, ArtifactError, TypeError, ValueError):
        raise _corrupt() from None


def read_registration(
    engine: Engine, artifact_id: str
) -> tuple[ArtifactRecord, tuple[BlobRecord, ...]]:
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("BEGIN")
            return _load(connection, artifact_id)
    except SQLAlchemyError:
        raise ArtifactError(
            ArtifactReason.DATABASE_FAILED, "制品登记无法读取；请检查数据库"
        ) from None


def list_registrations(
    engine: Engine,
) -> tuple[tuple[ArtifactRecord, tuple[BlobRecord, ...]], ...]:
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("BEGIN")
            ids = (
                connection.execute(
                    select(artifacts.c.artifact_id).order_by(artifacts.c.artifact_id)
                )
                .scalars()
                .all()
            )
            registered = tuple(_load(connection, artifact_id) for artifact_id in ids)
            # 不允许孤立登记成为备份时遗漏的事实。
            all_blobs = set(
                connection.execute(select(content_objects.c.sha256)).scalars()
            )
            referenced = {blob.sha256 for _, blobs in registered for blob in blobs}
            all_refs = connection.execute(
                select(artifact_members.c.artifact_id, artifact_members.c.role)
            ).all()
            expected_refs = {
                (record.artifact_id, member.role)
                for record, _ in registered
                for member in record.members
            }
            if all_blobs != referenced or set(map(tuple, all_refs)) != expected_refs:
                raise _corrupt()
            return registered
    except SQLAlchemyError:
        raise ArtifactError(
            ArtifactReason.DATABASE_FAILED, "制品登记无法读取；请检查数据库"
        ) from None


def save_registration(
    engine: Engine,
    kind: str,
    members: tuple[ArtifactMember, ...],
    blobs: tuple[BlobRecord, ...],
) -> ArtifactRecord:
    manifest = artifact_manifest(kind, members)
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            try:
                existing = connection.execute(
                    select(artifacts.c.artifact_id).where(
                        artifacts.c.artifact_id == manifest.artifact_id
                    )
                ).first()
                if existing is not None:
                    saved, _ = _load(connection, manifest.artifact_id)
                    connection.commit()
                    return saved
                now = datetime.now(UTC).isoformat()
                for blob in blobs:
                    row = (
                        connection.execute(
                            select(content_objects).where(
                                content_objects.c.sha256 == blob.sha256
                            )
                        )
                        .mappings()
                        .first()
                    )
                    if row is not None:
                        if (
                            row["size_bytes"],
                            row["relative_path"],
                            row["layout_version"],
                        ) != (blob.size_bytes, blob.relative_path, blob.layout_version):
                            raise _corrupt()
                    else:
                        orphan = connection.execute(
                            select(artifact_members.c.artifact_id)
                            .where(artifact_members.c.sha256 == blob.sha256)
                            .limit(1)
                        ).first()
                        if orphan is not None:
                            raise _corrupt()
                        connection.execute(
                            content_objects.insert().values(
                                sha256=blob.sha256,
                                size_bytes=blob.size_bytes,
                                layout_version=blob.layout_version,
                                relative_path=blob.relative_path,
                                created_at=now,
                            )
                        )
                connection.execute(
                    artifacts.insert().values(
                        artifact_id=manifest.artifact_id,
                        kind=kind,
                        format_version=manifest.format_version,
                        created_at=now,
                    )
                )
                for member in members:
                    connection.execute(
                        artifact_members.insert().values(
                            artifact_id=manifest.artifact_id, **member.model_dump()
                        )
                    )
                saved, _ = _load(connection, manifest.artifact_id)
                connection.commit()
                return saved
            except BaseException:
                connection.rollback()
                raise
    except SQLAlchemyError as error:
        if (
            isinstance(error, DBAPIError)
            and isinstance(error.orig, sqlite3.Error)
            and getattr(error.orig, "sqlite_errorcode", 0) & 0xFF == sqlite3.SQLITE_BUSY
        ):
            raise ArtifactError(
                ArtifactReason.DATABASE_BUSY, "数据库忙（锁等待上限 5 秒）；请稍后重试"
            ) from None
        raise ArtifactError(
            ArtifactReason.DATABASE_FAILED,
            "制品登记失败；数据库事实已整体回滚，可核验文件后重试",
        ) from None


def check_blob_registration(engine: Engine, blob: BlobRecord) -> bool:
    """新发布前检查已有登记,不允许用重试补回损坏历史。"""
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("BEGIN")
            row = (
                connection.execute(
                    select(content_objects).where(
                        content_objects.c.sha256 == blob.sha256
                    )
                )
                .mappings()
                .first()
            )
            refs = (
                connection.execute(
                    select(artifact_members.c.artifact_id).where(
                        artifact_members.c.sha256 == blob.sha256
                    )
                )
                .scalars()
                .all()
            )
            if row is None:
                if refs:
                    raise _corrupt()
                return False
            if not refs or (
                row["size_bytes"],
                row["relative_path"],
                row["layout_version"],
            ) != (blob.size_bytes, blob.relative_path, blob.layout_version):
                raise _corrupt()
            for artifact_id in set(refs):
                _load(connection, artifact_id)
            return True
    except SQLAlchemyError:
        raise ArtifactError(
            ArtifactReason.DATABASE_FAILED, "内容对象登记无法读取"
        ) from None
