"""B PDF 所有者归属/合法性确认及原子样本关联。"""

from alembic import op

revision = "b003_pdf_confirmations"
down_revision = "b002_delegated_acceptances"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE experiment_pdf_confirmations (
        confirmation_id TEXT NOT NULL PRIMARY KEY,
        request_id TEXT NOT NULL UNIQUE,
        selection_id TEXT NOT NULL REFERENCES experiment_selections(selection_id),
        acceptance_id TEXT NOT NULL REFERENCES experiment_acceptances(acceptance_id),
        paper_id TEXT NOT NULL REFERENCES papers(paper_id),
        version_id TEXT NOT NULL REFERENCES paper_versions(version_id),
        record_json TEXT NOT NULL)""")
    op.execute("""ALTER TABLE body_pdfs ADD COLUMN confirmation_id TEXT
        REFERENCES experiment_pdf_confirmations(confirmation_id)""")
    op.execute("""CREATE TABLE experiment_frozen_samples (
        confirmation_id TEXT NOT NULL PRIMARY KEY
            REFERENCES experiment_pdf_confirmations(confirmation_id),
        attachment_id TEXT NOT NULL UNIQUE REFERENCES body_pdfs(attachment_id),
        sample_id TEXT NOT NULL UNIQUE REFERENCES body_samples(sample_id))""")
    for table, keys in (
        ("experiment_pdf_confirmations", ("confirmation_id", "request_id")),
        (
            "experiment_frozen_samples",
            ("confirmation_id", "attachment_id", "sample_id"),
        ),
    ):
        duplicates = " OR ".join(f"{key}=NEW.{key}" for key in keys)
        op.execute(f"""CREATE TRIGGER {table}_append BEFORE INSERT ON {table}
            WHEN EXISTS (SELECT 1 FROM {table} WHERE {duplicates})
            BEGIN SELECT RAISE(ABORT, 'append_only'); END""")
        for action in ("UPDATE", "DELETE"):
            op.execute(f"""CREATE TRIGGER {table}_no_{action.lower()}
                BEFORE {action} ON {table} BEGIN
                SELECT RAISE(ABORT, 'append_only'); END""")


def downgrade() -> None:
    op.execute("DROP TABLE experiment_frozen_samples")
    op.execute("ALTER TABLE body_pdfs DROP COLUMN confirmation_id")
    op.execute("DROP TABLE experiment_pdf_confirmations")
