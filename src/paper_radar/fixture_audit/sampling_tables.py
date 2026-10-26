"""冻结 Feed 与只追加选样事件;沿用 A10 单一未发布 migration。"""

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

sampling_feeds = Table(
    "audit_sampling_feeds",
    metadata,
    Column("freeze_id", String(64), nullable=False, unique=True),
    Column("plan_id", String(64), ForeignKey("audit_plans.plan_id"), primary_key=True),
    Column("journal", String(16), primary_key=True),
    Column(
        "acquisition_id",
        String(64),
        ForeignKey("audit_route_starts.execution_id"),
        nullable=False,
    ),
    Column(
        "artifact_id", String(64), ForeignKey("artifacts.artifact_id"), nullable=False
    ),
    Column("content_json", Text, nullable=False),
)
sampling_events = Table(
    "audit_sampling_events",
    metadata,
    Column("event_no", Integer, primary_key=True, autoincrement=True),
    Column("event_id", String(64), nullable=False, unique=True),
    Column("plan_id", String(64), ForeignKey("audit_plans.plan_id"), nullable=False),
    Column("journal", String(16), nullable=False),
    Column(
        "previous_event_id", String(64), ForeignKey("audit_sampling_events.event_id")
    ),
    Column("content_json", Text, nullable=False),
    UniqueConstraint("previous_event_id"),
)
