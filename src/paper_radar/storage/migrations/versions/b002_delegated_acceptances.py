"""B 预先选样授权与代执行决定的只追加关联。"""

from alembic import op

revision = "b002_delegated_acceptances"
down_revision = "b001_selection_authorizations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""ALTER TABLE body_decisions ADD COLUMN delegation_kind TEXT
        CHECK(delegation_kind IS NULL OR delegation_kind='stage_b_preselection')""")
    op.execute("""CREATE TABLE experiment_acceptances (
        acceptance_id TEXT NOT NULL PRIMARY KEY,
        request_id TEXT NOT NULL UNIQUE,
        selection_id TEXT NOT NULL UNIQUE
            REFERENCES experiment_selections(selection_id),
        decision_id TEXT NOT NULL UNIQUE REFERENCES body_decisions(decision_id),
        boundary_success_id TEXT NOT NULL REFERENCES screening_successes(success_id),
        value_success_id TEXT NOT NULL REFERENCES screening_successes(success_id),
        record_json TEXT NOT NULL)""")
    op.execute("""CREATE TRIGGER experiment_acceptances_append
        BEFORE INSERT ON experiment_acceptances
        WHEN EXISTS (SELECT 1 FROM experiment_acceptances
            WHERE acceptance_id=NEW.acceptance_id OR request_id=NEW.request_id
                OR selection_id=NEW.selection_id OR decision_id=NEW.decision_id)
        BEGIN SELECT RAISE(ABORT, 'append_only'); END""")
    for action in ("UPDATE", "DELETE"):
        op.execute(f"""CREATE TRIGGER experiment_acceptances_no_{action.lower()}
            BEFORE {action} ON experiment_acceptances BEGIN
            SELECT RAISE(ABORT, 'append_only'); END""")


def downgrade() -> None:
    op.execute("DROP TABLE experiment_acceptances")
    op.execute("ALTER TABLE body_decisions DROP COLUMN delegation_kind")
