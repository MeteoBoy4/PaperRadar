"""不可变语言派生依据及 value 预算关联。"""

from alembic import op

revision = "feed02_title_language"
down_revision = "feed01_identity_conflicts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE title_language_policies (
        policy_version TEXT PRIMARY KEY NOT NULL, mapping_json TEXT NOT NULL
    )""")
    op.get_bind().exec_driver_sql("""INSERT INTO title_language_policies VALUES
        ('v1','{"aies":false,"dqkx":true,"jgr":false,"qjrms":false}')""")
    op.execute("""CREATE TABLE feed_journal_bindings (
        feed_id VARCHAR(36) PRIMARY KEY NOT NULL REFERENCES feeds(feed_id),
        journal TEXT NOT NULL CHECK(journal IN ('dqkx','aies','jgr','qjrms'))
    )""")
    op.execute("""CREATE TABLE title_language_resolutions (
        resolution_id VARCHAR(64) PRIMARY KEY NOT NULL,
        paper_id VARCHAR(36) NOT NULL REFERENCES papers(paper_id),
        policy_version TEXT NOT NULL REFERENCES title_language_policies(policy_version),
        basis_json TEXT NOT NULL
    )""")
    op.execute("""CREATE TABLE screening_language_basis (
        budget_id VARCHAR(36) PRIMARY KEY NOT NULL
            REFERENCES screening_budgets(budget_id),
        resolution_id VARCHAR(64) NOT NULL
            REFERENCES title_language_resolutions(resolution_id)
    )""")


def downgrade() -> None:
    raise RuntimeError("语言依据只追加；不支持降级")
