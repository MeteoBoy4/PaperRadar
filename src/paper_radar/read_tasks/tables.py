"""Read查询描述;DDL仅由migration管理。"""

from sqlalchemy import TableClause, column, table


def read_table(name: str, names: str) -> TableClause:
    return table("read_" + name, *(column(n) for n in names.split()))


budgets = read_table(
    "budgets",
    "budget_id paper_id fingerprint stage snapshot_id payload "
    "extraction_fingerprint artifact_id reading_sha256 evidence_map_sha256 "
    "output_language created_at",
)
tasks = read_table(
    "tasks",
    "task_id budget_id generation parent_task_id retry_reason retry_actor created_at",
)
registrations = read_table(
    "registrations",
    "request_id request_hash request_json task_id snapshot_id label registered_at",
)
attempts = read_table(
    "attempts",
    "attempt_id task_id ordinal token claimed_at lease_until basis_json metadata_json",
)
renewals = read_table("renewals", "attempt_id sequence renewed_at lease_until")
outcomes = read_table("outcomes", "attempt_id failure issues_json settled_at")
analyses = read_table(
    "analyses",
    "analysis_id task_id attempt_id candidate_artifact_id candidate_sha256 output_json "
    "degrade_policy attempt_ordinal evidence_rule_version numeric_rule_version "
    "limitation_rule_version discards_json diagnostics_json warnings_json "
    "executor_kind audit_json settled_at",
)
evidence = read_table("evidence", "analysis_id evidence_id artifact_id")
