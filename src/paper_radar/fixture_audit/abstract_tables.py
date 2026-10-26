"""按成员/路线/策略/通道原子追加的安全摘要解释。"""

from sqlalchemy import Column, ForeignKey, String, Table, Text, UniqueConstraint

from paper_radar.storage.schema import metadata

abstract_rows = Table(
    "audit_abstract_rows",
    metadata,
    Column("row_id", String(64), primary_key=True),
    Column("plan_id", String(64), ForeignKey("audit_plans.plan_id"), nullable=False),
    Column("member_id", String(64), nullable=False),
    Column("route", String(32), nullable=False),
    Column("strategy_version", String(64), nullable=False),
    Column("channel", String(32), nullable=False),
    Column(
        "acquisition_id",
        String(64),
        ForeignKey("audit_route_starts.execution_id"),
        nullable=False,
    ),
    Column("content_json", Text, nullable=False),
    UniqueConstraint("plan_id", "member_id", "route", "strategy_version", "channel"),
)
