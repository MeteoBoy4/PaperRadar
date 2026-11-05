"""Read独立任务、代际预算、租约与分析接收闭包。"""

from alembic import op

revision = "body02_read_tasks"
down_revision = "body01_persistence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE body_extraction_attempts ADD COLUMN executor_audit_json TEXT"
    )
    for statement in (
        """CREATE TABLE read_budgets (
        budget_id TEXT PRIMARY KEY, paper_id TEXT NOT NULL REFERENCES papers(paper_id),
        fingerprint TEXT NOT NULL, stage TEXT NOT NULL CHECK(stage='read'),
        snapshot_id TEXT NOT NULL REFERENCES runtime_config_snapshots(snapshot_id),
        payload BLOB NOT NULL CHECK(typeof(payload)='blob'),
        extraction_fingerprint TEXT NOT NULL REFERENCES
        body_extraction_inputs(fingerprint),
        artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
        reading_sha256 TEXT NOT NULL, evidence_map_sha256 TEXT NOT NULL,
        output_language TEXT NOT NULL CHECK(output_language IN ('zh','en')),
        created_at TEXT NOT NULL, UNIQUE(paper_id,stage,fingerprint))""",
        """CREATE TABLE read_tasks (
        task_id TEXT PRIMARY KEY, budget_id TEXT NOT NULL REFERENCES
        read_budgets(budget_id),
        generation INTEGER NOT NULL CHECK(generation>0),
        parent_task_id TEXT UNIQUE REFERENCES read_tasks(task_id),
        retry_reason TEXT, retry_actor TEXT, created_at TEXT NOT NULL,
        CHECK((generation=1 AND parent_task_id IS NULL AND retry_reason IS NULL AND
        retry_actor IS NULL)
        OR (generation>1 AND parent_task_id IS NOT NULL AND length(retry_reason)>0
        AND length(retry_actor)>0)),
        UNIQUE(budget_id,generation))""",
        """CREATE TABLE read_registrations (
        request_id TEXT PRIMARY KEY, request_hash TEXT NOT NULL,
        request_json TEXT NOT NULL,
        task_id TEXT NOT NULL REFERENCES read_tasks(task_id),
        snapshot_id TEXT NOT NULL REFERENCES runtime_config_snapshots(snapshot_id),
        label TEXT NOT NULL, registered_at TEXT NOT NULL)""",
        """CREATE TABLE read_attempts (
        attempt_id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES
        read_tasks(task_id),
        ordinal INTEGER NOT NULL CHECK(ordinal IN (1,2)), token TEXT NOT NULL UNIQUE,
        claimed_at TEXT NOT NULL, lease_until TEXT NOT NULL,
        basis_json TEXT NOT NULL, metadata_json TEXT NOT NULL,
        UNIQUE(task_id,ordinal))""",
        """CREATE TABLE read_renewals (
        attempt_id TEXT NOT NULL REFERENCES read_attempts(attempt_id),
        sequence INTEGER NOT NULL CHECK(sequence>0), renewed_at TEXT NOT NULL,
        lease_until TEXT NOT NULL, PRIMARY KEY(attempt_id,sequence))""",
        """CREATE TABLE read_outcomes (
        attempt_id TEXT PRIMARY KEY REFERENCES read_attempts(attempt_id),
        failure TEXT CHECK(failure IN
        ('output_invalid','model_mismatch','timeout','cancelled',
        'protocol_error','executor_error','outcome_unknown')),
        issues_json TEXT NOT NULL, settled_at TEXT NOT NULL)""",
        """CREATE TABLE read_analyses (
        analysis_id TEXT PRIMARY KEY, task_id TEXT NOT NULL UNIQUE REFERENCES
        read_tasks(task_id),
        attempt_id TEXT NOT NULL UNIQUE REFERENCES read_outcomes(attempt_id),
        candidate_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
        candidate_sha256 TEXT NOT NULL, output_json TEXT NOT NULL,
        degrade_policy TEXT NOT NULL, attempt_ordinal INTEGER NOT NULL
        CHECK(attempt_ordinal IN (1,2)),
        evidence_rule_version TEXT NOT NULL, numeric_rule_version TEXT NOT NULL,
        limitation_rule_version TEXT NOT NULL, discards_json TEXT NOT NULL,
        diagnostics_json TEXT NOT NULL, warnings_json TEXT NOT NULL,
        executor_kind TEXT NOT NULL CHECK(executor_kind IN ('test','pi_rpc')),
        audit_json TEXT NOT NULL, settled_at TEXT NOT NULL)""",
        """CREATE TABLE read_evidence (
        analysis_id TEXT NOT NULL REFERENCES read_analyses(analysis_id),
        evidence_id TEXT NOT NULL, artifact_id TEXT NOT NULL REFERENCES
        artifacts(artifact_id),
        PRIMARY KEY(analysis_id,evidence_id))""",
    ):
        op.execute(statement)


def downgrade() -> None:
    for name in (
        "read_evidence",
        "read_analyses",
        "read_outcomes",
        "read_renewals",
        "read_attempts",
        "read_registrations",
        "read_tasks",
        "read_budgets",
    ):
        op.execute(f"DROP TABLE {name}")

    op.execute("ALTER TABLE body_extraction_attempts DROP COLUMN executor_audit_json")
