"""Body 表的查询描述;DDL 仅由不可变 migration 管理。"""

from sqlalchemy import TableClause, column, table


def body_table(name: str, names: str) -> TableClause:
    return table("body_" + name, *(column(name) for name in names.split()))


roots = body_table("root", "singleton root_id purpose registered_at registration_hash")
decisions = body_table(
    "decisions",
    "decision_id request_id request_hash paper_id version_id "
    "revision_no sequence record_json actor decided_at",
)
decision_screenings = body_table("decision_screenings", "decision_id success_id")
pdfs = body_table(
    "pdfs",
    "attachment_id request_id request_hash paper_id version_id "
    "sequence artifact_id pdf_sha256 attached_at access_basis "
    "requested_version_id",
)
samples = body_table(
    "samples",
    "sample_id request_id request_hash paper_id version_id sequence "
    "feed_id pdf_sha256 reason frozen_at",
)
inputs = body_table(
    "extraction_inputs", "fingerprint backend pdf_sha256 snapshot_id payload"
)
attempts = body_table(
    "extraction_attempts",
    "attempt_id fingerprint backend ordinal claimed_at executor_audit_json",
)
outcomes = body_table(
    "extraction_outcomes",
    "attempt_id failure artifact_id reading_sha256 evidence_map_sha256 "
    "quality_failure elapsed_seconds peak_memory_bytes settled_at",
)
successes = body_table("extraction_successes", "fingerprint attempt_id")
reviews = body_table(
    "layout_reviews",
    "review_id request_id request_hash fingerprint reading_sha256 "
    "evidence_map_sha256 passed checks_json note actor reviewed_at",
)
