"""A10 未发布唯一 revision;仅追加本批实际消费的事实。"""

from alembic import op

revision = "a1001_fixture_audit"
down_revision = "a704_screening_retry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE fixture_declarations (
            declaration_id VARCHAR(64) PRIMARY KEY NOT NULL,
            declaration_key VARCHAR(128) NOT NULL,
            declared_version VARCHAR(64) NOT NULL,
            format_version INTEGER NOT NULL CHECK(format_version=1),
            raw_sha256 VARCHAR(64) NOT NULL,
            raw_content BLOB NOT NULL,
            UNIQUE(declaration_key, declared_version),
            CHECK(length(declaration_id)=64 AND declaration_id NOT GLOB '*[^0-9a-f]*'),
            CHECK(length(raw_sha256)=64 AND raw_sha256 NOT GLOB '*[^0-9a-f]*')
        )
    """)
    op.execute("""
        CREATE TABLE fixture_records (
            event_no INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            record_id VARCHAR(64) NOT NULL,
            declaration_id VARCHAR(64) NOT NULL
                REFERENCES fixture_declarations(declaration_id),
            purpose VARCHAR(32) NOT NULL
                CHECK(purpose IN ('feed','abstract_audit','references','pdf')),
            journal VARCHAR(16) NOT NULL
                CHECK(journal IN ('aies','jgr','qjrms','dqkx')),
            sample_key VARCHAR(128) NOT NULL,
            entry_json TEXT NOT NULL,
            replaces VARCHAR(64) REFERENCES fixture_records(record_id),
            UNIQUE(declaration_id, purpose, journal, sample_key),
            UNIQUE(record_id),
            UNIQUE(replaces),
            CHECK(length(record_id)=64 AND record_id NOT GLOB '*[^0-9a-f]*')
        )
    """)
