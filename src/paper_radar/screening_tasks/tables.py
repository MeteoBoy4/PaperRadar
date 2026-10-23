"""Screening 登记事实;共享 metadata,独立于论文事实。"""

import sqlalchemy as sa

from paper_radar.papers import tables as paper_tables  # noqa: F401
from paper_radar.storage.schema import metadata

inputs = sa.Table(
    "screening_inputs",
    metadata,
    sa.Column("fingerprint", sa.String(64), primary_key=True),
    sa.Column("stage", sa.String(8), nullable=False),
    sa.Column("payload", sa.LargeBinary(), nullable=False),
    sa.Column("format_version", sa.Integer(), nullable=False),
    sa.CheckConstraint("stage IN ('boundary','value')"),
    sa.CheckConstraint("format_version = 1"),
    sa.CheckConstraint("typeof(payload) = 'blob'"),
)
budgets = sa.Table(
    "screening_budgets",
    metadata,
    sa.Column("budget_id", sa.String(36), primary_key=True),
    sa.Column(
        "paper_id", sa.String(36), sa.ForeignKey("papers.paper_id"), nullable=False
    ),
    sa.Column("stage", sa.String(8), nullable=False),
    sa.Column(
        "fingerprint",
        sa.String(64),
        sa.ForeignKey("screening_inputs.fingerprint"),
        nullable=False,
    ),
    sa.Column(
        "snapshot_id",
        sa.String(64),
        sa.ForeignKey("runtime_config_snapshots.snapshot_id"),
        nullable=False,
    ),
    sa.Column("version_id", sa.String(36), nullable=False),
    sa.Column("revision_no", sa.Integer(), nullable=False),
    sa.Column(
        "selection_id",
        sa.String(36),
        sa.ForeignKey("paper_selection_events.selection_id"),
    ),
    sa.Column("original_title_is_zh", sa.Boolean()),
    sa.ForeignKeyConstraint(
        ["paper_id", "version_id"],
        ["paper_versions.paper_id", "paper_versions.version_id"],
    ),
    sa.ForeignKeyConstraint(
        ["version_id", "revision_no"],
        ["paper_version_revisions.version_id", "paper_version_revisions.revision_no"],
    ),
    sa.UniqueConstraint("paper_id", "stage", "fingerprint"),
    sa.CheckConstraint("stage IN ('boundary','value')"),
    sa.CheckConstraint(
        "(stage='boundary' AND original_title_is_zh IS NULL) OR "
        "(stage='value' AND original_title_is_zh IN (0,1) "
        "AND original_title_is_zh IS NOT NULL)"
    ),
)
tasks = sa.Table(
    "screening_tasks",
    metadata,
    sa.Column("task_id", sa.String(36), primary_key=True),
    sa.Column(
        "budget_id",
        sa.String(36),
        sa.ForeignKey("screening_budgets.budget_id"),
        nullable=False,
    ),
    sa.Column("generation", sa.Integer(), nullable=False),
    sa.Column(
        "parent_task_id",
        sa.String(36),
        sa.ForeignKey("screening_tasks.task_id"),
        unique=True,
    ),
    sa.UniqueConstraint("budget_id", "generation"),
    sa.CheckConstraint("generation >= 0"),
)
requests = sa.Table(
    "screening_requests",
    metadata,
    sa.Column("receipt_id", sa.String(64), primary_key=True),
    sa.Column("request_id", sa.Text(), unique=True),
    sa.Column("request_sha256", sa.String(64), nullable=False),
    sa.Column(
        "task_id",
        sa.String(36),
        sa.ForeignKey("screening_tasks.task_id"),
        nullable=False,
    ),
    sa.Column("source", sa.String(12), nullable=False),
    sa.Column(
        "snapshot_id",
        sa.String(64),
        sa.ForeignKey("runtime_config_snapshots.snapshot_id"),
        nullable=False,
    ),
    sa.Column("version_id", sa.String(36), nullable=False),
    sa.Column("revision_no", sa.Integer(), nullable=False),
    sa.Column(
        "selection_id",
        sa.String(36),
        sa.ForeignKey("paper_selection_events.selection_id"),
    ),
    sa.Column("scheduled_day", sa.Text()),
    sa.Column(
        "cached_success_id",
        sa.String(36),
        sa.ForeignKey("screening_successes.success_id"),
    ),
    sa.Column("reason", sa.Text()),
    sa.Column("actor", sa.Text()),
    sa.ForeignKeyConstraint(
        ["version_id", "revision_no"],
        ["paper_version_revisions.version_id", "paper_version_revisions.revision_no"],
    ),
    sa.CheckConstraint("source IN ('scheduled','manual','retry')"),
    sa.CheckConstraint(
        "(source='scheduled' AND scheduled_day IS NOT NULL AND request_id IS NULL "
        "AND reason IS NULL AND actor IS NULL) OR "
        "(source IN ('manual','retry') AND scheduled_day IS NULL "
        "AND request_id IS NOT NULL "
        "AND reason IS NOT NULL AND actor IS NOT NULL)"
    ),
)

