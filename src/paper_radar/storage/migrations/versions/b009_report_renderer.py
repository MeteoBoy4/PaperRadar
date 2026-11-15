"""为冻结报告新增 renderer v2;保留 v1 与全部历史成员。"""

from alembic import op

revision = "b009_report_renderer"
down_revision = "b008_body_selection"
branch_labels = None
depends_on = None


def _replace(*, upgrading: bool) -> None:
    # DDL 固定于本 migration,不从运行时 SQLAlchemy metadata 派生。
    parent = """CREATE TABLE report_runs_b009 (
        report_id TEXT NOT NULL PRIMARY KEY,
        run_key TEXT NOT NULL UNIQUE,
        kind TEXT NOT NULL CHECK(kind IN ('daily','paper')),
        scope TEXT NOT NULL CHECK(scope='experiment'),
        report_date TEXT NOT NULL,
        timezone TEXT NOT NULL,
        input_fingerprint TEXT NOT NULL,
        projection_json TEXT NOT NULL,
        renderer_version INTEGER NOT NULL CHECK(renderer_version IN (1,2)),
        relative_path TEXT NOT NULL UNIQUE,
        content_sha256 TEXT NOT NULL,
        state TEXT NOT NULL CHECK(state IN ('prepared','published')),
        published_at TEXT)"""
    if not upgrading:
        if (
            op.get_bind()
            .exec_driver_sql(
                "SELECT 1 FROM report_runs WHERE renderer_version=2 LIMIT 1"
            )
            .first()
            is not None
        ):
            raise ValueError("renderer_v2_history_present")
        parent = parent.replace(
            "CHECK(renderer_version IN (1,2))", "CHECK(renderer_version=1)"
        )
    op.execute(parent)
    op.execute("""CREATE TABLE report_entries_b009 (
        report_id TEXT NOT NULL REFERENCES report_runs_b009(report_id),
        position INTEGER NOT NULL CHECK(position BETWEEN 1 AND 5),
        display_number TEXT NOT NULL
            CHECK(display_number IN ('N1','N2','N3','N4','N5')),
        paper_id TEXT NOT NULL REFERENCES papers(paper_id),
        version_id TEXT NOT NULL REFERENCES paper_versions(version_id),
        revision_no INTEGER NOT NULL CHECK(revision_no>0),
        primary_kind TEXT NOT NULL
            CHECK(primary_kind IN ('analysis','pending','blocked')),
        primary_ref TEXT NOT NULL,
        analysis_id TEXT REFERENCES read_analyses(analysis_id),
        supporting_success_id TEXT REFERENCES screening_successes(success_id),
        section TEXT NOT NULL
            CHECK(section IN ('transferable','cognitive','pending','blocked')),
        first_publication_key TEXT NOT NULL,
        daily_first_key TEXT UNIQUE,
        projection_json TEXT NOT NULL,
        PRIMARY KEY(report_id,position),
        UNIQUE(report_id,first_publication_key),
        UNIQUE(report_id,display_number),
        FOREIGN KEY(version_id,revision_no)
            REFERENCES paper_version_revisions(version_id,revision_no))""")
    op.execute(
        "INSERT INTO report_runs_b009 (report_id,run_key,kind,scope,"
        "report_date,timezone,input_fingerprint,projection_json,"
        "renderer_version,relative_path,content_sha256,state,published_at) "
        "SELECT report_id,run_key,kind,scope,report_date,timezone,"
        "input_fingerprint,projection_json,renderer_version,relative_path,"
        "content_sha256,state,published_at FROM "
        "report_runs"
    )
    op.execute(
        "INSERT INTO report_entries_b009 (report_id,position,"
        "display_number,paper_id,version_id,revision_no,primary_kind,"
        "primary_ref,analysis_id,supporting_success_id,section,"
        "first_publication_key,daily_first_key,projection_json) SELECT "
        "report_id,position,display_number,paper_id,version_id,revision_no,"
        "primary_kind,primary_ref,analysis_id,supporting_success_id,"
        "section,first_publication_key,daily_first_key,projection_json "
        "FROM "
        "report_entries"
    )
    # 外键始终开启;先移除旧 child,随后替换 parent 和 child。
    op.execute("DROP TABLE report_entries")
    op.execute("DROP TABLE report_runs")
    op.execute("ALTER TABLE report_runs_b009 RENAME TO report_runs")
    op.execute("ALTER TABLE report_entries_b009 RENAME TO report_entries")
    for table in ("report_runs", "report_entries"):
        op.execute(f"""CREATE TRIGGER {table}_no_delete BEFORE DELETE ON {table}
            BEGIN SELECT RAISE(ABORT, 'append_only'); END""")
    op.execute("""CREATE TRIGGER report_entries_no_update
        BEFORE UPDATE ON report_entries
        BEGIN SELECT RAISE(ABORT, 'append_only'); END""")
    op.execute("""CREATE TRIGGER report_runs_publish_only BEFORE UPDATE ON report_runs
        WHEN OLD.state!='prepared' OR NEW.state!='published' OR NEW.published_at IS NULL
        OR OLD.report_id IS NOT NEW.report_id OR OLD.run_key IS NOT NEW.run_key
        OR OLD.kind IS NOT NEW.kind OR OLD.scope IS NOT NEW.scope
        OR OLD.report_date IS NOT NEW.report_date OR OLD.timezone IS NOT NEW.timezone
        OR OLD.input_fingerprint IS NOT NEW.input_fingerprint
        OR OLD.projection_json IS NOT NEW.projection_json
        OR OLD.renderer_version IS NOT NEW.renderer_version
        OR OLD.relative_path IS NOT NEW.relative_path
        OR OLD.content_sha256 IS NOT NEW.content_sha256
        BEGIN SELECT RAISE(ABORT, 'append_only'); END""")

    if op.get_bind().exec_driver_sql("PRAGMA foreign_key_check").first() is not None:
        raise ValueError("report_foreign_key_invalid")


def upgrade() -> None:
    _replace(upgrading=True)


def downgrade() -> None:
    _replace(upgrading=False)
