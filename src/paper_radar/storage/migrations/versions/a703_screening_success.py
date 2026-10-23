"""原始候选的权威成功、输出失败细节和登记时命中回执。"""

import sqlalchemy as sa
from alembic import op

revision = "a703_screening_success"
down_revision = "a702_screening_attempts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "screening_successes",
        sa.Column("success_id", sa.String(36), primary_key=True),
        sa.Column(
            "budget_id",
            sa.String(36),
            sa.ForeignKey("screening_budgets.budget_id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("task_id", sa.String(36), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column(
            "artifact_id",
            sa.String(64),
            sa.ForeignKey("artifacts.artifact_id"),
            nullable=False,
        ),
        sa.Column("structured_json", sa.Text(), nullable=False),
        sa.Column("submission_sha256", sa.String(64), nullable=False),
        sa.Column("audit_json", sa.Text(), nullable=False),
        sa.Column("settled_at", sa.Text(), nullable=False),
        sa.UniqueConstraint("task_id", "attempt_no"),
        sa.ForeignKeyConstraint(
            ["task_id", "attempt_no"],
            ["screening_attempts.task_id", "screening_attempts.attempt_no"],
        ),
    )
    # SQLite 的可空 REFERENCES 列支持原位追加,保留旧表所有 CHECK。
    op.execute(
        "ALTER TABLE screening_requests ADD COLUMN cached_success_id VARCHAR(36) "
        "REFERENCES screening_successes(success_id)"
    )
    op.add_column("screening_failures", sa.Column("issues_json", sa.Text()))
    op.add_column("screening_failures", sa.Column("submission_sha256", sa.String(64)))
    op.add_column("screening_failures", sa.Column("audit_json", sa.Text()))
