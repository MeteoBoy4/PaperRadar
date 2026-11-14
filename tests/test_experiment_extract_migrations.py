"""B-E11 独立 D1:上一非空 revision 升级、DDL 故障原子性。"""

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from paper_radar.experiment.pdf import PdfSamples
from paper_radar.storage import database as database_module
from paper_radar.storage.database import DatabaseMode, open_database, upgrade_database
from paper_radar.storage.errors import StorageError
from tests.artifact_support import fail_sql
from tests.experiment_extract_support import extract_fixture
from tests.migration_expectations import EXPECTED_MIGRATION_REVISION
from tests.test_experiment_candidates_cli import FeedFixture
from tests.test_experiment_candidates_cli import feed as feed


@pytest.mark.parametrize(
    "stop",
    [
        None,
        "CREATE TABLE experiment_extractions",
        "CREATE TABLE experiment_extraction_peaks",
        "CREATE TRIGGER experiment_extraction_peaks_no_delete",
        "UPDATE alembic_version",
    ],
)
def test_nonempty_pdf_head_upgrade_is_atomic(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stop: str | None
) -> None:
    prepared = extract_fixture(feed, tmp_path, monkeypatch)
    root = prepared.root
    samples = PdfSamples(root.database, root.data_root).samples()
    assert len(samples) == 1
    config = Config()
    config.set_main_option(
        "script_location", str(Path(database_module.__file__).parent / "migrations")
    )
    engine = open_database(root.database, mode=DatabaseMode.READ_WRITE)
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            config.attributes["connection"] = connection
            command.downgrade(config, "b003_pdf_confirmations")
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
            ).fetchone() == ("b003_pdf_confirmations",)
            assert (
                connection.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE name LIKE 'experiment_extraction%'"
                ).fetchall()
                == []
            )
    assert upgrade_database(root.database) == EXPECTED_MIGRATION_REVISION
    assert PdfSamples(root.database, root.data_root).samples() == samples
    with sqlite3.connect(root.database) as connection:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
