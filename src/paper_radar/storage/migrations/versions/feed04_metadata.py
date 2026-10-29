"""当前版本元数据请求与适用路线的恢复依据。"""

from alembic import op

revision = "feed04_metadata"
down_revision = "feed03_feed_acquisition"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE feed_metadata_requests (
        request_key VARCHAR(64) PRIMARY KEY NOT NULL,
        paper_id VARCHAR(36) NOT NULL REFERENCES papers(paper_id),
        request_id TEXT NOT NULL, basis_json TEXT NOT NULL,
        basis_sha256 VARCHAR(64) NOT NULL, revision_no INTEGER,
        UNIQUE(paper_id,request_id)
    )""")
    op.execute("""CREATE TABLE feed_metadata_routes (
        request_key VARCHAR(64) NOT NULL REFERENCES feed_metadata_requests(request_key),
        route VARCHAR(32) NOT NULL, view_json TEXT NOT NULL,
        view_sha256 VARCHAR(64) NOT NULL,
        artifact_id VARCHAR(64) REFERENCES artifacts(artifact_id),
        acquisition_id VARCHAR(36) REFERENCES paper_source_acquisitions(acquisition_id),
        PRIMARY KEY(request_key,route)
    )""")


def downgrade() -> None:
    connection = op.get_bind()
    if connection.exec_driver_sql(
        "SELECT count(*) FROM feed_metadata_requests"
    ).scalar_one():
        raise RuntimeError("元数据事实非空,不支持降级")
    op.drop_table("feed_metadata_routes")
    op.drop_table("feed_metadata_requests")
