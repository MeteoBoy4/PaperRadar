"""不可变安装清理计划及其消费者所需退役识别。"""

import sqlalchemy as sa
from alembic import op

revision = "a404_pi_cleanup_plans"
down_revision = "a403_pi_activation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pi_cleanup_plans",
        sa.Column("plan_id", sa.String(64), primary_key=True),
        sa.Column("payload", sa.LargeBinary(), nullable=False, unique=True),
        sa.Column("created_at", sa.Text(), nullable=False),
    )
    op.create_table(
        "pi_install_retirements",
        sa.Column(
            "install_id",
            sa.String(32),
            sa.ForeignKey("pi_install_instances.install_id"),
            primary_key=True,
        ),
        sa.Column(
            "plan_id",
            sa.String(64),
            sa.ForeignKey("pi_cleanup_plans.plan_id"),
            nullable=False,
        ),
        sa.Column("created_at", sa.Text(), nullable=False),
    )
