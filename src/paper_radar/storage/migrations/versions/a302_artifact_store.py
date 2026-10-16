"""内容对象、制品与成员引用。仅追加表与索引。"""

import sqlalchemy as sa
from alembic import op

revision = "a302_artifact_store"
down_revision = "a201_profile_snapshot"
branch_labels = None
depends_on = None


def _hex(column: str) -> str:
    return f"length({column}) = 64 AND {column} NOT GLOB '*[^0-9a-f]*'"


def upgrade() -> None:
    op.create_table(
        "content_objects",
        sa.Column("sha256", sa.String(64), primary_key=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("layout_version", sa.Integer(), nullable=False),
        sa.Column("relative_path", sa.Text(), nullable=False, unique=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.CheckConstraint(_hex("sha256")),
        sa.CheckConstraint("typeof(size_bytes) = 'integer' AND size_bytes >= 0"),
        sa.CheckConstraint("typeof(layout_version) = 'integer' AND layout_version > 0"),
    )
    op.create_table(
        "artifacts",
        sa.Column("artifact_id", sa.String(64), primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("format_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.CheckConstraint(_hex("artifact_id")),
        sa.CheckConstraint("typeof(format_version) = 'integer' AND format_version > 0"),
    )
    op.create_table(
        "artifact_members",
        sa.Column(
            "artifact_id",
            sa.String(64),
            sa.ForeignKey("artifacts.artifact_id"),
            primary_key=True,
        ),
        sa.Column("role", sa.String(32), primary_key=True),
        sa.Column(
            "sha256",
            sa.String(64),
            sa.ForeignKey("content_objects.sha256"),
            nullable=False,
        ),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.CheckConstraint(_hex("sha256")),
        sa.CheckConstraint("typeof(size_bytes) = 'integer' AND size_bytes >= 0"),
    )
    op.create_index("ix_artifact_members_sha256", "artifact_members", ["sha256"])
