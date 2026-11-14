"""B-E12 独立 D1:非空 b004 升级及 DDL 原子性。"""

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from paper_radar.body import BodyService
from paper_radar.body.extraction import LAYOUT_CHECKS
from paper_radar.experiment.layout import LayoutReviews
from paper_radar.storage import database as database_module
from paper_radar.storage.database import DatabaseMode, open_database, upgrade_database
from paper_radar.storage.errors import StorageError
from tests.artifact_support import fail_sql
from tests.experiment_layout_support import layout_fixture
from tests.migration_expectations import EXPECTED_MIGRATION_REVISION
from tests.test_experiment_candidates_cli import FeedFixture
from tests.test_experiment_candidates_cli import feed as feed


@pytest.mark.parametrize(
    "stop",
    [
        None,
        "ALTER TABLE body_layout_reviews ADD COLUMN",
        "CREATE TABLE experiment_layout_recordings",
        "CREATE TRIGGER experiment_layout_recordings_no_delete",
        "UPDATE alembic_version",
    ],
)
def test_nonempty_bounded_head_upgrade_preserves_body_and_is_atomic(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stop: str | None
) -> None:
    prepared = layout_fixture(feed, tmp_path, monkeypatch)
    root = prepared.extraction.root
    body = BodyService(root.database, root.data_root)
    body.review_layout(
        prepared.identity,
        passed=True,
        checks={key: True for key in LAYOUT_CHECKS},
        note="legacy review",
        actor="agent",
        request_id="b-layout-legacy",
    )
    before = body.extractions(prepared.extraction.prepared.paper_id)
    config = Config()
    config.set_main_option(
        "script_location", str(Path(database_module.__file__).parent / "migrations")
    )
    engine = open_database(root.database, mode=DatabaseMode.READ_WRITE)
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            config.attributes["connection"] = connection
            command.downgrade(config, "b004_bounded_extractions")
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
            ).fetchone() == ("b004_bounded_extractions",)
            assert (
                connection.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE name LIKE 'experiment_layout_recordings%'"
                ).fetchall()
                == []
            )
            assert "recording_kind" not in {
                r[1]
                for r in connection.execute("PRAGMA table_info(body_layout_reviews)")
            }
    assert upgrade_database(root.database) == EXPECTED_MIGRATION_REVISION
    assert body.extractions(prepared.extraction.prepared.paper_id) == before
    assert LayoutReviews(root.database, root.data_root).history() == ()
    assert prepared.review()["quality"] == "experiment_document_gate"
    body.validate_all()
    with sqlite3.connect(root.database) as connection:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_old_review_wrapper_rejects_invalid_input_before_database_io(
    tmp_path: Path,
) -> None:
    """缺库故障接缝:既有 wrapper 不因新增同事务入口而改变校验顺序。"""
    from paper_radar.body.models import BodyError
    from paper_radar.reading.context import ExtractionIdentity

    body = BodyService(tmp_path / "absent.sqlite3", tmp_path / "data")
    with pytest.raises(BodyError) as error:
        body.review_layout(
            ExtractionIdentity("a" * 64, "b" * 64, "c" * 64),
            passed=True,
            checks={},
            note="legacy",
            actor="agent",
            request_id="legacy",
        )
    assert error.value.reason == "invalid_request"
    assert list(tmp_path.iterdir()) == []
