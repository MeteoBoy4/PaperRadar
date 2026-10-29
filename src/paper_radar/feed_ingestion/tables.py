"""生产取得事实与逐条目结算;不写审计计划表。"""

import sqlalchemy as sa

from paper_radar.storage.schema import metadata

checks = sa.Table(
    "feed_production_checks",
    metadata,
    sa.Column("event_no", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("check_id", sa.String(64), nullable=False, unique=True),
    sa.Column("feed_id", sa.String(36), sa.ForeignKey("feeds.feed_id"), nullable=False),
    sa.Column("request_id", sa.Text, nullable=False),
    sa.Column("checked_at", sa.Text, nullable=False),
    sa.Column("request_json", sa.Text, nullable=False),
    sa.Column(
        "prior_check_id",
        sa.String(64),
        sa.ForeignKey("feed_production_checks.check_id"),
    ),
    sa.Column("settlement_json", sa.Text),
    sa.Column("settlement_sha256", sa.String(64)),
    sa.Column("artifact_id", sa.String(64), sa.ForeignKey("artifacts.artifact_id")),
    sa.UniqueConstraint("feed_id", "request_id"),
)
items = sa.Table(
    "feed_production_items",
    metadata,
    sa.Column(
        "check_id",
        sa.String(64),
        sa.ForeignKey("feed_production_checks.check_id"),
        primary_key=True,
    ),
    sa.Column("position", sa.Integer, primary_key=True),
    sa.Column("result_json", sa.Text, nullable=False),
    sa.Column("result_sha256", sa.String(64), nullable=False),
)
