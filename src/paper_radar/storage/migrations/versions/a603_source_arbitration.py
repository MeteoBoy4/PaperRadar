"""来源仲裁类别及不可变人工修正事件。"""

import sqlalchemy as sa
from alembic import op

revision = "a603_source_arbitration"
down_revision = "a602_feed_discovery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Preserve the entire dependent closure, including Feed interpretation refs.
    names = (
        "paper_observations",
        "paper_source_acquisitions",
        "paper_field_candidates",
        "paper_candidate_authors",
        "paper_version_revisions",
        "paper_revision_fields",
        "feed_interpretations",
    )
    connection = op.get_bind()
    definitions = []
    indexes: list[str] = []
    for name in names:
        ddl = connection.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).scalar_one()
        definitions.append(
            ddl.replace(
                "source_kind IN ('publisher', 'feed')",
                "source_kind IN ('manual', 'publisher', 'registry', 'feed')",
            )
        )
        indexes.extend(
            connection.exec_driver_sql(
                "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name=? "
                "AND sql IS NOT NULL",
                (name,),
            ).scalars()
        )
        op.execute(f"CREATE TEMP TABLE saved_{name} AS SELECT * FROM {name}")
    for name in reversed(names):
        op.drop_table(name)
    for ddl in definitions:
        op.execute(ddl)
    for name in names:
        op.execute(f"INSERT INTO {name} SELECT * FROM saved_{name}")
        op.execute(f"DROP TABLE saved_{name}")
    for ddl in indexes:
        op.execute(ddl)
    op.create_table(
        "paper_manual_corrections",
        sa.Column(
            "version_id",
            sa.String(36),
            sa.ForeignKey("paper_versions.version_id"),
            primary_key=True,
        ),
        sa.Column("request_id", sa.Text(), primary_key=True),
        sa.Column(
            "acquisition_id",
            sa.String(36),
            sa.ForeignKey("paper_source_acquisitions.acquisition_id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("request_sha256", sa.String(64), nullable=False),
    )
