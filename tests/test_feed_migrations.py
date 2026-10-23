"""非空 a601 来源约束扩展及失败/强杀的原子升级。"""

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
from tests.test_paper_service import observation


def a601_copy(source: Path, target: Path) -> dict[str, list[tuple[object, ...]]]:
    config = Config()
    config.set_main_option(
        "script_location", str(Path(database_module.__file__).parent / "migrations")
    )
    engine = create_engine(f"sqlite:///{target}")
    try:
        with engine.connect() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "a601_paper_facts")
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
        expected = {}
        for name in names:
            columns = [row[1] for row in previous.execute(f"PRAGMA table_info({name})")]
            values = original.execute(
                f"SELECT {','.join(columns)} FROM {name}"
            ).fetchall()
            expected[name] = values
            previous.execute(f"DELETE FROM {name}")
            if values:
                previous.executemany(
                    f"INSERT INTO {name} VALUES ({','.join('?' for _ in columns)})",
                    values,
                )
        previous.commit()
    return expected


@pytest.mark.parametrize(
    "stop",
    ["success", "rebuild_failure", "stamp_failure", "kill_rebuild", "kill_stamp"],
)
def test_a601_upgrade_preserves_nonempty_history_and_unknown_raw_doi(
    tmp_path: Path, stop: str
) -> None:
    source = inputs(tmp_path / "source")
    prepare(tmp_path / "source", source)
    service = PaperFacts(source[0], tmp_path / "source/data")
    retained = service.submit(
        observation(
            fields={
                "title": {"value": "Publisher", "locator": "title"},
                "authors": {
                    "value": ("Author one", "Author two"),
                    "locator": "authors",
                },
            }
        )
    )
    assert retained.paper_id
    previous = tmp_path / "a601.sqlite"
    expected = a601_copy(source[0], previous)
    prefix = (
        "\nCREATE TABLE paper_observations"
        if "rebuild" in stop
        else "UPDATE alembic_version"
    )
    if "failure" in stop:
        with fail_sql(prefix), pytest.raises(StorageError) as failure:
            upgrade_database(previous)
        assert failure.value.reason == "upgrade_failed"
    elif stop.startswith("kill"):
        with paused_operation(
            "from pathlib import Path; import sys; "
            "from paper_radar.storage.database import upgrade_database; "
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
            ).fetchone() == ("a601_paper_facts",)
            assert (
                connection.execute(
                    "SELECT name FROM sqlite_master WHERE name='feeds'"
                ).fetchall()
                == []
            )
            assert {
                name: connection.execute(f"SELECT * FROM {name}").fetchall()
                for name in expected
            } == expected
    assert upgrade_database(previous) == "a704_screening_retry"
    assert upgrade_database(previous) == "a704_screening_retry"
    with closing(sqlite3.connect(previous)) as connection:
        for name, values in expected.items():
            columns = [
                row[1]
                for row in connection.execute(f"PRAGMA table_info({name})")
                if row[1] not in {"raw_doi", "result_reason"}
                and not (name == "paper_selection_events" and row[1] == "event_no")
            ]
            assert (
                connection.execute(f"SELECT {','.join(columns)} FROM {name}").fetchall()
                == values
            )
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()
    upgraded = PaperFacts(previous, tmp_path / "source/data")
    trace = upgraded.trace(retained.paper_id, verify_source_bytes=True)
    assert trace.current.fields["title"].value == "Publisher"
    assert (
        trace.acquisitions[0].raw_doi is None
    )  # a601 did not record the original spelling.
    assert history_view(previous, tmp_path / "source/data") == history_view(
        source[0], tmp_path / "source/data"
    )
    feed = upgraded.register_feed("https://feeds.example/f?query=kept")
    assert (
        upgraded.submit(item(feed.feed_id, doi="10.1234/abc")).paper_id
        == retained.paper_id
    )
    upgraded.validate_all()
