"""B 实验选样与接受授权只追加单链。"""

from alembic import op

revision = "b001_selection_authorizations"
down_revision = "body02_read_tasks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE experiment_selections (
        sequence INTEGER NOT NULL PRIMARY KEY CHECK(sequence>0),
        selection_id TEXT NOT NULL UNIQUE,
        request_id TEXT NOT NULL UNIQUE,
        replaces TEXT UNIQUE REFERENCES experiment_selections(selection_id),
        view_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
        paper_id TEXT NOT NULL REFERENCES papers(paper_id),
        version_id TEXT NOT NULL REFERENCES paper_versions(version_id),
        record_json TEXT NOT NULL)""")
    op.execute("""CREATE TRIGGER experiment_selections_append
        BEFORE INSERT ON experiment_selections
        WHEN NEW.sequence != COALESCE(
            (SELECT MAX(sequence) FROM experiment_selections),0)+1
        OR NEW.replaces IS NOT (
            SELECT selection_id FROM experiment_selections
            ORDER BY sequence DESC LIMIT 1)
        OR EXISTS (SELECT 1 FROM experiment_selections
            WHERE request_id=NEW.request_id OR selection_id=NEW.selection_id)
        BEGIN SELECT RAISE(ABORT, 'append_only'); END""")
    for action in ("UPDATE", "DELETE"):
        op.execute(f"""CREATE TRIGGER experiment_selections_no_{action.lower()}
            BEFORE {action} ON experiment_selections BEGIN
            SELECT RAISE(ABORT, 'append_only'); END""")


def downgrade() -> None:
    op.execute("DROP TABLE experiment_selections")
