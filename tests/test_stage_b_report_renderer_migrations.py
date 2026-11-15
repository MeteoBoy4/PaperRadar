"""#185 D1:冻结的非空 b008/v1 根升级、Schema 一致性和冷恢复。"""

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import CheckConstraint, UniqueConstraint, inspect
from typer.testing import CliRunner

from paper_radar.cli import app
from paper_radar.storage import database as database_module
from paper_radar.storage.database import DatabaseMode, open_database, upgrade_database
from paper_radar.storage.errors import StorageError
from paper_radar.storage.schema import report_entries, report_runs
from tests.artifact_support import fail_sql
from tests.migration_expectations import EXPECTED_MIGRATION_REVISION

FIXTURE = Path(__file__).parent / "fixtures/stage_b_report_v1.zip"


def legacy_root(tmp_path: Path) -> Path:
    assert (
        hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
        == "27e3f911f0092fc8afd223afd781c99376071864f19f4c39f97b224ece0c049d"
    )
    root = tmp_path / "legacy"
    with zipfile.ZipFile(FIXTURE) as archive:
        archive.extractall(root)
        for member in archive.infolist():
            (root / member.filename).chmod((member.external_attr >> 16) & 0o777)
    return root


def database_facts(
    database: Path,
) -> tuple[list[tuple[object, ...]], list[tuple[str, list[tuple[object, ...]]]]]:
    with sqlite3.connect(database) as connection:
        schema = connection.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"
        ).fetchall()
        rows = [
            (
                name,
                connection.execute(f'SELECT * FROM "{name}" ORDER BY rowid').fetchall(),
            )
            for (name,) in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        ]
    return schema, rows


@pytest.mark.parametrize(
    "stop",
    [
        None,
        "CREATE TABLE report_runs_b009",
        "INSERT INTO report_entries_b009",
        "DROP TABLE report_runs",
        "ALTER TABLE report_entries_b009",
        "CREATE TRIGGER report_runs_publish_only",
        "UPDATE alembic_version",
    ],
)
def test_nonempty_b008_upgrade_is_atomic_and_preserves_all_history(
    tmp_path: Path, stop: str | None
) -> None:
    root = legacy_root(tmp_path)
    database = root / "paper-radar.sqlite3"
    before = database_facts(database)
    if stop:
        with fail_sql(stop), pytest.raises(StorageError) as error:
            upgrade_database(database)
        assert error.value.reason == "upgrade_failed"
        assert database_facts(database) == before
    assert upgrade_database(database) == EXPECTED_MIGRATION_REVISION
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute("SELECT count(*) FROM report_entries").fetchone() == (
            1,
        )
        assert connection.execute(
            "SELECT renderer_version FROM report_runs"
        ).fetchall() == [(1,)]
    after = database_facts(database)
    assert before[1][1:] == after[1][1:]  # alembic_version 是按名称排列的首表。


def test_report_schema_matches_metadata_and_keeps_constraints(tmp_path: Path) -> None:
    root = legacy_root(tmp_path)
    database = root / "paper-radar.sqlite3"
    upgrade_database(database)
    engine = open_database(database, mode=DatabaseMode.READ_WRITE)
    try:
        inspector = inspect(engine)

        def normalize(value: str) -> str:
            return "".join(value.lower().replace('"', "").split())

        for table in (report_runs, report_entries):
            reflected = inspector.get_columns(table.name)
            assert {
                (c["name"], str(c["type"]).upper(), c["nullable"]) for c in reflected
            } == {(c.name, str(c.type).upper(), c.nullable) for c in table.columns}
            assert inspector.get_pk_constraint(table.name)["constrained_columns"] == [
                c.name for c in table.primary_key
            ]
            assert {
                tuple(c["column_names"])
                for c in inspector.get_unique_constraints(table.name)
            } == {
                tuple(c.name for c in u.columns)
                for u in table.constraints
                if isinstance(u, UniqueConstraint)
            }
            assert {
                (
                    tuple(f["constrained_columns"]),
                    f["referred_table"],
                    tuple(f["referred_columns"]),
                )
                for f in inspector.get_foreign_keys(table.name)
            } == {
                (
                    tuple(c.parent.name for c in f.elements),
                    f.elements[0].target_fullname.split(".")[0],
                    tuple(c.target_fullname.split(".")[1] for c in f.elements),
                )
                for f in table.foreign_key_constraints
            }
            assert {
                normalize(c["sqltext"])
                for c in inspector.get_check_constraints(table.name)
            } == {
                normalize(str(c.sqltext))
                for c in table.constraints
                if isinstance(c, CheckConstraint)
            }
    finally:
        engine.dispose()
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        assert connection.execute("PRAGMA foreign_keys").fetchone() == (1,)
        for sql in [
            "DELETE FROM report_runs",
            "DELETE FROM report_entries",
            "UPDATE report_entries SET position=2",
            "UPDATE report_runs SET content_sha256='bad'",
        ]:
            with pytest.raises(sqlite3.IntegrityError, match="append_only"):
                connection.execute(sql)
        row = list(connection.execute("SELECT * FROM report_runs").fetchone())
        row[0], row[1], row[9], row[8] = "new-report", "new-run", "new/path.md", 3
        with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
            connection.execute(
                f"INSERT INTO report_runs VALUES ({','.join('?' for _ in row)})", row
            )
        row[8] = 2
        connection.execute(
            f"INSERT INTO report_runs VALUES ({','.join('?' for _ in row)})", row
        )
        connection.rollback()


