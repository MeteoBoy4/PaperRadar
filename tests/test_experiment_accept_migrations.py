"""B-E9 独立 D1:从非空前一 revision 升级及故障回滚。"""

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
from tests.test_experiment_candidates_cli import FeedFixture, invoke
from tests.test_experiment_candidates_cli import feed as feed
from tests.test_experiment_selection_cli import select


@pytest.mark.parametrize(
    "stop",
    [
        None,
        "ALTER TABLE body_decisions ADD COLUMN",
        "CREATE TABLE experiment_acceptances",
        "CREATE TRIGGER experiment_acceptances_no_delete",
        "UPDATE alembic_version",
    ],
)
def test_upgrade_from_selection_head_keeps_authorization_and_is_atomic(
    feed: FeedFixture,
    stop: str | None,
) -> None:
    root, _, fetch = feed
    check = fetch("before-acceptance-migration")
    import json

    view = json.loads(
        invoke(
            "candidates", "--root", str(root), "--check-id", check["check_id"]
        ).stdout
    )
    selected = select(root, view["view_id"], "original-selection", "--position", "1")
    assert selected.exit_code == 0, selected.output
    before = invoke("selection", "--root", str(root)).stdout
    database = root / "paper-radar.sqlite3"
    registered = BodyService(database, root).root()
    config = Config()
    config.set_main_option(
        "script_location", str(Path(database_module.__file__).parent / "migrations")
    )
    engine = open_database(database, mode=DatabaseMode.READ_WRITE)
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            config.attributes["connection"] = connection
            command.downgrade(config, "b001_selection_authorizations")
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
            ).fetchone() == ("b001_selection_authorizations",)
            assert (
                connection.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE name LIKE 'experiment_acceptances%'"
                ).fetchall()
                == []
            )
            assert "delegation_kind" not in {
                row[1]
                for row in connection.execute("PRAGMA table_info(body_decisions)")
            }
    assert upgrade_database(database) == EXPECTED_MIGRATION_REVISION
    assert BodyService(database, root).root() == registered
    assert invoke("selection", "--root", str(root)).stdout == before
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_ordinary_body_request_resembling_delegation_survives_upgrade(
    feed: FeedFixture,
) -> None:
    from paper_radar.experiment.acceptance import Acceptances
    from paper_radar.screening.reasons import ScreeningReasonInput

    root, _, fetch = feed
    check = fetch("ordinary-decisions")
    paper_id = check["items"][0]["paper_id"]
    assert paper_id is not None
    database = root / "paper-radar.sqlite3"
    body = BodyService(database, root)
    reason = ScreeningReasonInput.model_validate(
        dict(result="accepted", source="direct_manual_decision", reason="user_judgment")
    )
    request = "b-accept-" + "a" * 64
    original = body.decide(paper_id, reason, request_id=request, actor="agent")
    config = Config()
    config.set_main_option(
        "script_location", str(Path(database_module.__file__).parent / "migrations")
    )
    engine = open_database(database, mode=DatabaseMode.READ_WRITE)
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            config.attributes["connection"] = connection
            command.downgrade(config, "b001_selection_authorizations")
            connection.commit()
    finally:
        engine.dispose()
    with sqlite3.connect(database) as connection:
        legacy = connection.execute("SELECT * FROM body_decisions").fetchone()
        assert legacy is not None
    upgrade_database(database)
    assert body.decide(paper_id, reason, request_id=request, actor="agent") == original
    with sqlite3.connect(database) as connection:
        after = connection.execute("SELECT * FROM body_decisions").fetchone()
        assert after is not None and after[: len(legacy)] == legacy
    body.decide(paper_id, reason, request_id="b-accept-" + "b" * 64, actor="agent")
    body.validate_all()
    assert Acceptances(database, root).history() == ()
