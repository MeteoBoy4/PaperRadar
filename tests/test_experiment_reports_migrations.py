"""B-E14 独立 D1:非空 b005 升级、事务故障与标准恢复。"""

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from typer.testing import CliRunner

from paper_radar.body import BodyService
from paper_radar.cli import app
from paper_radar.experiment.root import ExperimentRoot
from paper_radar.storage import database as database_module
from paper_radar.storage.database import DatabaseMode, open_database, upgrade_database
from paper_radar.storage.errors import StorageError
from tests.artifact_support import fail_sql
from tests.migration_expectations import EXPECTED_MIGRATION_REVISION


@pytest.mark.parametrize(
    "stop",
    [
        None,
        "CREATE TABLE report_runs",
        "CREATE TABLE report_entries",
        "CREATE TRIGGER report_entries_no_update",
        "UPDATE alembic_version",
    ],
)
def test_nonempty_previous_revision_upgrade_is_atomic_and_restorable(
    tmp_path: Path, stop: str | None
) -> None:
    root = ExperimentRoot(tmp_path / "experiment")
    original = root.initialize()
    config = Config()
    config.set_main_option(
        "script_location", str(Path(database_module.__file__).parent / "migrations")
    )
    engine = open_database(root.database, mode=DatabaseMode.READ_WRITE)
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            config.attributes["connection"] = connection
            command.downgrade(config, "b005_layout_recordings")
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
            ).fetchone() == ("b005_layout_recordings",)
            assert (
                connection.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE name IN ('report_runs','report_entries')"
                ).fetchall()
                == []
            )
    assert upgrade_database(root.database) == EXPECTED_MIGRATION_REVISION
    assert BodyService(root.database, root.data_root).root() == original
    backup = CliRunner().invoke(
        app,
        [
            "backup",
            "create",
            "--database",
            str(root.database),
            "--data-root",
            str(root.data_root),
            "--output",
            str(tmp_path / "backups"),
        ],
    )
    assert backup.exit_code == 0, backup.output
    (batch,) = (tmp_path / "backups").iterdir()
    target = tmp_path / "restored"
    restored = subprocess.run(
        [
            str(Path(sys.executable).with_name("paper-radar")),
            "restore",
            "verify",
            str(batch),
            "--target",
            str(target),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert restored.returncode == 0, restored.stdout + restored.stderr
    assert BodyService(target / "database.sqlite3", target).root() == original
    assert "token" not in restored.stdout
