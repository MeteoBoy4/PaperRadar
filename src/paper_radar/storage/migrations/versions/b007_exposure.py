"""不可改写的内容寻址暴露导出登记。"""

from alembic import op

revision = "b007_exposure"
down_revision = "b006_reports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE exposure_exports (
        export_id TEXT NOT NULL PRIMARY KEY CHECK(length(export_id)=64),
        root_id TEXT NOT NULL,
        format_version INTEGER NOT NULL CHECK(format_version=1),
        artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
        audit_sha256 TEXT NOT NULL CHECK(length(audit_sha256)=64),
        scope_json TEXT NOT NULL)""")
    for action in ("UPDATE", "DELETE"):
        op.execute(f"""CREATE TRIGGER exposure_exports_no_{action.lower()}
            BEFORE {action} ON exposure_exports
            BEGIN SELECT RAISE(ABORT, 'append_only'); END""")


def downgrade() -> None:
    op.execute("DROP TABLE exposure_exports")
