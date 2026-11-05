"""配置、制品与 Body/Read 事实的共享 SQLAlchemy Core 元数据。"""

from sqlalchemy import (
    REAL,
    CheckConstraint,
    Column,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)

metadata = MetaData()

config_versions = Table(
    "config_versions",
    metadata,
    Column("kind", String(32), primary_key=True),
    Column("name", String(64), primary_key=True),
    Column("declared_version", String(64), primary_key=True),
    Column("raw_sha256", String(64), nullable=False),
    Column("raw_content", LargeBinary, nullable=False),
)

runtime_config_snapshots = Table(
    "runtime_config_snapshots",
    metadata,
    Column("snapshot_id", String(64), primary_key=True),
    Column("payload_json", Text, nullable=False),
    Column("created_at", Text, nullable=False),
)

snapshot_version_refs = Table(
    "snapshot_version_refs",
    metadata,
    Column(
        "snapshot_id",
        String(64),
        ForeignKey("runtime_config_snapshots.snapshot_id"),
        primary_key=True,
    ),
    Column("kind", String(32), primary_key=True),
    Column("name", String(64), primary_key=True),
    Column("declared_version", String(64), primary_key=True),
    Column("raw_sha256", String(64), nullable=False),
    ForeignKeyConstraint(
        ["kind", "name", "declared_version"],
        [
            "config_versions.kind",
            "config_versions.name",
            "config_versions.declared_version",
        ],
    ),
)


content_objects = Table(
    "content_objects",
    metadata,
    Column("sha256", String(64), primary_key=True),
    Column("size_bytes", Integer, nullable=False),
    Column("layout_version", Integer, nullable=False),
    Column("relative_path", Text, nullable=False, unique=True),
    Column("created_at", Text, nullable=False),
    CheckConstraint("length(sha256) = 64 AND sha256 NOT GLOB '*[^0-9a-f]*'"),
    CheckConstraint("typeof(size_bytes) = 'integer' AND size_bytes >= 0"),
    CheckConstraint("typeof(layout_version) = 'integer' AND layout_version > 0"),
)

artifacts = Table(
    "artifacts",
    metadata,
    Column("artifact_id", String(64), primary_key=True),
    Column("kind", String(32), nullable=False),
    Column("format_version", Integer, nullable=False),
    Column("created_at", Text, nullable=False),
    CheckConstraint("length(artifact_id) = 64 AND artifact_id NOT GLOB '*[^0-9a-f]*'"),
    CheckConstraint("typeof(format_version) = 'integer' AND format_version > 0"),
)

artifact_members = Table(
    "artifact_members",
    metadata,
    Column(
        "artifact_id", String(64), ForeignKey("artifacts.artifact_id"), primary_key=True
    ),
    Column("role", String(32), primary_key=True),
    Column(
        "sha256",
        String(64),
        ForeignKey("content_objects.sha256"),
        nullable=False,
        index=True,
    ),
    Column("size_bytes", Integer, nullable=False),
    CheckConstraint("length(sha256) = 64 AND sha256 NOT GLOB '*[^0-9a-f]*'"),
    CheckConstraint("typeof(size_bytes) = 'integer' AND size_bytes >= 0"),
)


# body01/body02 使用 SQLite 原生 DDL。未显式 NOT NULL 的单列主键保留
# nullable=True。元数据描述既有结构,用户数据库仍只经 migration 创建和升级。
body_root = Table(
    "body_root",
    metadata,
    Column("singleton", Integer, primary_key=True, nullable=True),
    Column("root_id", Text, nullable=False, unique=True),
    Column("purpose", Text, nullable=False),
    Column("registered_at", Text, nullable=False),
    Column("registration_hash", Text, nullable=False),
    CheckConstraint("singleton=1"),
    CheckConstraint("purpose IN ('production','experiment')"),
)

