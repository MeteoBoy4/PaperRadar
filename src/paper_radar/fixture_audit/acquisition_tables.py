"""审计计划、路线 started 与原子结算的独立事实。"""

from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)

from paper_radar.storage.schema import metadata

audit_plans = Table(
    "audit_plans",
    metadata,
    Column("plan_id", String(64), primary_key=True),
    Column("plan_key", String(128), nullable=False, unique=True),
    Column("plan_json", Text, nullable=False),
)
audit_route_starts = Table(
    "audit_route_starts",
    metadata,
    Column("event_no", Integer, primary_key=True, autoincrement=True),
    Column("execution_id", String(64), nullable=False, unique=True),
    Column("plan_id", String(64), ForeignKey("audit_plans.plan_id"), nullable=False),
    Column("request_key", String(128), nullable=False),
    Column("request_json", Text, nullable=False),
    Column("started_at", Text, nullable=False),
    UniqueConstraint("plan_id", "request_key"),
)
audit_route_settlements = Table(
    "audit_route_settlements",
    metadata,
    Column(
        "execution_id",
        String(64),
        ForeignKey("audit_route_starts.execution_id"),
        primary_key=True,
    ),
    Column("settlement_json", Text, nullable=False),
    Column("artifact_id", String(64), ForeignKey("artifacts.artifact_id")),
)
