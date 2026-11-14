"""所有者授权的只追加正文选择;预算和旧正文保持。"""

from alembic import op

revision = "b008_body_selection"
down_revision = "b007_exposure"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE body_selections (
        body_selection_id TEXT NOT NULL PRIMARY KEY,
        request_id TEXT NOT NULL UNIQUE,
        request_hash TEXT NOT NULL,
        root_id TEXT NOT NULL REFERENCES body_root(root_id),
        paper_id TEXT NOT NULL REFERENCES papers(paper_id),
        version_id TEXT NOT NULL,
        revision_no INTEGER NOT NULL,
        sequence INTEGER NOT NULL CHECK(sequence>0),
        sample_id TEXT NOT NULL REFERENCES body_samples(sample_id),
        attachment_id TEXT NOT NULL REFERENCES body_pdfs(attachment_id),
        authorization_id TEXT NOT NULL REFERENCES experiment_selections(selection_id),
        pdf_sha256 TEXT NOT NULL,
        fingerprint TEXT NOT NULL REFERENCES body_extraction_successes(fingerprint),
        reading_sha256 TEXT NOT NULL,
        evidence_map_sha256 TEXT NOT NULL,
        selector TEXT NOT NULL CHECK(selector='owner'),
        recorder TEXT NOT NULL CHECK(recorder='agent'),
        selected_at TEXT NOT NULL,
        UNIQUE(paper_id,sequence),
        FOREIGN KEY(paper_id,version_id) REFERENCES paper_versions(paper_id,version_id),
        FOREIGN KEY(version_id,revision_no)
          REFERENCES paper_version_revisions(version_id,revision_no))""")
    op.execute("""CREATE TRIGGER body_selections_append
        BEFORE INSERT ON body_selections
        WHEN EXISTS (SELECT 1 FROM body_selections WHERE
          body_selection_id=NEW.body_selection_id OR request_id=NEW.request_id
          OR (paper_id=NEW.paper_id AND sequence=NEW.sequence))
        BEGIN SELECT RAISE(ABORT, 'append_only'); END""")
    for action in ("UPDATE", "DELETE"):
        op.execute(f"""CREATE TRIGGER body_selections_no_{action.lower()}
            BEFORE {action} ON body_selections
            BEGIN SELECT RAISE(ABORT, 'append_only'); END""")


def downgrade() -> None:
    op.execute("DROP TABLE body_selections")
