"""非空 a603→a604 原子升级及旧事实逐列保留。"""

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
from tests.test_version_relations import relation


def previous_copy(
    source: Path, target: Path
) -> dict[str, tuple[list[str], list[tuple[object, ...]]]]:
    config = Config()
    config.set_main_option(
        "script_location", str(Path(database_module.__file__).parent / "migrations")
    )
    engine = create_engine(f"sqlite:///{target}")
    try:
        with engine.connect() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "a603_source_arbitration")
            connection.commit()
    finally:
        engine.dispose()
    expected = {}
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
        for name in names:
            columns = [row[1] for row in previous.execute(f"PRAGMA table_info({name})")]
            rows = original.execute(
                f"SELECT {','.join(columns)} FROM {name}"
            ).fetchall()
            expected[name] = columns, rows
            previous.execute(f"DELETE FROM {name}")
            if rows:
                previous.executemany(
                    f"INSERT INTO {name} VALUES ({','.join('?' for _ in columns)})",
                    rows,
                )
        previous.commit()
    return expected


@pytest.mark.parametrize(
    "stop", ["success", "ddl_failure", "stamp_failure", "kill_ddl", "kill_stamp"]
)
def test_nonempty_a603_upgrade_is_atomic_and_preserves_all_history(
    tmp_path: Path, stop: str
) -> None:
    root = tmp_path / "source"
    source = inputs(root)
    prepare(root, source)
    service = PaperFacts(source[0], root / "data")
    original = service.submit(observation(doi="10.1/pre", version_kind="preprint"))
    assert original.paper_id and original.version_id
    feed = service.register_feed("https://example.org/feed")
    service.submit(item(feed.feed_id, doi="10.1/pre", version_kind="preprint"))
    service.correct(correction(original.version_id))
    before = service.trace(original.paper_id).model_dump(mode="json")
    old = tmp_path / "a603.sqlite"
    expected = previous_copy(source[0], old)
    prefix = (
        "\nCREATE TABLE paper_version_relations"
        if "ddl" in stop
        else "UPDATE alembic_version"
    )
    if "failure" in stop:
        with fail_sql(prefix), pytest.raises(StorageError) as failure:
            upgrade_database(old)
        assert failure.value.reason == "upgrade_failed"
    elif stop.startswith("kill"):
        with paused_operation(
            "from pathlib import Path; import sys; from paper_radar.storage.database "
            "import upgrade_database; upgrade_database(Path(sys.argv[1]))",
            [str(old)],
            prefix,
        ) as process:
            process.kill()
            process.wait(timeout=15)
    if stop != "success":
        with closing(sqlite3.connect(old)) as connection:
            assert connection.execute(
                "SELECT version_num FROM alembic_version"
            ).fetchone() == ("a603_source_arbitration",)
            assert not connection.execute(
                "SELECT name FROM sqlite_master WHERE name='paper_version_relations'"
            ).fetchall()
            assert {
                name: connection.execute(
                    f"SELECT {','.join(columns)} FROM {name}"
                ).fetchall()
                for name, (columns, _) in expected.items()
            } == {name: rows for name, (_, rows) in expected.items()}
            assert not connection.execute("PRAGMA foreign_key_check").fetchall()
    assert upgrade_database(old) == "a704_screening_retry"
    with closing(sqlite3.connect(old)) as connection:
        assert {
            name: connection.execute(
                f"SELECT {','.join(columns)} FROM {name}"
            ).fetchall()
            for name, (columns, _) in expected.items()
        } == {name: rows for name, (_, rows) in expected.items()}
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()
    upgraded = PaperFacts(old, root / "data")
    assert (
        upgraded.trace(original.paper_id, verify_source_bytes=True).model_dump(
            mode="json"
        )
        == before
    )
    assert history_view(old, root / "data") == history_view(source[0], root / "data")
    assert (
        upgraded.submit(
            observation(
                doi="10.1/pre",
                version_kind="preprint",
                payload=b"relation",
                relations=relation(),
            )
        ).status
        == "retained"
    )
    assert (
        upgraded.submit(observation(doi="10.1/journal")).paper_id == original.paper_id
    )
    upgraded.validate_all()