body_decisions = Table(
    "body_decisions",
    metadata,
    Column("decision_id", Text, primary_key=True, nullable=True),
    Column("request_id", Text, nullable=False, unique=True),
    Column("request_hash", Text, nullable=False),
    Column("paper_id", Text, ForeignKey("papers.paper_id"), nullable=False),
    Column("version_id", Text, nullable=False),
    Column("revision_no", Integer, nullable=False),
    Column("sequence", Integer, nullable=False),
    Column("record_json", Text, nullable=False),
    Column("actor", Text, nullable=False),
    Column("decided_at", Text, nullable=False),
    UniqueConstraint("paper_id", "sequence"),
    ForeignKeyConstraint(
        ["paper_id", "version_id"],
        ["paper_versions.paper_id", "paper_versions.version_id"],
    ),
    ForeignKeyConstraint(
        ["version_id", "revision_no"],
        ["paper_version_revisions.version_id", "paper_version_revisions.revision_no"],
    ),
    CheckConstraint("sequence>0"),
)

body_decision_screenings = Table(
    "body_decision_screenings",
    metadata,
    Column(
        "decision_id", Text, ForeignKey("body_decisions.decision_id"), primary_key=True
    ),
    Column(
        "success_id",
        Text,
        ForeignKey("screening_successes.success_id"),
        primary_key=True,
    ),
)

body_pdfs = Table(
    "body_pdfs",
    metadata,
    Column("attachment_id", Text, primary_key=True, nullable=True),
    Column("request_id", Text, nullable=False, unique=True),
    Column("request_hash", Text, nullable=False),
    Column("paper_id", Text, ForeignKey("papers.paper_id"), nullable=False),
    Column("version_id", Text, nullable=False),
    Column("sequence", Integer, nullable=False),
    Column("artifact_id", Text, ForeignKey("artifacts.artifact_id"), nullable=False),
    Column("pdf_sha256", Text, nullable=False),
    Column("attached_at", Text, nullable=False),
    Column("requested_version_id", Text),
    Column("access_basis", Text, nullable=False),
    UniqueConstraint("paper_id", "sequence"),
    ForeignKeyConstraint(
        ["paper_id", "version_id"],
        ["paper_versions.paper_id", "paper_versions.version_id"],
    ),
    CheckConstraint("sequence>0"),
    CheckConstraint("access_basis='manual'"),
)

body_samples = Table(
    "body_samples",
    metadata,
    Column("sample_id", Text, primary_key=True, nullable=True),
    Column("request_id", Text, nullable=False, unique=True),
    Column("request_hash", Text, nullable=False),
    Column("paper_id", Text, ForeignKey("papers.paper_id"), nullable=False),
    Column("version_id", Text, nullable=False),
    Column("sequence", Integer, nullable=False),
    Column("feed_id", Text, ForeignKey("feeds.feed_id"), nullable=False),
    Column("pdf_sha256", Text, nullable=False),
    Column("reason", Text, nullable=False),
    Column("frozen_at", Text, nullable=False),
    UniqueConstraint("paper_id", "sequence"),
    ForeignKeyConstraint(
        ["paper_id", "version_id"],
        ["paper_versions.paper_id", "paper_versions.version_id"],
    ),
    CheckConstraint("sequence>0"),
)

body_extraction_inputs = Table(
    "body_extraction_inputs",
    metadata,
    Column("fingerprint", Text, primary_key=True, nullable=True),
    Column("backend", Text, nullable=False),
    Column("pdf_sha256", Text, nullable=False),
    Column(
        "snapshot_id",
        Text,
        ForeignKey("runtime_config_snapshots.snapshot_id"),
        nullable=False,
    ),
    Column("payload", LargeBinary, nullable=False),
    CheckConstraint("typeof(payload)='blob'"),
)

body_extraction_attempts = Table(
    "body_extraction_attempts",
    metadata,
    Column("attempt_id", Text, primary_key=True, nullable=True),
    Column(
        "fingerprint",
        Text,
        ForeignKey("body_extraction_inputs.fingerprint"),
        nullable=False,
    ),
    Column("backend", Text, nullable=False),
    Column("ordinal", Integer, nullable=False),
    Column("claimed_at", Text, nullable=False),
    Column("executor_audit_json", Text),
    UniqueConstraint("backend", "fingerprint", "ordinal"),
    CheckConstraint("ordinal IN (1,2)"),
)

