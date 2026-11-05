"""Body 前置事实与跨论文提取预算;Read 任务由后继 migration 持有。"""

from alembic import op

revision = "body01_persistence"
down_revision = "feed07_parser_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    statements = (
        """CREATE TABLE body_root (
        singleton INTEGER PRIMARY KEY CHECK(singleton=1), root_id TEXT NOT NULL UNIQUE,
        purpose TEXT NOT NULL CHECK(purpose IN ('production','experiment')),
        registered_at TEXT NOT NULL, registration_hash TEXT NOT NULL)""",
        """CREATE TABLE body_decisions (
        decision_id TEXT PRIMARY KEY, request_id TEXT NOT NULL UNIQUE,
        request_hash TEXT NOT NULL, paper_id TEXT NOT NULL REFERENCES papers(paper_id),
        version_id TEXT NOT NULL, revision_no INTEGER NOT NULL,
        sequence INTEGER NOT NULL CHECK(sequence>0), record_json TEXT NOT NULL,
        actor TEXT NOT NULL, decided_at TEXT NOT NULL,
        UNIQUE(paper_id,sequence),
        FOREIGN KEY(paper_id,version_id) REFERENCES paper_versions(paper_id,version_id),
        FOREIGN KEY(version_id,revision_no)
        REFERENCES paper_version_revisions(version_id,revision_no))""",
        """CREATE TABLE body_decision_screenings (
        decision_id TEXT NOT NULL REFERENCES body_decisions(decision_id),
        success_id TEXT NOT NULL REFERENCES screening_successes(success_id),
        PRIMARY KEY(decision_id,success_id))""",
        """CREATE TABLE body_pdfs (
        attachment_id TEXT PRIMARY KEY, request_id TEXT NOT NULL UNIQUE,
        request_hash TEXT NOT NULL, paper_id TEXT NOT NULL REFERENCES papers(paper_id),
        version_id TEXT NOT NULL, sequence INTEGER NOT NULL CHECK(sequence>0),
        artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
        pdf_sha256 TEXT NOT NULL, attached_at TEXT NOT NULL,
        requested_version_id TEXT,
        access_basis TEXT NOT NULL CHECK(access_basis='manual'),
        UNIQUE(paper_id,sequence),
        FOREIGN KEY(paper_id,version_id)
        REFERENCES paper_versions(paper_id,version_id))""",
        """CREATE TABLE body_samples (
        sample_id TEXT PRIMARY KEY, request_id TEXT NOT NULL UNIQUE,
        request_hash TEXT NOT NULL, paper_id TEXT NOT NULL REFERENCES papers(paper_id),
        version_id TEXT NOT NULL, sequence INTEGER NOT NULL CHECK(sequence>0),
        feed_id TEXT NOT NULL REFERENCES feeds(feed_id),
        pdf_sha256 TEXT NOT NULL, reason TEXT NOT NULL, frozen_at TEXT NOT NULL,
        UNIQUE(paper_id,sequence),
        FOREIGN KEY(paper_id,version_id)
        REFERENCES paper_versions(paper_id,version_id))""",
        """CREATE TABLE body_extraction_inputs (
        fingerprint TEXT PRIMARY KEY, backend TEXT NOT NULL, pdf_sha256 TEXT NOT NULL,
        snapshot_id TEXT NOT NULL REFERENCES runtime_config_snapshots(snapshot_id),
        payload BLOB NOT NULL CHECK(typeof(payload)='blob'))""",
        """CREATE TABLE body_extraction_attempts (
        attempt_id TEXT PRIMARY KEY,
        fingerprint TEXT NOT NULL REFERENCES body_extraction_inputs(fingerprint),
        backend TEXT NOT NULL, ordinal INTEGER NOT NULL CHECK(ordinal IN (1,2)),
        claimed_at TEXT NOT NULL, UNIQUE(backend,fingerprint,ordinal))""",
        """CREATE TABLE body_extraction_outcomes (
        attempt_id TEXT PRIMARY KEY REFERENCES body_extraction_attempts(attempt_id),
        failure TEXT CHECK(failure IN ('timeout','resource_exhausted','executor_error',
        'outcome_unknown','extraction_failed_no_text_layer',
        'extraction_failed_quality_gate')),
        artifact_id TEXT REFERENCES artifacts(artifact_id),
        reading_sha256 TEXT, evidence_map_sha256 TEXT, quality_failure TEXT,
        elapsed_seconds REAL NOT NULL CHECK(elapsed_seconds>=0),
        peak_memory_bytes INTEGER NOT NULL CHECK(peak_memory_bytes>=0),
        settled_at TEXT NOT NULL,
        CHECK((artifact_id IS NULL AND reading_sha256 IS NULL
        AND evidence_map_sha256 IS NULL
        AND failure IS NOT NULL AND quality_failure IS NULL) OR
        (artifact_id IS NOT NULL AND reading_sha256 IS NOT NULL
        AND evidence_map_sha256 IS NOT NULL
        AND ((failure IS NULL AND quality_failure IS NULL) OR
        (failure IN ('extraction_failed_quality_gate','extraction_failed_no_text_layer')
        AND quality_failure IS NOT NULL)))))""",
        """CREATE TABLE body_extraction_successes (
        fingerprint TEXT PRIMARY KEY REFERENCES body_extraction_inputs(fingerprint),
        attempt_id TEXT NOT NULL UNIQUE
        REFERENCES body_extraction_outcomes(attempt_id))""",
        """CREATE TABLE body_layout_reviews (
        review_id TEXT PRIMARY KEY, request_id TEXT NOT NULL UNIQUE,
        request_hash TEXT NOT NULL,
        fingerprint TEXT NOT NULL REFERENCES body_extraction_successes(fingerprint),
        reading_sha256 TEXT NOT NULL, evidence_map_sha256 TEXT NOT NULL,
        passed INTEGER NOT NULL CHECK(passed IN (0,1)), checks_json TEXT NOT NULL,
        note TEXT NOT NULL, actor TEXT NOT NULL, reviewed_at TEXT NOT NULL)""",
    )
    for statement in statements:
        op.execute(statement)
    for operation in ("UPDATE", "DELETE"):
        op.execute(
            f"CREATE TRIGGER body_root_no_{operation.lower()} "
            f"BEFORE {operation} ON body_root "
            "BEGIN SELECT RAISE(ABORT, 'immutable root'); END"
        )


def downgrade() -> None:
    for name in (
        "body_layout_reviews",
        "body_extraction_successes",
        "body_extraction_outcomes",
        "body_extraction_attempts",
        "body_extraction_inputs",
        "body_samples",
        "body_pdfs",
        "body_decision_screenings",
        "body_decisions",
        "body_root",
    ):
        op.execute(f"DROP TABLE {name}")
