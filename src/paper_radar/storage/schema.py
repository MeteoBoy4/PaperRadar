"""配置事实与不可变制品登记的 SQLAlchemy Core 元数据。"""

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
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


content_objects = Table(
    "content_objects",
    metadata,
    Column("sha256", String(64), primary_key=True),
    Column("size_bytes", Integer, nullable=False),
    Column("layout_version", Integer, nullable=False),
    Column("relative_path", Text, nullable=False, unique=True),
    Column("created_at", Text, nullable=False),
    CheckConstraint("length(sha256) = 64 AND sha256 NOT GLOB '*[^0-9a-f]*'"),
    CheckConstraint("typeof(size_bytes) = 'integer' AND size_bytes >= 0"),
    CheckConstraint("typeof(layout_version) = 'integer' AND layout_version > 0"),
)

artifacts = Table(
    "artifacts",
    metadata,
    Column("artifact_id", String(64), primary_key=True),
    Column("kind", String(32), nullable=False),
    Column("format_version", Integer, nullable=False),
    Column("created_at", Text, nullable=False),
    CheckConstraint("length(artifact_id) = 64 AND artifact_id NOT GLOB '*[^0-9a-f]*'"),
    CheckConstraint("typeof(format_version) = 'integer' AND format_version > 0"),
)

artifact_members = Table(
    "artifact_members",
    metadata,
    Column(
        "artifact_id", String(64), ForeignKey("artifacts.artifact_id"), primary_key=True
    ),
    Column("role", String(32), primary_key=True),
    Column(
        "sha256",
        String(64),
        ForeignKey("content_objects.sha256"),
        nullable=False,
        index=True,
    ),
    Column("size_bytes", Integer, nullable=False),
    CheckConstraint("length(sha256) = 64 AND sha256 NOT GLOB '*[^0-9a-f]*'"),
    CheckConstraint("typeof(size_bytes) = 'integer' AND size_bytes >= 0"),
)