body_extraction_outcomes = Table(
    "body_extraction_outcomes",
    metadata,
    Column(
        "attempt_id",
        Text,
        ForeignKey("body_extraction_attempts.attempt_id"),
        primary_key=True,
        nullable=True,
    ),
    Column("failure", Text),
    Column("artifact_id", Text, ForeignKey("artifacts.artifact_id")),
    Column("reading_sha256", Text),
    Column("evidence_map_sha256", Text),
    Column("quality_failure", Text),
    Column("elapsed_seconds", REAL, nullable=False),
    Column("peak_memory_bytes", Integer, nullable=False),
    Column("settled_at", Text, nullable=False),
    CheckConstraint(
        "failure IN ('timeout','resource_exhausted','executor_error',"
        "'outcome_unknown','extraction_failed_no_text_layer',"
        "'extraction_failed_quality_gate')"
    ),
    CheckConstraint("elapsed_seconds>=0"),
    CheckConstraint("peak_memory_bytes>=0"),
    CheckConstraint(
        "(artifact_id IS NULL AND reading_sha256 IS NULL "
        "AND evidence_map_sha256 IS NULL "
        "AND failure IS NOT NULL AND quality_failure IS NULL) OR "
        "(artifact_id IS NOT NULL AND reading_sha256 IS NOT NULL "
        "AND evidence_map_sha256 IS NOT NULL "
        "AND ((failure IS NULL AND quality_failure IS NULL) OR "
        "(failure IN ('extraction_failed_quality_gate',"
        "'extraction_failed_no_text_layer') "
        "AND quality_failure IS NOT NULL)))"
    ),
)

body_extraction_successes = Table(
    "body_extraction_successes",
    metadata,
    Column(
        "fingerprint",
        Text,
        ForeignKey("body_extraction_inputs.fingerprint"),
        primary_key=True,
        nullable=True,
    ),
    Column(
        "attempt_id",
        Text,
        ForeignKey("body_extraction_outcomes.attempt_id"),
        nullable=False,
        unique=True,
    ),
)

body_layout_reviews = Table(
    "body_layout_reviews",
    metadata,
    Column("review_id", Text, primary_key=True, nullable=True),
    Column("request_id", Text, nullable=False, unique=True),
    Column("request_hash", Text, nullable=False),
    Column(
        "fingerprint",
        Text,
        ForeignKey("body_extraction_successes.fingerprint"),
        nullable=False,
    ),
    Column("reading_sha256", Text, nullable=False),
    Column("evidence_map_sha256", Text, nullable=False),
    Column("passed", Integer, nullable=False),
    Column("checks_json", Text, nullable=False),
    Column("note", Text, nullable=False),
    Column("actor", Text, nullable=False),
    Column("reviewed_at", Text, nullable=False),
    CheckConstraint("passed IN (0,1)"),
)

read_budgets = Table(
    "read_budgets",
    metadata,
    Column("budget_id", Text, primary_key=True, nullable=True),
    Column("paper_id", Text, ForeignKey("papers.paper_id"), nullable=False),
    Column("fingerprint", Text, nullable=False),
    Column("stage", Text, nullable=False),
    Column(
        "snapshot_id",
        Text,
        ForeignKey("runtime_config_snapshots.snapshot_id"),
        nullable=False,
    ),
    Column("payload", LargeBinary, nullable=False),
    Column(
        "extraction_fingerprint",
        Text,
        ForeignKey("body_extraction_inputs.fingerprint"),
        nullable=False,
    ),
    Column("artifact_id", Text, ForeignKey("artifacts.artifact_id"), nullable=False),
    Column("reading_sha256", Text, nullable=False),
    Column("evidence_map_sha256", Text, nullable=False),
    Column("output_language", Text, nullable=False),
    Column("created_at", Text, nullable=False),
    UniqueConstraint("paper_id", "stage", "fingerprint"),
    CheckConstraint("stage='read'"),
    CheckConstraint("typeof(payload)='blob'"),
    CheckConstraint("output_language IN ('zh','en')"),
)

read_tasks = Table(
    "read_tasks",
    metadata,
    Column("task_id", Text, primary_key=True, nullable=True),
    Column("budget_id", Text, ForeignKey("read_budgets.budget_id"), nullable=False),
    Column("generation", Integer, nullable=False),
    Column("parent_task_id", Text, ForeignKey("read_tasks.task_id"), unique=True),
    Column("retry_reason", Text),
    Column("retry_actor", Text),
    Column("created_at", Text, nullable=False),
    UniqueConstraint("budget_id", "generation"),
    CheckConstraint("generation>0"),
    CheckConstraint(
        "(generation=1 AND parent_task_id IS NULL AND retry_reason IS NULL "
        "AND retry_actor IS NULL) OR (generation>1 AND parent_task_id IS NOT NULL "
        "AND length(retry_reason)>0 AND length(retry_actor)>0)"
    ),
)

