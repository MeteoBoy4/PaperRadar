"""非空 a701 登记历史升级到尝试事实的原子边界。"""

import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine

from paper_radar.screening_tasks import ScreeningTasks
from paper_radar.storage import database as database_module
from paper_radar.storage.database import upgrade_database
from paper_radar.storage.errors import StorageError
from tests.a7_registration_support import archive, request_for
from tests.artifact_support import fail_sql, paused_operation


def previous_registration_copy(
    source: Path, target: Path
) -> dict[str, list[tuple[object, ...]]]:
    config = Config()
    config.set_main_option(
        "script_location", str(Path(database_module.__file__).parent / "migrations")
    )
    engine = create_engine(f"sqlite:///{target}")
    try:
        with engine.connect() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "a701_screening_registration")
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
        columns = {
            name: ",".join(
                row[1] for row in previous.execute(f"PRAGMA table_info({name})")
            )
            for name in names
        }
        expected = {
            name: original.execute(f"SELECT {columns[name]} FROM {name}").fetchall()
            for name in names
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
    "stop", ["success", "ddl_failure", "stamp_failure", "kill_ddl", "kill_stamp"]
)
def test_nonempty_registration_upgrade_retains_receipts_and_is_atomic(
    tmp_path: Path, stop: str
) -> None:
    root = tmp_path / "source"
    root.mkdir()
    data = archive(root)
    original = ScreeningTasks(data.database)
    receipts = (
        original.register(request_for(data)),
        original.register(request_for(data, stage="value", original_title_is_zh=False)),
    )
    old = tmp_path / "a701.sqlite"
    expected = previous_registration_copy(data.database, old)
    assert len(expected["screening_requests"]) == 2
    with pytest.raises(StorageError) as failure:
        ScreeningTasks(old).get_receipt(receipts[0].receipt_id)
    assert failure.value.reason == "upgrade_required"
    prefix = (
        "\nCREATE TABLE screening_failures"
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
            ).fetchone() == ("a701_screening_registration",)
            assert not connection.execute(
                "SELECT name FROM sqlite_master WHERE name IN "
                "('screening_attempts','screening_leases','screening_failures')"
            ).fetchall()
            assert {
                name: connection.execute(f"SELECT * FROM {name}").fetchall()
                for name in expected
            } == expected
    assert upgrade_database(old) == "a704_screening_retry"
    assert upgrade_database(old) == "a704_screening_retry"
    with closing(sqlite3.connect(old)) as connection:
        assert {
            name: [
                row[: len(expected[name][0])]
                for row in connection.execute(f"SELECT * FROM {name}").fetchall()
            ]
            if expected[name]
            else []
            for name in expected
        } == expected
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()
        assert connection.execute("PRAGMA journal_mode").fetchone() == ("wal",)
    upgraded = ScreeningTasks(old, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC))
    assert (
        tuple(upgraded.get_receipt(receipt.receipt_id) for receipt in receipts)
        == receipts
    )
    assert upgraded.status(receipts[0].receipt_id).used_attempts == 0
    assert upgraded.claim(receipts[0].receipt_id).attempt_no == 1
    upgraded.validate_all()
