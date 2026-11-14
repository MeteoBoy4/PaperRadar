"""D1: 非空 b007 升级、DDL 原子回滚及旧暴露范围保留。"""

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from paper_radar.body import BodyService
from paper_radar.body.selection import BodySelections
from paper_radar.experiment.exposure import Exposures
from paper_radar.storage import database as database_module
from paper_radar.storage.database import DatabaseMode, open_database, upgrade_database
from paper_radar.storage.errors import StorageError
from tests.artifact_support import fail_sql
from tests.experiment_layout_support import layout_fixture
from tests.exposure_support import payload
from tests.migration_expectations import EXPECTED_MIGRATION_REVISION
from tests.test_experiment_candidates_cli import FeedFixture
from tests.test_experiment_candidates_cli import feed as feed


@pytest.mark.parametrize(
    "stop",
    [
        None,
        "CREATE TABLE body_selections",
        "CREATE TRIGGER body_selections_no_delete",
        "UPDATE alembic_version",
    ],
)
def test_nonempty_previous_head_upgrade_rolls_back_and_preserves_frozen_export(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stop: str | None
) -> None:
    fixture = layout_fixture(feed, tmp_path, monkeypatch)
    root = fixture.extraction.root
    before = BodyService(root.database, root.data_root).extractions(
        fixture.extraction.prepared.paper_id
    )
    receipt, _, exported = payload(root)
    config = Config()
    config.set_main_option(
        "script_location", str(Path(database_module.__file__).parent / "migrations")
    )
    engine = open_database(root.database, mode=DatabaseMode.READ_WRITE)
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            config.attributes["connection"] = connection
            command.downgrade(config, "b007_exposure")
            connection.commit()
    finally:
        engine.dispose()
    if stop:
        with fail_sql(stop), pytest.raises(StorageError) as error:
            upgrade_database(root.database)
        assert error.value.reason == "upgrade_failed"
        with sqlite3.connect(root.database) as connection:
            assert connection.execute(
                "SELECT version_num FROM alembic_version"
            ).fetchone() == ("b007_exposure",)
            assert (
                connection.execute(
                    "SELECT name FROM sqlite_master WHERE name LIKE 'body_selections%'"
                ).fetchall()
                == []
            )
    assert upgrade_database(root.database) == EXPECTED_MIGRATION_REVISION
    assert BodySelections(root.database, root.data_root).history() == ()
    assert (
        BodyService(root.database, root.data_root).extractions(
            fixture.extraction.prepared.paper_id
        )
        == before
    )
    assert (
        Exposures(root.database, root.data_root).payload(receipt["export_id"])
        == exported
    )
    BodyService(root.database, root.data_root).validate_all()
    with sqlite3.connect(root.database) as connection:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
