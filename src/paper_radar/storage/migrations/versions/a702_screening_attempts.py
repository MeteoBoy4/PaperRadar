"""原子领取、当前租约与失败事实。"""

import sqlalchemy as sa
from alembic import op

revision = "a702_screening_attempts"
down_revision = "a701_screening_registration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "screening_attempts",
        sa.Column(
            "task_id",
            sa.String(36),
            sa.ForeignKey("screening_tasks.task_id"),
            primary_key=True,
        ),
        sa.Column("attempt_no", sa.Integer(), primary_key=True),
        sa.Column(
            "receipt_id",
            sa.String(64),
            sa.ForeignKey("screening_requests.receipt_id"),
            nullable=False,
        ),
        sa.Column("version_id", sa.String(36), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column(
            "selection_id",
            sa.String(36),
            sa.ForeignKey("paper_selection_events.selection_id"),
        ),
        sa.Column("claimed_at", sa.Text(), nullable=False),
        sa.Column("credential_sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("renewal_sha256", sa.String(64), nullable=False, unique=True),
        sa.ForeignKeyConstraint(
            ["version_id", "revision_no"],
            [
                "paper_version_revisions.version_id",
                "paper_version_revisions.revision_no",
            ],
        ),
        sa.CheckConstraint("attempt_no IN (1,2)"),
    )
    op.create_table(
        "screening_leases",
        sa.Column("task_id", sa.String(36), primary_key=True),
        sa.Column("attempt_no", sa.Integer(), primary_key=True),
        sa.Column("expires_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["task_id", "attempt_no"],
            ["screening_attempts.task_id", "screening_attempts.attempt_no"],
        ),
    )
    op.create_table(
        "screening_failures",
        sa.Column("task_id", sa.String(36), primary_key=True),
        sa.Column("attempt_no", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("origin", sa.String(12), nullable=False),
        sa.Column("settled_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["task_id", "attempt_no"],
            ["screening_attempts.task_id", "screening_attempts.attempt_no"],
        ),
        sa.CheckConstraint(
            "kind IN ('output_invalid','model_mismatch','timeout','cancelled',"
            "'protocol_error','executor_error','outcome_unknown')"
        ),
        sa.CheckConstraint("origin IN ('executor','exception','recovery')"),
    )
