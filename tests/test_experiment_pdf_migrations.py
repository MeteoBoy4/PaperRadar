"""B-E10 独立 D1:前一非空 revision 升级及原子 DDL 回滚。"""

import json
import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from paper_radar.body import BodyService
from paper_radar.experiment.root import ExperimentRoot
from paper_radar.storage import database as database_module
from paper_radar.storage.database import DatabaseMode, open_database, upgrade_database
from paper_radar.storage.errors import StorageError
from tests.artifact_support import fail_sql
from tests.experiment_screen_support import screen_fixture
from tests.migration_expectations import EXPECTED_MIGRATION_REVISION
from tests.test_experiment_accept_cli import accept
from tests.test_experiment_candidates_cli import FeedFixture, invoke
from tests.test_experiment_candidates_cli import feed as feed
from tests.test_experiment_pdf_cli import PDF, attach


@pytest.mark.parametrize(
    "stop",
    [
        None,
        "CREATE TABLE experiment_pdf_confirmations",
        "ALTER TABLE body_pdfs ADD COLUMN",
        "CREATE TABLE experiment_frozen_samples",
        "CREATE TRIGGER experiment_frozen_samples_no_delete",
        "UPDATE alembic_version",
    ],
)
def test_nonempty_acceptance_head_upgrade_preserves_facts_and_rolls_back(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stop: str | None
) -> None:
    prepared = screen_fixture(feed, tmp_path, monkeypatch)
    assert prepared.screen().exit_code == 0
    accepted = accept(prepared)
    assert accepted.exit_code == 0, accepted.output
    root = ExperimentRoot(prepared.root)
    body = BodyService(root.database, root.data_root)
    original = body.attach_pdf(prepared.paper_id, PDF, request_id="legacy-pdf")
    before_selection = invoke("selection", "--root", str(root.root)).stdout
    config = Config()
    config.set_main_option(
        "script_location", str(Path(database_module.__file__).parent / "migrations")
    )
    engine = open_database(root.database, mode=DatabaseMode.READ_WRITE)
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            config.attributes["connection"] = connection
            command.downgrade(config, "b002_delegated_acceptances")
            connection.commit()
    finally:
        engine.dispose()
    with sqlite3.connect(root.database) as connection:
        legacy = connection.execute("SELECT * FROM body_pdfs").fetchall()
    if stop:
        with fail_sql(stop), pytest.raises(StorageError) as error:
            upgrade_database(root.database)
        assert error.value.reason == "upgrade_failed"
        with sqlite3.connect(root.database) as connection:
            assert connection.execute(
                "SELECT version_num FROM alembic_version"
            ).fetchone() == ("b002_delegated_acceptances",)
            assert (
                connection.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE name LIKE 'experiment_pdf_confirmations%' "
                    "OR name LIKE 'experiment_frozen_samples%'"
                ).fetchall()
                == []
            )
            assert "confirmation_id" not in {
                row[1] for row in connection.execute("PRAGMA table_info(body_pdfs)")
            }
            assert connection.execute("SELECT * FROM body_pdfs").fetchall() == legacy
    assert upgrade_database(root.database) == EXPECTED_MIGRATION_REVISION
    assert body.pdfs(prepared.paper_id) == (original,)
    assert invoke("selection", "--root", str(root.root)).stdout == before_selection
    assert json.loads(accept(prepared).stdout) == {
        **json.loads(accepted.stdout),
        "replayed": True,
    }
    with sqlite3.connect(root.database) as connection:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    attached = attach(prepared, tmp_path)
    assert attached.exit_code == 0, attached.output
    body.validate_all()
