"""JGR Feed 生产检查及逐条目结算。"""

from alembic import op

revision = "feed03_feed_acquisition"
down_revision = "feed02_title_language"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE feed_production_checks (
        event_no INTEGER PRIMARY KEY AUTOINCREMENT,
        check_id VARCHAR(64) NOT NULL UNIQUE,
        feed_id VARCHAR(36) NOT NULL REFERENCES feeds(feed_id),
        request_id TEXT NOT NULL,
        checked_at TEXT NOT NULL,
        request_json TEXT NOT NULL,
        prior_check_id VARCHAR(64) REFERENCES feed_production_checks(check_id),
        settlement_json TEXT,
        settlement_sha256 VARCHAR(64),
        artifact_id VARCHAR(64) REFERENCES artifacts(artifact_id),
        UNIQUE(feed_id, request_id),
        CHECK((settlement_json IS NULL) = (settlement_sha256 IS NULL))
    )""")
    op.execute("""CREATE TABLE feed_production_items (
        check_id VARCHAR(64) NOT NULL REFERENCES feed_production_checks(check_id),
        position INTEGER NOT NULL CHECK(position>0),
        result_json TEXT NOT NULL,
        result_sha256 VARCHAR(64) NOT NULL,
        PRIMARY KEY(check_id,position)
    )""")


def downgrade() -> None:
    op.drop_table("feed_production_items")
    op.drop_table("feed_production_checks")
