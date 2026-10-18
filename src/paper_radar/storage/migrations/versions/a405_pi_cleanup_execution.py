"""安装清理的追加执行与逐项进展。"""

import sqlalchemy as sa
from alembic import op

revision = "a405_pi_cleanup_execution"
down_revision = "a404_pi_cleanup_plans"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pi_cleanup_executions",
        sa.Column("run_id", sa.String(32), primary_key=True),
        sa.Column(
            "plan_id",
            sa.String(64),
            sa.ForeignKey("pi_cleanup_plans.plan_id"),
            nullable=False,
        ),
        sa.Column("created_at", sa.Text(), nullable=False),
    )
    op.create_table(
        "pi_cleanup_progress",
        sa.Column("event_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "run_id",
            sa.String(32),
            sa.ForeignKey("pi_cleanup_executions.run_id"),
            nullable=False,
        ),
        sa.Column(
            "install_id",
            sa.String(32),
            sa.ForeignKey("pi_install_instances.install_id"),
            nullable=False,
        ),
        sa.Column("phase", sa.String(32), nullable=False),
        sa.Column("reason", sa.String(64), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "phase IN ('not_run', 'retired', 'moved', 'completed', 'failed')"
        ),
    )
