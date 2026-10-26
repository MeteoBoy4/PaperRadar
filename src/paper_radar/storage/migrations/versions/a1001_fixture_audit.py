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

    op.execute("""
        CREATE TABLE fixture_pdf_acquisitions (
            event_no INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            pdf_id VARCHAR(64) NOT NULL,
            sample_record_id VARCHAR(64) NOT NULL REFERENCES fixture_records(record_id),
            request_key VARCHAR(128) NOT NULL,
            artifact_id VARCHAR(64) NOT NULL REFERENCES artifacts(artifact_id),
            content_json TEXT NOT NULL,
            replaces VARCHAR(64) REFERENCES fixture_pdf_acquisitions(pdf_id),
            UNIQUE(pdf_id),
            UNIQUE(replaces),
            UNIQUE(sample_record_id, request_key)
        )
    """)

    op.execute("""
        CREATE TABLE fixture_pdf_expectations (
            event_no INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            expectation_id VARCHAR(64) NOT NULL,
            pdf_id VARCHAR(64) NOT NULL REFERENCES fixture_pdf_acquisitions(pdf_id),
            request_key VARCHAR(128) NOT NULL,
            backend_identity VARCHAR(64) NOT NULL,
            content_json TEXT NOT NULL,
            UNIQUE(expectation_id),
            UNIQUE(pdf_id, request_key),
            UNIQUE(pdf_id, backend_identity)
        )
    """)

    op.execute("""
        CREATE TABLE audit_plans (
            plan_id VARCHAR(64) NOT NULL PRIMARY KEY,
            plan_key VARCHAR(128) NOT NULL,
            plan_json TEXT NOT NULL,
            UNIQUE(plan_key)
        )
    """)
    op.execute("""
        CREATE TABLE audit_route_starts (
            event_no INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            execution_id VARCHAR(64) NOT NULL,
            plan_id VARCHAR(64) NOT NULL REFERENCES audit_plans(plan_id),
            request_key VARCHAR(128) NOT NULL,
            request_json TEXT NOT NULL,
            started_at TEXT NOT NULL,
            previous_execution_id VARCHAR(64) REFERENCES audit_route_starts(execution_id),
            UNIQUE(previous_execution_id),
            UNIQUE(plan_id, request_key),
            UNIQUE(execution_id)
        )
    """)
    op.execute("""
        CREATE TABLE audit_route_settlements (
            execution_id VARCHAR(64) NOT NULL PRIMARY KEY
                REFERENCES audit_route_starts(execution_id),
            settlement_json TEXT NOT NULL,
            artifact_id VARCHAR(64) REFERENCES artifacts(artifact_id)
        )
    """)

    op.execute("""
        CREATE TABLE audit_sampling_feeds (
            freeze_id VARCHAR(64) NOT NULL,
            plan_id VARCHAR(64) NOT NULL REFERENCES audit_plans(plan_id),
            journal VARCHAR(16) NOT NULL,
            acquisition_id VARCHAR(64) NOT NULL
                REFERENCES audit_route_starts(execution_id),
            artifact_id VARCHAR(64) NOT NULL REFERENCES artifacts(artifact_id),
            content_json TEXT NOT NULL,
            PRIMARY KEY(plan_id, journal),
            UNIQUE(freeze_id)
        )
    """)
    op.execute("""
        CREATE TABLE audit_sampling_events (
            event_no INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            event_id VARCHAR(64) NOT NULL,
            plan_id VARCHAR(64) NOT NULL REFERENCES audit_plans(plan_id),
            journal VARCHAR(16) NOT NULL,
            previous_event_id VARCHAR(64)
                REFERENCES audit_sampling_events(event_id),
            content_json TEXT NOT NULL,
            UNIQUE(event_id),
            UNIQUE(previous_event_id)
        )
    """)

    op.execute("""
        CREATE TABLE audit_abstract_rows (
            event_no INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            row_id VARCHAR(64) NOT NULL UNIQUE,
            generation INTEGER NOT NULL,
            previous_row_id VARCHAR(64) REFERENCES audit_abstract_rows(row_id),
            plan_id VARCHAR(64) NOT NULL REFERENCES audit_plans(plan_id),
            member_id VARCHAR(64) NOT NULL,
            route VARCHAR(32) NOT NULL,
            strategy_version VARCHAR(64) NOT NULL,
            channel VARCHAR(32) NOT NULL,
            acquisition_id VARCHAR(64) NOT NULL REFERENCES audit_route_starts(execution_id),
            content_json TEXT NOT NULL,
            UNIQUE(previous_row_id),
            UNIQUE(plan_id, member_id, route, strategy_version, channel, generation)
        )
    """)

    op.execute("""
        CREATE TABLE audit_parser_declarations (
            declaration_id VARCHAR(64) NOT NULL PRIMARY KEY,
            parser_version VARCHAR(128) NOT NULL UNIQUE,
            content_json TEXT NOT NULL
        )
    """)
    op.execute("""
        CREATE TABLE audit_interpretations (
            event_no INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            interpretation_id VARCHAR(64) NOT NULL UNIQUE,
            plan_id VARCHAR(64) NOT NULL REFERENCES audit_plans(plan_id),
            request_key VARCHAR(128) NOT NULL,
            parser_declaration_id VARCHAR(64) NOT NULL REFERENCES audit_parser_declarations(declaration_id),
            previous_interpretation_id VARCHAR(64) REFERENCES audit_interpretations(interpretation_id),
            content_json TEXT NOT NULL,
            UNIQUE(previous_interpretation_id),
            UNIQUE(plan_id, request_key)
        )
    """)
