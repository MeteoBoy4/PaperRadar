"""权威版本关系及有序版本选择。"""

import sqlalchemy as sa
from alembic import op

revision = "a604_version_relations"
down_revision = "a603_source_arbitration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    op.execute(
        "ALTER TABLE paper_source_acquisitions ADD COLUMN result_reason VARCHAR(24)"
    )
    rows = (
        connection.exec_driver_sql("SELECT * FROM paper_selection_events")
        .mappings()
        .all()
    )
    op.drop_table("paper_selection_events")
    op.create_table(
        "paper_selection_events",
        sa.Column("selection_id", sa.String(36), primary_key=True),
        sa.Column("paper_id", sa.String(36), nullable=False),
        sa.Column("version_id", sa.String(36), nullable=False),
        sa.Column("reason", sa.String(16), nullable=False),
        sa.Column("selected_at", sa.Text(), nullable=False),
        sa.Column("event_no", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(
            ["paper_id", "version_id"],
            ["paper_versions.paper_id", "paper_versions.version_id"],
        ),
        sa.UniqueConstraint("paper_id", "event_no"),
        sa.CheckConstraint("reason IN ('initial','journal_upgrade')"),
    )
    for row in rows:
        connection.exec_driver_sql(
            "INSERT INTO paper_selection_events "
            "(selection_id,paper_id,version_id,reason,selected_at,event_no) "
            "VALUES (?,?,?,?,?,1)",
            tuple(row.values()),
        )
    op.create_table(
        "paper_version_relations",
        sa.Column("relation_id", sa.String(36), primary_key=True),
        sa.Column("preprint_doi", sa.Text(), nullable=False),
        sa.Column("journal_doi", sa.Text(), nullable=False),
        sa.Column(
            "acquisition_id",
            sa.String(36),
            sa.ForeignKey("paper_source_acquisitions.acquisition_id"),
            nullable=False,
        ),
        sa.Column(
            "artifact_id",
            sa.String(64),
            sa.ForeignKey("artifacts.artifact_id"),
            nullable=False,
        ),
        sa.Column("locator", sa.Text(), nullable=False),
        sa.CheckConstraint("preprint_doi != journal_doi"),
        sa.UniqueConstraint("preprint_doi", "journal_doi"),
    )
    op.create_table(
        "paper_relation_references",
        sa.Column(
            "acquisition_id",
            sa.String(36),
            sa.ForeignKey("paper_source_acquisitions.acquisition_id"),
            primary_key=True,
        ),
        sa.Column(
            "relation_id",
            sa.String(36),
            sa.ForeignKey("paper_version_relations.relation_id"),
            primary_key=True,
        ),
        sa.Column("raw_source_doi", sa.Text(), primary_key=True),
        sa.Column("raw_target_doi", sa.Text(), primary_key=True),
        sa.Column("raw_kind", sa.String(24), primary_key=True),
        sa.Column("locator", sa.Text(), primary_key=True),
    )
