"""快照发现所需的只读索引查询。不加载配置正文或验证制品。"""

from dataclasses import dataclass

from sqlalchemy import Engine, select
from sqlalchemy.exc import SQLAlchemyError

from paper_radar.storage.errors import StorageError
from paper_radar.storage.schema import runtime_config_snapshots, snapshot_version_refs


@dataclass(frozen=True, slots=True, kw_only=True)
class VersionRefRecord:
    kind: str
    name: str
    declared_version: str


@dataclass(frozen=True, slots=True)
class SnapshotIndexRecord:
    snapshot_id: str
    created_at: str | None
    versions: tuple[VersionRefRecord, ...]


def read_snapshot_ids(engine: Engine) -> tuple[str, ...]:
    try:
        with engine.connect() as connection:
            return tuple(
                connection.execute(
                    select(runtime_config_snapshots.c.snapshot_id).order_by(
                        runtime_config_snapshots.c.snapshot_id
                    )
                ).scalars()
            )
    except SQLAlchemyError:
        raise StorageError("快照索引读取失败；请检查数据库表和迁移状态") from None


def read_snapshot_index(engine: Engine) -> tuple[SnapshotIndexRecord, ...]:
    try:
        with engine.connect() as connection:
            # sqlite3 的 legacy 模式不为 SELECT 发出 BEGIN。
            # SQLAlchemy autobegin 只改变其自身状态。显式 BEGIN 固定两次查询的读视图。
            connection.exec_driver_sql("BEGIN")
            snapshots = connection.execute(
                select(
                    runtime_config_snapshots.c.snapshot_id,
                    runtime_config_snapshots.c.created_at,
                ).order_by(runtime_config_snapshots.c.snapshot_id)
            ).all()
            refs = connection.execute(
                select(
                    snapshot_version_refs.c.snapshot_id,
                    snapshot_version_refs.c.kind,
                    snapshot_version_refs.c.name,
                    snapshot_version_refs.c.declared_version,
                ).order_by(
                    snapshot_version_refs.c.kind,
                    snapshot_version_refs.c.name,
                    snapshot_version_refs.c.declared_version,
                )
            ).all()
            versions: dict[str, list[VersionRefRecord]] = {}
            for snapshot_id, kind, name, version in refs:
                versions.setdefault(snapshot_id, []).append(
                    VersionRefRecord(kind=kind, name=name, declared_version=version)
                )
            return tuple(
                SnapshotIndexRecord(
                    snapshot_id, created_at, tuple(versions.get(snapshot_id, ()))
                )
                for snapshot_id, created_at in snapshots
            )
    except SQLAlchemyError:
        raise StorageError("快照索引读取失败；请检查数据库表和迁移状态") from None
