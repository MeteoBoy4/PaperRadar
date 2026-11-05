"""Body D1:上一非空 revision 升级与失败事务完整性。"""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from paper_radar.body import BodyService
from paper_radar.storage import database as database_module
from paper_radar.storage.database import DatabaseMode, open_database, upgrade_database
from paper_radar.storage.errors import StorageError
from tests.artifact_support import fail_sql
from tests.body_support import body_archive
from tests.migration_expectations import EXPECTED_MIGRATION_REVISION


def previous_copy(source: Path, target: Path) -> dict[str, list[tuple[object, ...]]]:
    config = Config()
    config.set_main_option(
        "script_location", str(Path(database_module.__file__).parent / "migrations")
    )
    engine = open_database(target, mode=DatabaseMode.CREATE)
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            config.attributes["connection"] = connection
            command.upgrade(config, "feed07_parser_versions")
            connection.commit()
    finally:
        engine.dispose()
    with (
        closing(sqlite3.connect(source)) as original,
        closing(sqlite3.connect(target)) as previous,
    ):
        names = [
            row[0]
            for row in previous.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name!='alembic_version' ORDER BY name"
            )
        ]
        expected = {
            name: original.execute(f"SELECT * FROM {name}").fetchall() for name in names
        }
        for name, rows in expected.items():
            previous.execute(f"DELETE FROM {name}")
            if rows:
                previous.executemany(
                    f"INSERT INTO {name} VALUES ({','.join('?' for _ in rows[0])})",
                    rows,
                )
        previous.commit()
    return expected


@pytest.mark.parametrize(
    "stop", [None, "CREATE TABLE body_root", "UPDATE alembic_version"]
)
def test_nonempty_previous_revision_upgrade_is_atomic(
    tmp_path: Path, stop: str | None
) -> None:
    source = body_archive(tmp_path / "source")
    target = tmp_path / "previous.sqlite3"
    expected = previous_copy(source.database, target)
    if stop:
        with fail_sql(stop), pytest.raises(StorageError) as error:
            upgrade_database(target)
        assert error.value.reason == "upgrade_failed"
        with closing(sqlite3.connect(target)) as connection:
            assert connection.execute(
                "SELECT version_num FROM alembic_version"
            ).fetchone() == ("feed07_parser_versions",)
            assert not connection.execute(
                "SELECT 1 FROM sqlite_master WHERE name='body_root'"
            ).fetchall()
    assert upgrade_database(target) == EXPECTED_MIGRATION_REVISION
    with closing(sqlite3.connect(target)) as connection:
        assert {
            name: connection.execute(f"SELECT * FROM {name}").fetchall()
            for name in expected
        } == expected
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    service = BodyService(target, source.data_root)
    service.register_root("experiment")
    service.validate_all()
