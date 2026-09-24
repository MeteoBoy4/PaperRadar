"""配置版本与运行配置快照初始表。

Revision ID: a201_profile_snapshot
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "a201_profile_snapshot"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "config_versions",
        sa.Column("kind", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(64), primary_key=True),
        sa.Column("declared_version", sa.String(64), primary_key=True),
        sa.Column("raw_sha256", sa.String(64), nullable=False),
        sa.Column("raw_content", sa.LargeBinary(), nullable=False),
    )
    op.create_table(
        "runtime_config_snapshots",
        sa.Column("snapshot_id", sa.String(64), primary_key=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
    )
    op.create_table(
        "snapshot_version_refs",
        sa.Column(
            "snapshot_id",
            sa.String(64),
            sa.ForeignKey("runtime_config_snapshots.snapshot_id"),
            primary_key=True,
        ),
        sa.Column("kind", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(64), primary_key=True),
        sa.Column("declared_version", sa.String(64), primary_key=True),
        sa.Column("raw_sha256", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(
            ["kind", "name", "declared_version"],
            [
                "config_versions.kind",
                "config_versions.name",
                "config_versions.declared_version",
            ],
        ),
    )
