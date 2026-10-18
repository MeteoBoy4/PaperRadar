"""既有供给重建的失败事实;失败不创建安装实例。"""

import sqlalchemy as sa
from alembic import op

revision = "a402_pi_rebuild_failures"
down_revision = "a401_pi_supply"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pi_rebuild_failures",
        sa.Column("failure_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "supply_id",
            sa.String(64),
            sa.ForeignKey("pi_supplies.supply_id"),
            nullable=False,
        ),
        sa.Column("reason", sa.String(64), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
    )