attempts = sa.Table(
    "screening_attempts",
    metadata,
    sa.Column(
        "task_id",
        sa.String(36),
        sa.ForeignKey("screening_tasks.task_id"),
        primary_key=True,
    ),
    sa.Column("attempt_no", sa.Integer(), primary_key=True),
    sa.Column(
        "receipt_id",
        sa.String(64),
        sa.ForeignKey("screening_requests.receipt_id"),
        nullable=False,
    ),
    sa.Column("version_id", sa.String(36), nullable=False),
    sa.Column("revision_no", sa.Integer(), nullable=False),
    sa.Column(
        "selection_id",
        sa.String(36),
        sa.ForeignKey("paper_selection_events.selection_id"),
    ),
    sa.Column("claimed_at", sa.Text(), nullable=False),
    sa.Column("credential_sha256", sa.String(64), nullable=False, unique=True),
    sa.Column("renewal_sha256", sa.String(64), nullable=False, unique=True),
    sa.ForeignKeyConstraint(
        ["version_id", "revision_no"],
        ["paper_version_revisions.version_id", "paper_version_revisions.revision_no"],
    ),
    sa.CheckConstraint("attempt_no IN (1,2)"),
)
leases = sa.Table(
    "screening_leases",
    metadata,
    sa.Column("task_id", sa.String(36), primary_key=True),
    sa.Column("attempt_no", sa.Integer(), primary_key=True),
    sa.Column("expires_at", sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(
        ["task_id", "attempt_no"],
        ["screening_attempts.task_id", "screening_attempts.attempt_no"],
    ),
)
failures = sa.Table(
    "screening_failures",
    metadata,
    sa.Column("task_id", sa.String(36), primary_key=True),
    sa.Column("attempt_no", sa.Integer(), primary_key=True),
    sa.Column("issues_json", sa.Text()),
    sa.Column("submission_sha256", sa.String(64)),
    sa.Column("audit_json", sa.Text()),
    sa.Column("kind", sa.String(20), nullable=False),
    sa.Column("origin", sa.String(12), nullable=False),
    sa.Column("settled_at", sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(
        ["task_id", "attempt_no"],
        ["screening_attempts.task_id", "screening_attempts.attempt_no"],
    ),
    sa.CheckConstraint(
        "kind IN ('output_invalid','model_mismatch','timeout','cancelled',"
        "'protocol_error','executor_error','outcome_unknown')"
    ),
    sa.CheckConstraint("origin IN ('executor','exception','recovery')"),
)


successes = sa.Table(
    "screening_successes",
    metadata,
    sa.Column("success_id", sa.String(36), primary_key=True),
    sa.Column(
        "budget_id",
        sa.String(36),
        sa.ForeignKey("screening_budgets.budget_id"),
        nullable=False,
        unique=True,
    ),
    sa.Column("task_id", sa.String(36), nullable=False),
    sa.Column("attempt_no", sa.Integer(), nullable=False),
    sa.Column(
        "artifact_id",
        sa.String(64),
        sa.ForeignKey("artifacts.artifact_id"),
        nullable=False,
    ),
    sa.Column("structured_json", sa.Text(), nullable=False),
    sa.Column("submission_sha256", sa.String(64), nullable=False),
    sa.Column("audit_json", sa.Text(), nullable=False),
    sa.Column("settled_at", sa.Text(), nullable=False),
    sa.UniqueConstraint("task_id", "attempt_no"),
    sa.ForeignKeyConstraint(
        ["task_id", "attempt_no"],
        ["screening_attempts.task_id", "screening_attempts.attempt_no"],
    ),
)
