"""保留强身份冲突拒绝的独立证据。"""

from alembic import op

revision = "feed01_identity_conflicts"
down_revision = "a1001_fixture_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE paper_identity_conflicts (
        conflict_id VARCHAR(64) PRIMARY KEY NOT NULL,
        request_sha256 VARCHAR(64) NOT NULL UNIQUE,
        artifact_id VARCHAR(64) NOT NULL REFERENCES artifacts(artifact_id),
        assertion_json TEXT NOT NULL,
        payload_sha256 VARCHAR(64) NOT NULL,
        conflict VARCHAR(32) NOT NULL CHECK(conflict IN
          ('doi_owner_conflict','target_mismatch','version_kind_conflict','entry_doi_changed')),
        version_ids_json TEXT NOT NULL
    )""")


def downgrade() -> None:
    op.drop_table("paper_identity_conflicts")
