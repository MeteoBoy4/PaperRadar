"""配置版本和快照的短事务持久化。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Connection, Engine, select
from sqlalchemy.exc import SQLAlchemyError

from paper_radar.config.compile import Material, RuntimeConfigSnapshot
from paper_radar.config.errors import ConfigError
from paper_radar.config.identity import sha256
from paper_radar.storage.schema import (
    config_versions,
    runtime_config_snapshots,
    snapshot_version_refs,
)


def _version_row(connection: Connection, material: Material) -> Any:
    return (
        connection.execute(
            select(config_versions).where(
                config_versions.c.kind == material.kind,
                config_versions.c.name == material.name,
                config_versions.c.declared_version == material.version,
            )
        )
        .mappings()
        .first()
    )


def _check_version(connection: Connection, material: Material) -> bool:
    row = _version_row(connection, material)
    if row is None:
        return False
    if row["raw_sha256"] != material.raw_sha256 or row["raw_content"] != material.raw:
        raise ConfigError(
            f"{material.kind}.{material.name}.{material.version}：声明版本已登记不同字节；请创建新版本"
        )
    return True


def check_version(engine: Engine, material: Material | None) -> None:
    if material is None:
        return
    try:
        with engine.connect() as connection:
            _check_version(connection, material)
    except SQLAlchemyError:
        raise ConfigError("数据库读取失败；请检查数据库状态") from None


def save_snapshot(
    engine: Engine, snapshot: RuntimeConfigSnapshot, material: Material | None
) -> None:
    """BEGIN IMMEDIATE 覆盖冲突检查与全部写入。失败整体回滚。"""
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            try:
                if material is not None and not _check_version(connection, material):
                    connection.execute(
                        config_versions.insert().values(
                            kind=material.kind,
                            name=material.name,
                            declared_version=material.version,
                            raw_sha256=material.raw_sha256,
                            raw_content=material.raw,
                        )
                    )
                existing = connection.execute(
                    select(runtime_config_snapshots.c.payload_json).where(
                        runtime_config_snapshots.c.snapshot_id == snapshot.snapshot_id
                    )
                ).scalar_one_or_none()
                payload_json = snapshot.payload_json
                if existing is None:
                    connection.execute(
                        runtime_config_snapshots.insert().values(
                            snapshot_id=snapshot.snapshot_id,
                            payload_json=payload_json,
                            created_at=datetime.now(UTC).isoformat(),
                        )
                    )
                    if material is not None:
                        connection.execute(
                            snapshot_version_refs.insert().values(
                                snapshot_id=snapshot.snapshot_id,
                                kind=material.kind,
                                name=material.name,
                                declared_version=material.version,
                                raw_sha256=material.raw_sha256,
                            )
                        )
                elif existing != payload_json:
                    raise ConfigError("快照身份对应内容损坏；请检查数据库")
                connection.commit()
            except BaseException:
                connection.rollback()
                raise
    except ConfigError:
        raise
    except SQLAlchemyError:
        raise ConfigError("数据库写入失败；配置事实已回滚，请检查数据库") from None


def read_snapshot(
    engine: Engine, snapshot_id: str
) -> tuple[str, list[tuple[str, str, str, str, bytes]]]:
    try:
        with engine.connect() as connection:
            payload = connection.execute(
                select(runtime_config_snapshots.c.payload_json).where(
                    runtime_config_snapshots.c.snapshot_id == snapshot_id
                )
            ).scalar_one_or_none()
            if payload is None:
                raise ConfigError("快照身份不存在；请检查完整 64 位 SHA-256")
            rows = connection.execute(
                select(
                    snapshot_version_refs.c.kind,
                    snapshot_version_refs.c.name,
                    snapshot_version_refs.c.declared_version,
                    snapshot_version_refs.c.raw_sha256,
                    config_versions.c.raw_sha256.label("registered_sha256"),
                    config_versions.c.raw_content,
                )
                .select_from(
                    snapshot_version_refs.join(
                        config_versions,
                        (snapshot_version_refs.c.kind == config_versions.c.kind)
                        & (snapshot_version_refs.c.name == config_versions.c.name)
                        & (
                            snapshot_version_refs.c.declared_version
                            == config_versions.c.declared_version
                        ),
                    )
                )
                .where(snapshot_version_refs.c.snapshot_id == snapshot_id)
            ).all()
            ref_count = connection.execute(
                select(snapshot_version_refs.c.kind).where(
                    snapshot_version_refs.c.snapshot_id == snapshot_id
                )
            ).all()
            if len(rows) != len(ref_count):
                raise ConfigError("快照版本引用损坏；请检查数据库")
            materials: list[tuple[str, str, str, str, bytes]] = []
            for kind, name, version, raw_hash, registered_hash, raw in rows:
                if sha256(raw) != raw_hash or registered_hash != raw_hash:
                    raise ConfigError("已登记版本内容损坏；请检查数据库")
                materials.append((kind, name, version, raw_hash, raw))
            return payload, materials
    except ConfigError:
        raise
    except SQLAlchemyError:
        raise ConfigError("数据库读取失败；请检查数据库状态") from None
