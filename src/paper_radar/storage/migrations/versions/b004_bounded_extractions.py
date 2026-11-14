"""B 有界提取领取事实及独立 cgroup 历史峰值观察。"""

from alembic import op

revision = "b004_bounded_extractions"
down_revision = "b003_pdf_confirmations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE experiment_extractions (
        attempt_id TEXT NOT NULL PRIMARY KEY
            REFERENCES body_extraction_attempts(attempt_id),
        sample_id TEXT NOT NULL REFERENCES body_samples(sample_id),
        paper_id TEXT NOT NULL REFERENCES papers(paper_id),
        record_json TEXT NOT NULL)""")
    op.execute("""CREATE TABLE experiment_extraction_peaks (
        attempt_id TEXT NOT NULL PRIMARY KEY
            REFERENCES experiment_extractions(attempt_id),
        cgroup_peak_bytes INTEGER)""")
    for table in ("experiment_extractions", "experiment_extraction_peaks"):
        op.execute(f"""CREATE TRIGGER {table}_append BEFORE INSERT ON {table}
            WHEN EXISTS (SELECT 1 FROM {table} WHERE attempt_id=NEW.attempt_id)
            BEGIN SELECT RAISE(ABORT, 'append_only'); END""")
        for action in ("UPDATE", "DELETE"):
            op.execute(f"""CREATE TRIGGER {table}_no_{action.lower()}
                BEFORE {action} ON {table} BEGIN
                SELECT RAISE(ABORT, 'append_only'); END""")


def downgrade() -> None:
    op.execute("DROP TABLE experiment_extraction_peaks")
    op.execute("DROP TABLE experiment_extractions")
