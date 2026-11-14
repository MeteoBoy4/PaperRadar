"""所有者核查与 Agent 代录追加关联。"""

from alembic import op

revision = "b005_layout_recordings"
down_revision = "b004_bounded_extractions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE body_layout_reviews ADD COLUMN recording_kind TEXT")
    op.execute("""CREATE TABLE experiment_layout_recordings (
        review_id TEXT NOT NULL PRIMARY KEY REFERENCES body_layout_reviews(review_id),
        sample_id TEXT NOT NULL REFERENCES body_samples(sample_id),
        paper_id TEXT NOT NULL REFERENCES papers(paper_id),
        record_json TEXT NOT NULL)""")
    op.execute("""CREATE TRIGGER experiment_layout_recordings_append
        BEFORE INSERT ON experiment_layout_recordings
        WHEN EXISTS (SELECT 1 FROM experiment_layout_recordings WHERE
            review_id=NEW.review_id)
        BEGIN SELECT RAISE(ABORT, 'append_only'); END""")
    for action in ("UPDATE", "DELETE"):
        op.execute(f"""CREATE TRIGGER experiment_layout_recordings_no_{action.lower()}
            BEFORE {action} ON experiment_layout_recordings BEGIN
            SELECT RAISE(ABORT, 'append_only'); END""")


def downgrade() -> None:
    op.execute("DROP TABLE experiment_layout_recordings")
    op.execute("ALTER TABLE body_layout_reviews DROP COLUMN recording_kind")