read_registrations = Table(
    "read_registrations",
    metadata,
    Column("request_id", Text, primary_key=True, nullable=True),
    Column("request_hash", Text, nullable=False),
    Column("request_json", Text, nullable=False),
    Column("task_id", Text, ForeignKey("read_tasks.task_id"), nullable=False),
    Column(
        "snapshot_id",
        Text,
        ForeignKey("runtime_config_snapshots.snapshot_id"),
        nullable=False,
    ),
    Column("label", Text, nullable=False),
    Column("registered_at", Text, nullable=False),
)

read_attempts = Table(
    "read_attempts",
    metadata,
    Column("attempt_id", Text, primary_key=True, nullable=True),
    Column("task_id", Text, ForeignKey("read_tasks.task_id"), nullable=False),
    Column("ordinal", Integer, nullable=False),
    Column("token", Text, nullable=False, unique=True),
    Column("claimed_at", Text, nullable=False),
    Column("lease_until", Text, nullable=False),
    Column("basis_json", Text, nullable=False),
    Column("metadata_json", Text, nullable=False),
    UniqueConstraint("task_id", "ordinal"),
    CheckConstraint("ordinal IN (1,2)"),
)

read_renewals = Table(
    "read_renewals",
    metadata,
    Column(
        "attempt_id", Text, ForeignKey("read_attempts.attempt_id"), primary_key=True
    ),
    Column("sequence", Integer, primary_key=True),
    Column("renewed_at", Text, nullable=False),
    Column("lease_until", Text, nullable=False),
    CheckConstraint("sequence>0"),
)

read_outcomes = Table(
    "read_outcomes",
    metadata,
    Column(
        "attempt_id",
        Text,
        ForeignKey("read_attempts.attempt_id"),
        primary_key=True,
        nullable=True,
    ),
    Column("failure", Text),
    Column("issues_json", Text, nullable=False),
    Column("settled_at", Text, nullable=False),
    CheckConstraint(
        "failure IN ('output_invalid','model_mismatch','timeout','cancelled',"
        "'protocol_error','executor_error','outcome_unknown')"
    ),
)

read_analyses = Table(
    "read_analyses",
    metadata,
    Column("analysis_id", Text, primary_key=True, nullable=True),
    Column(
        "task_id", Text, ForeignKey("read_tasks.task_id"), nullable=False, unique=True
    ),
    Column(
        "attempt_id",
        Text,
        ForeignKey("read_outcomes.attempt_id"),
        nullable=False,
        unique=True,
    ),
    Column(
        "candidate_artifact_id",
        Text,
        ForeignKey("artifacts.artifact_id"),
        nullable=False,
    ),
    Column("candidate_sha256", Text, nullable=False),
    Column("output_json", Text, nullable=False),
    Column("degrade_policy", Text, nullable=False),
    Column("attempt_ordinal", Integer, nullable=False),
    Column("evidence_rule_version", Text, nullable=False),
    Column("numeric_rule_version", Text, nullable=False),
    Column("limitation_rule_version", Text, nullable=False),
    Column("discards_json", Text, nullable=False),
    Column("diagnostics_json", Text, nullable=False),
    Column("warnings_json", Text, nullable=False),
    Column("executor_kind", Text, nullable=False),
    Column("audit_json", Text, nullable=False),
    Column("settled_at", Text, nullable=False),
    CheckConstraint("attempt_ordinal IN (1,2)"),
    CheckConstraint("executor_kind IN ('test','pi_rpc')"),
)

read_evidence = Table(
    "read_evidence",
    metadata,
    Column(
        "analysis_id", Text, ForeignKey("read_analyses.analysis_id"), primary_key=True
    ),
    Column("evidence_id", Text, primary_key=True),
    Column("artifact_id", Text, ForeignKey("artifacts.artifact_id"), nullable=False),
)