def test_v1_upgrade_backup_and_cold_restore_keep_exact_report_bytes(
    tmp_path: Path,
) -> None:
    root = legacy_root(tmp_path)
    database = root / "paper-radar.sqlite3"
    before = next((root / "views/2026-11-14").glob("*.md")).read_bytes()
    assert (
        hashlib.sha256(before).hexdigest()
        == "4c0c27698af9ee63d1b1b6a22a87ca58ce7cea6d57e18000f26aa0a48265d8e6"
    )
    upgrade_database(database)
    with sqlite3.connect(database) as connection:
        report_id, relative = connection.execute(
            "SELECT report_id,relative_path FROM report_runs"
        ).fetchone()
    verify = CliRunner().invoke(
        app, ["experiment", "report", "verify", report_id, "--root", str(root)]
    )
    assert verify.exit_code == 0, verify.output
    backup = CliRunner().invoke(
        app,
        [
            "backup",
            "create",
            "--database",
            str(database),
            "--data-root",
            str(root / "data"),
            "--output",
            str(tmp_path / "backups"),
        ],
    )
    assert backup.exit_code == 0, backup.output
    (batch,) = (tmp_path / "backups").iterdir()
    (root / "config").mkdir()
    (root / "config/sentinel").write_text("synthetic original config")
    materials = tmp_path / "materials"
    materials.mkdir()
    (materials / "sentinel").write_text("synthetic original materials")
    target = tmp_path / "restored"
    code = """
import socket, ssl
def denied(*args, **kwargs): raise AssertionError('external I/O forbidden')
socket.socket = denied
from paper_radar.cli import app
app()
"""
    restored = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
            "restore",
            "verify",
            str(batch),
            "--target",
            str(target),
            "--replay-container",
        ],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert restored.returncode == 0, restored.stdout + restored.stderr
    replayed = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
            "replay",
            "--restored",
            str(target),
            "--original-database",
            str(database),
            "--original-data-root",
            str(root / "data"),
            "--original-config-root",
            str(root / "config"),
            "--original-material-root",
            str(materials),
        ],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert replayed.returncode == 0, replayed.stdout + replayed.stderr
    isolation = json.loads(replayed.stdout)
    assert isolation["isolation"] == "verified"
    assert isolation["missing_originals"] == 0
    assert isolation["originals_denied"] >= 4
    assert (target / "views" / relative).read_bytes() == before


def test_renderer_v2_downgrade_refuses_without_losing_history(tmp_path: Path) -> None:
    root = legacy_root(tmp_path)
    database = root / "paper-radar.sqlite3"
    upgrade_database(database)
    with sqlite3.connect(database) as connection:
        row = list(connection.execute("SELECT * FROM report_runs").fetchone())
        row[0], row[1], row[9], row[8] = "v2-report", "v2-run", "v2/path.md", 2
        connection.execute(
            f"INSERT INTO report_runs VALUES ({','.join('?' for _ in row)})", row
        )
    before = database_facts(database)
    config = Config()
    config.set_main_option(
        "script_location", str(Path(database_module.__file__).parent / "migrations")
    )
    engine = open_database(database, mode=DatabaseMode.READ_WRITE)
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            config.attributes["connection"] = connection
            with pytest.raises(ValueError, match="renderer_v2_history_present"):
                command.downgrade(config, "b008_body_selection")
            connection.rollback()
    finally:
        engine.dispose()
    assert database_facts(database) == before
