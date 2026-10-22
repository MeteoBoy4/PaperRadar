"""非空 a602→a603 原子迁移与原历史保留。"""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine

from paper_radar.papers import PaperFacts
from paper_radar.storage import database as database_module
from paper_radar.storage.database import upgrade_database
from paper_radar.storage.errors import StorageError
from tests.artifact_support import fail_sql, paused_operation
from tests.feed_support import item
from tests.pi_supply_support import inputs, prepare
from tests.restore_support import history_view
from tests.test_manual_corrections import correction
from tests.test_paper_service import observation


def previous_copy(source: Path, target: Path) -> dict[str, list[tuple[object, ...]]]:
    config = Config()
    config.set_main_option(
        "script_location", str(Path(database_module.__file__).parent / "migrations")
    )
    engine = create_engine(f"sqlite:///{target}")
    try:
        with engine.connect() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "a602_feed_discovery")
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
                "SELECT name FROM sqlite_master WHERE type='table' AND "
                "name!='alembic_version' ORDER BY name"
            )
        ]
        expected = {}
        for name in names:
            values = original.execute(f"SELECT * FROM {name}").fetchall()
            expected[name] = values
            previous.execute(f"DELETE FROM {name}")
            if values:
                previous.executemany(
                    f"INSERT INTO {name} VALUES ({','.join('?' for _ in values[0])})",
                    values,
                )
        previous.commit()
    return expected


@pytest.mark.parametrize(
    "stop", ["success", "ddl_failure", "stamp_failure", "kill_ddl", "kill_stamp"]
)
def test_nonempty_previous_revision_upgrades_atomically_preserving_history(
    tmp_path: Path, stop: str
) -> None:
    root = tmp_path / "source"
    source = inputs(root)
    prepare(root, source)
    service = PaperFacts(source[0], root / "data")
    original = service.submit(observation())
    feed = service.register_feed("https://example.org/feed")
    assert service.submit(item(feed.feed_id, doi="10.1234/abc")).status == "retained"
    assert original.paper_id and original.version_id
    before = service.trace(original.paper_id).model_dump(mode="json")
    previous = tmp_path / "previous.sqlite"
    expected = previous_copy(source[0], previous)
    prefix = (
        "\nCREATE TABLE paper_manual_corrections"
        if "ddl" in stop
        else "UPDATE alembic_version"
    )
    if "failure" in stop:
        with fail_sql(prefix), pytest.raises(StorageError) as failure:
            upgrade_database(previous)
        assert failure.value.reason == "upgrade_failed"
    elif stop.startswith("kill"):
        with paused_operation(
            "from pathlib import Path; import sys; from "
            "paper_radar.storage.database import upgrade_database; "
            "upgrade_database(Path(sys.argv[1]))",
            [str(previous)],
            prefix,
        ) as process:
            process.kill()
            process.wait(timeout=15)
    if stop != "success":
        with closing(sqlite3.connect(previous)) as connection:
            assert connection.execute(
                "SELECT version_num FROM alembic_version"
            ).fetchone() == ("a602_feed_discovery",)
            assert not connection.execute(
                "SELECT name FROM sqlite_master WHERE name='paper_manual_corrections'"
            ).fetchall()
            assert {
                name: connection.execute(f"SELECT * FROM {name}").fetchall()
                for name in expected
            } == expected
            assert not connection.execute("PRAGMA foreign_key_check").fetchall()
    assert upgrade_database(previous) == "a603_source_arbitration"
    with closing(sqlite3.connect(previous)) as connection:
        assert {
            name: connection.execute(f"SELECT * FROM {name}").fetchall()
            for name in expected
        } == expected
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()
    upgraded = PaperFacts(previous, root / "data")
    assert (
        upgraded.trace(original.paper_id, verify_source_bytes=True).model_dump(
            mode="json"
        )
        == before
    )
    assert history_view(previous, root / "data") == history_view(
        source[0], root / "data"
    )
    assert upgraded.correct(correction(original.version_id)).status == "retained"
    upgraded.validate_all()
