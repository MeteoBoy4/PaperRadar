"""B-E4 独立 D1:非空上一 revision 原子升级,人工 head 预期。"""

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from paper_radar.body import BodyService
from paper_radar.storage import database as database_module
from paper_radar.storage.database import DatabaseMode, open_database, upgrade_database
from paper_radar.storage.errors import StorageError
from tests.artifact_support import fail_sql
from tests.migration_expectations import EXPECTED_MIGRATION_REVISION


@pytest.mark.parametrize(
    "stop",
    [
        None,
        "CREATE TABLE experiment_selections",
        "CREATE TRIGGER experiment_selections_no_delete",
        "UPDATE alembic_version",
    ],
)
def test_previous_nonempty_revision_upgrade_is_atomic(
    tmp_path: Path, stop: str | None
) -> None:
    database = tmp_path / "previous.sqlite3"
    upgrade_database(database)
    original = BodyService(database, tmp_path).register_root("experiment")
    config = Config()
    config.set_main_option(
        "script_location", str(Path(database_module.__file__).parent / "migrations")
    )
    engine = open_database(database, mode=DatabaseMode.READ_WRITE)
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            config.attributes["connection"] = connection
            # 固定历史节点;不得由当前生产 head 推导上一 revision。
            command.downgrade(config, "body02_read_tasks")
            connection.commit()
    finally:
        engine.dispose()
    if stop is not None:
        with fail_sql(stop), pytest.raises(StorageError) as caught:
            upgrade_database(database)
        assert caught.value.reason == "upgrade_failed"
        with sqlite3.connect(database) as connection:
            assert connection.execute(
                "SELECT version_num FROM alembic_version"
            ).fetchone() == ("body02_read_tasks",)
            assert (
                connection.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE name LIKE 'experiment_selections%'"
                ).fetchall()
                == []
            )
    assert upgrade_database(database) == EXPECTED_MIGRATION_REVISION
    assert BodyService(database, tmp_path).root() == original
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
