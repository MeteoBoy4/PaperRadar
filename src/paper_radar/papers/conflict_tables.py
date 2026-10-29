"""与成功论文观察分离的不可变拒绝证据。"""

import sqlalchemy as sa

from paper_radar.storage.schema import metadata

conflicts = sa.Table(
    "paper_identity_conflicts",
    metadata,
    sa.Column("conflict_id", sa.String(64), primary_key=True),
    sa.Column("request_sha256", sa.String(64), nullable=False, unique=True),
    sa.Column(
        "artifact_id",
        sa.String(64),
        sa.ForeignKey("artifacts.artifact_id"),
        nullable=False,
    ),
    sa.Column("assertion_json", sa.Text(), nullable=False),
    sa.Column("payload_sha256", sa.String(64), nullable=False),
    sa.Column("conflict", sa.String(32), nullable=False),
    sa.Column("version_ids_json", sa.Text(), nullable=False),
    sa.CheckConstraint(
        "conflict IN ('doi_owner_conflict','target_mismatch',"
        "'version_kind_conflict','entry_doi_changed')"
    ),
)
