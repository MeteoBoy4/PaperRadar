"""当前 prepare/list/show 实际消费的最小持久化表。"""

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Table,
    Text,
)

from paper_radar.storage.schema import metadata

database_identity = Table(
    "pi_supply_database",
    metadata,
    Column("singleton", Integer, primary_key=True),
    Column("database_id", String(32), nullable=False, unique=True),
    CheckConstraint("singleton = 1"),
)
roots = Table(
    "pi_supply_roots",
    metadata,
    Column("root_id", String(32), primary_key=True),
    Column("path", Text, nullable=False, unique=True),
)
supplies = Table(
    "pi_supplies",
    metadata,
    Column("supply_id", String(64), primary_key=True),
    Column("material_key", String(64), nullable=False, unique=True),
    Column("manifest", LargeBinary, nullable=False, unique=True),
    Column("created_at", Text, nullable=False),
)
materials = Table(
    "pi_supply_materials",
    metadata,
    Column(
        "supply_id", String(64), ForeignKey("pi_supplies.supply_id"), primary_key=True
    ),
    Column("role", Text, primary_key=True),
    Column("sha256", String(64), nullable=False),
    Column("raw", LargeBinary, nullable=False),
)
installs = Table(
    "pi_install_instances",
    metadata,
    Column("install_id", String(32), primary_key=True),
    Column(
        "supply_id", String(64), ForeignKey("pi_supplies.supply_id"), nullable=False
    ),
    Column(
        "root_id", String(32), ForeignKey("pi_supply_roots.root_id"), nullable=False
    ),
    Column("created_at", Text, nullable=False),
)
checks = Table(
    "pi_install_checks",
    metadata,
    Column("check_id", Integer, primary_key=True, autoincrement=True),
    Column(
        "install_id",
        String(32),
        ForeignKey("pi_install_instances.install_id"),
        nullable=False,
    ),
    Column("scope", String(32), nullable=False),
    Column("passed", Integer, nullable=False),
    Column("reason", String(64), nullable=False),
    Column("created_at", Text, nullable=False),
    CheckConstraint("scope = 'install_check'"),
    CheckConstraint("passed IN (0, 1)"),
)
