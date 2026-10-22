"""首条 DOI 出版者事实路径。"""

import sqlalchemy as sa
from alembic import op

revision = "a601_paper_facts"
down_revision = "a405_pi_cleanup_execution"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("papers", sa.Column("paper_id", sa.String(36), primary_key=True))
    op.create_table(
        "paper_versions",
        sa.Column("version_id", sa.String(36), primary_key=True),
        sa.Column(
            "paper_id", sa.String(36), sa.ForeignKey("papers.paper_id"), nullable=False
        ),
        sa.Column("version_kind", sa.String(16), nullable=False),
        sa.CheckConstraint("version_kind IN ('preprint', 'journal')"),
        sa.UniqueConstraint("paper_id", "version_id"),
    )
    op.create_table(
        "external_identifiers",
        sa.Column("scheme", sa.String(8), primary_key=True),
        sa.Column("normalized_value", sa.Text(), primary_key=True),
        sa.Column("paper_id", sa.String(36), nullable=False),
        sa.Column("version_id", sa.String(36), nullable=False, unique=True),
        sa.ForeignKeyConstraint(
            ["paper_id", "version_id"],
            ["paper_versions.paper_id", "paper_versions.version_id"],
        ),
        sa.CheckConstraint("scheme = 'doi'"),
    )
    op.create_table(
        "paper_observations",
        sa.Column("observation_id", sa.String(36), primary_key=True),
        sa.Column(
            "version_id",
            sa.String(36),
            sa.ForeignKey("paper_versions.version_id"),
            nullable=False,
        ),
        sa.Column("source_kind", sa.String(16), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("query_key", sa.Text(), nullable=False),
        sa.Column("observed_at", sa.Text(), nullable=False),
        sa.Column("parser_version", sa.Integer(), nullable=False),
        sa.Column(
            "artifact_id",
            sa.String(64),
            sa.ForeignKey("artifacts.artifact_id"),
            nullable=False,
        ),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("candidate_sha256", sa.String(64), nullable=False),
        sa.UniqueConstraint(
            "version_id", "source_kind", "provider", "query_key", "candidate_sha256"
        ),
        sa.CheckConstraint("source_kind = 'publisher'"),
        sa.CheckConstraint("parser_version > 0"),
        sa.UniqueConstraint(
            "version_id",
            "source_kind",
            "provider",
            "query_key",
            "observed_at",
            "payload_sha256",
            "parser_version",
        ),
    )
    op.create_table(
        "paper_source_acquisitions",
        sa.Column("acquisition_id", sa.String(36), primary_key=True),
        sa.Column(
            "version_id", sa.String(36), sa.ForeignKey("paper_versions.version_id")
        ),
        sa.Column("doi", sa.Text(), nullable=False),
        sa.Column("version_kind", sa.String(16), nullable=False),
        sa.Column("source_kind", sa.String(16), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("query_key", sa.Text(), nullable=False),
        sa.Column("observed_at", sa.Text(), nullable=False),
        sa.Column("parser_version", sa.Integer(), nullable=False),
        sa.Column("payload_sha256", sa.String(64), nullable=False),
        sa.Column("interpretation_sha256", sa.String(64), nullable=False),
        sa.Column(
            "source_observation_id",
            sa.String(36),
            sa.ForeignKey("paper_observations.observation_id"),
        ),
        sa.Column("response_bytes_retained", sa.Boolean(), nullable=False),
        sa.Column("event_no", sa.Integer()),
        sa.Column("result_status", sa.String(16), nullable=False),
        sa.Column("result_revision_no", sa.Integer()),
        sa.UniqueConstraint("version_id", "event_no"),
        sa.UniqueConstraint(
            "source_kind",
            "provider",
            "query_key",
            "doi",
            "observed_at",
            "payload_sha256",
            "parser_version",
        ),
        sa.CheckConstraint("source_kind = 'publisher'"),
        sa.CheckConstraint("version_kind IN ('preprint','journal')"),
        sa.CheckConstraint("parser_version > 0"),
        sa.CheckConstraint("event_no IS NULL OR event_no > 0"),
        sa.CheckConstraint("result_status IN ('retained','not_retained')"),
    )

    op.create_table(
        "paper_field_candidates",
        sa.Column("candidate_id", sa.String(36), primary_key=True),
        sa.Column(
            "observation_id",
            sa.String(36),
            sa.ForeignKey("paper_observations.observation_id"),
            nullable=False,
        ),
        sa.Column("field_name", sa.String(24), nullable=False),
        sa.Column("locator", sa.Text(), nullable=False),
        sa.Column("text_value", sa.Text()),
        sa.Column("is_truncated", sa.Boolean()),
        sa.Column("abstract_rule", sa.Text()),
        sa.Column("date_precision", sa.String(8)),
        sa.Column("text_norm", sa.Integer(), nullable=False),
        sa.UniqueConstraint("observation_id", "field_name"),
        sa.CheckConstraint(
            "field_name IN ('title','abstract','authors','journal','volume','"
            "issue','pages','online_date','print_date','source_url')"
        ),
        sa.CheckConstraint("text_norm = 1"),
    )
    op.create_table(
        "paper_candidate_authors",
        sa.Column(
            "candidate_id",
            sa.String(36),
            sa.ForeignKey("paper_field_candidates.candidate_id"),
            primary_key=True,
        ),
        sa.Column("ordinal", sa.Integer(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.CheckConstraint("ordinal >= 0"),
    )
    op.create_table(
        "paper_version_revisions",
        sa.Column(
            "version_id",
            sa.String(36),
            sa.ForeignKey("paper_versions.version_id"),
            primary_key=True,
        ),
        sa.Column("revision_no", sa.Integer(), primary_key=True),
        sa.Column("revised_at", sa.Text(), nullable=False),
        sa.Column(
            "acquisition_id",
            sa.String(36),
            sa.ForeignKey("paper_source_acquisitions.acquisition_id"),
            nullable=False,
        ),
        sa.CheckConstraint("revision_no > 0"),
    )
    op.create_table(
        "paper_revision_fields",
        sa.Column("version_id", sa.String(36), primary_key=True),
        sa.Column("revision_no", sa.Integer(), primary_key=True),
        sa.Column("field_name", sa.String(24), primary_key=True),
        sa.Column(
            "candidate_id",
            sa.String(36),
            sa.ForeignKey("paper_field_candidates.candidate_id"),
            nullable=False,
        ),
        sa.Column("rule_version", sa.Integer(), nullable=False),
        sa.Column(
            "acquisition_id",
            sa.String(36),
            sa.ForeignKey("paper_source_acquisitions.acquisition_id"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["version_id", "revision_no"],
            [
                "paper_version_revisions.version_id",
                "paper_version_revisions.revision_no",
            ],
        ),
        sa.CheckConstraint("rule_version = 1"),
    )
    op.create_table(
        "paper_selection_events",
        sa.Column("selection_id", sa.String(36), primary_key=True),
        sa.Column("paper_id", sa.String(36), nullable=False),
        sa.Column("version_id", sa.String(36), nullable=False),
        sa.Column("reason", sa.String(16), nullable=False),
        sa.Column("selected_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["paper_id", "version_id"],
            ["paper_versions.paper_id", "paper_versions.version_id"],
        ),
        sa.UniqueConstraint("paper_id"),
        sa.CheckConstraint("reason = 'initial'"),
    )
    op.create_index(
        "ix_paper_observations_stream",
        "paper_observations",
        ["version_id", "source_kind", "provider", "query_key", "observed_at"],
    )
