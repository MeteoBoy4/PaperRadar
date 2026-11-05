"""D1第二线性迁移从非空Body上一revision原子升级。"""

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from paper_radar.storage import database as database_module
from paper_radar.storage.database import DatabaseMode, open_database, upgrade_database
from paper_radar.storage.errors import StorageError
from tests.artifact_support import fail_sql
from tests.migration_expectations import EXPECTED_MIGRATION_REVISION


@pytest.mark.parametrize(
    "stop", [None, "CREATE TABLE read_tasks", "UPDATE alembic_version"]
)
def test_nonempty_body_revision_upgrades_atomically(
    tmp_path: Path, stop: str | None
) -> None:
    database = tmp_path / "old.sqlite3"
    config = Config()
    config.set_main_option(
        "script_location", str(Path(database_module.__file__).parent / "migrations")
    )
    engine = open_database(database, mode=DatabaseMode.CREATE)
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            config.attributes["connection"] = connection
            command.upgrade(config, "body01_persistence")
            connection.commit()
    finally:
        engine.dispose()
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO body_root VALUES(1,'root','experiment','2026-01-01','hash')"
        )
    if stop:
        with fail_sql(stop), pytest.raises(StorageError) as caught:
            upgrade_database(database)
        assert caught.value.reason == "upgrade_failed"
        with sqlite3.connect(database) as connection:
            assert connection.execute(
                "SELECT version_num FROM alembic_version"
            ).fetchone() == ("body01_persistence",)
            assert not connection.execute(
                "SELECT 1 FROM sqlite_master WHERE name='read_budgets'"
            ).fetchall()
            assert "executor_audit_json" not in {
                r[1]
                for r in connection.execute(
                    "PRAGMA table_info(body_extraction_attempts)"
                )
            }
    assert upgrade_database(database) == EXPECTED_MIGRATION_REVISION
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT root_id FROM body_root").fetchone() == (
            "root",
        )
        assert "executor_audit_json" in {
            r[1]
            for r in connection.execute("PRAGMA table_info(body_extraction_attempts)")
        }
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
