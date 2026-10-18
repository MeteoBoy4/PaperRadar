"""Pi 固定材料、安装根、实例与 install_check;不预建激活或清理表。"""

import sqlalchemy as sa
from alembic import op

revision = "a401_pi_supply"
down_revision = "a302_artifact_store"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pi_supply_database",
        sa.Column("singleton", sa.Integer(), primary_key=True),
        sa.Column("database_id", sa.String(32), nullable=False, unique=True),
        sa.CheckConstraint("singleton = 1"),
    )
    op.execute("INSERT INTO pi_supply_database VALUES (1, lower(hex(randomblob(16))))")
    op.create_table(
        "pi_supply_roots",
        sa.Column("root_id", sa.String(32), primary_key=True),
        sa.Column("path", sa.Text(), nullable=False, unique=True),
    )
    op.create_table(
        "pi_supplies",
        sa.Column("supply_id", sa.String(64), primary_key=True),
        sa.Column("material_key", sa.String(64), nullable=False, unique=True),
        sa.Column("manifest", sa.LargeBinary(), nullable=False, unique=True),
        sa.Column("created_at", sa.Text(), nullable=False),
    )
    op.create_table(
        "pi_supply_materials",
        sa.Column(
            "supply_id",
            sa.String(64),
            sa.ForeignKey("pi_supplies.supply_id"),
            primary_key=True,
        ),
        sa.Column("role", sa.Text(), primary_key=True),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("raw", sa.LargeBinary(), nullable=False),
    )
    op.create_table(
        "pi_install_instances",
        sa.Column("install_id", sa.String(32), primary_key=True),
        sa.Column(
            "supply_id",
            sa.String(64),
            sa.ForeignKey("pi_supplies.supply_id"),
            nullable=False,
        ),
        sa.Column(
            "root_id",
            sa.String(32),
            sa.ForeignKey("pi_supply_roots.root_id"),
            nullable=False,
        ),
        sa.Column("created_at", sa.Text(), nullable=False),
    )
    op.create_table(
        "pi_install_checks",
        sa.Column("check_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "install_id",
            sa.String(32),
            sa.ForeignKey("pi_install_instances.install_id"),
            nullable=False,
        ),
        sa.Column("scope", sa.String(32), nullable=False),
        sa.Column("passed", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(64), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.CheckConstraint("scope = 'install_check'"),
        sa.CheckConstraint("passed IN (0, 1)"),
    )
