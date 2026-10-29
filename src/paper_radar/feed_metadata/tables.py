"""实际消费的元数据请求及路线执行事实。"""

import sqlalchemy as sa

from paper_radar.storage.schema import metadata

runs = sa.Table(
    "feed_metadata_requests",
    metadata,
    sa.Column("request_key", sa.String(64), primary_key=True),
    sa.Column(
        "paper_id", sa.String(36), sa.ForeignKey("papers.paper_id"), nullable=False
    ),
    sa.Column("request_id", sa.Text, nullable=False),
    sa.Column("basis_json", sa.Text, nullable=False),
    sa.Column("basis_sha256", sa.String(64), nullable=False),
    sa.Column("revision_no", sa.Integer),
    sa.UniqueConstraint("paper_id", "request_id"),
)
routes = sa.Table(
    "feed_metadata_routes",
    metadata,
    sa.Column(
        "request_key",
        sa.String(64),
        sa.ForeignKey("feed_metadata_requests.request_key"),
        primary_key=True,
    ),
    sa.Column("route", sa.String(32), primary_key=True),
    sa.Column("view_json", sa.Text, nullable=False),
    sa.Column("view_sha256", sa.String(64), nullable=False),
    sa.Column("artifact_id", sa.String(64), sa.ForeignKey("artifacts.artifact_id")),
    sa.Column(
        "acquisition_id",
        sa.String(36),
        sa.ForeignKey("paper_source_acquisitions.acquisition_id"),
    ),
)
