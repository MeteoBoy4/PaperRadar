"""每库唯一执行选择及只追加激活历史。"""

import sqlalchemy as sa
from alembic import op

revision = "a403_pi_activation"
down_revision = "a402_pi_rebuild_failures"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pi_activation_events",
        sa.Column("activation_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "supply_id",
            sa.String(64),
            sa.ForeignKey("pi_supplies.supply_id"),
            nullable=False,
        ),
        sa.Column(
            "install_id",
            sa.String(32),
            sa.ForeignKey("pi_install_instances.install_id"),
            nullable=False,
        ),
        sa.Column(
            "snapshot_id",
            sa.String(64),
            sa.ForeignKey("runtime_config_snapshots.snapshot_id"),
            nullable=False,
        ),
        sa.Column(
            "root_id",
            sa.String(32),
            sa.ForeignKey("pi_supply_roots.root_id"),
            nullable=False,
        ),
        sa.Column("root_path", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
    )
    op.create_table(
        "pi_current_selection",
        sa.Column("singleton", sa.Integer(), primary_key=True),
        sa.Column(
            "activation_id",
            sa.Integer(),
            sa.ForeignKey("pi_activation_events.activation_id"),
            nullable=False,
        ),
        sa.CheckConstraint("singleton = 1"),
    )
