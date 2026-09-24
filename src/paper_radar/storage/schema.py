"""配置事实的 SQLAlchemy Core 元数据。"""

from sqlalchemy import (
    Column,
    ForeignKey,
    ForeignKeyConstraint,
    LargeBinary,
    MetaData,
    String,
    Table,
    Text,
)

metadata = MetaData()

config_versions = Table(
    "config_versions",
    metadata,
    Column("kind", String(32), primary_key=True),
    Column("name", String(64), primary_key=True),
    Column("declared_version", String(64), primary_key=True),
    Column("raw_sha256", String(64), nullable=False),
    Column("raw_content", LargeBinary, nullable=False),
)

runtime_config_snapshots = Table(
    "runtime_config_snapshots",
    metadata,
    Column("snapshot_id", String(64), primary_key=True),
    Column("payload_json", Text, nullable=False),
    Column("created_at", Text, nullable=False),
)

snapshot_version_refs = Table(
    "snapshot_version_refs",
    metadata,
    Column(
        "snapshot_id",
        String(64),
        ForeignKey("runtime_config_snapshots.snapshot_id"),
        primary_key=True,
    ),
    Column("kind", String(32), primary_key=True),
    Column("name", String(64), primary_key=True),
    Column("declared_version", String(64), primary_key=True),
    Column("raw_sha256", String(64), nullable=False),
    ForeignKeyConstraint(
        ["kind", "name", "declared_version"],
        [
            "config_versions.kind",
            "config_versions.name",
            "config_versions.declared_version",
        ],
    ),
)
