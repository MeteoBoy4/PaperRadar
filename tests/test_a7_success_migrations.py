"""非空 a702 尝试历史增量升级并保留原约束及预算。"""

import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine

from paper_radar.screening_tasks import FailureKind, FailureReport, ScreeningTasks
from paper_radar.storage import database as database_module
from paper_radar.storage.database import upgrade_database
from paper_radar.storage.errors import StorageError
from tests.a7_registration_support import archive, request_for
from tests.artifact_support import fail_sql, paused_operation

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def previous_attempt_copy(
    source: Path, target: Path
) -> tuple[dict[str, list[str]], dict[str, list[tuple[object, ...]]]]:
    config = Config()
    config.set_main_option(
        "script_location", str(Path(database_module.__file__).parent / "migrations")
    )
    engine = create_engine(f"sqlite:///{target}")
    try:
        with engine.connect() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "a702_screening_attempts")
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
            name: [row[1] for row in previous.execute(f"PRAGMA table_info({name})")]
            for name in names
        }
        expected = {
            name: original.execute(
                f"SELECT {','.join(columns[name])} FROM {name}"
            ).fetchall()
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
    return columns, expected


@pytest.mark.parametrize(
    "stop", ["success", "ddl_failure", "stamp_failure", "kill_ddl", "kill_stamp"]
)
def test_nonempty_attempt_upgrade_retains_old_attempts_and_is_atomic(
    tmp_path: Path, stop: str
) -> None:
    root = tmp_path / "source"
    root.mkdir()
    data = archive(root)
    service = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    boundary = service.register(request_for(data))
    value = service.register(
        request_for(data, stage="value", original_title_is_zh=False)
    )
    service.fail(service.claim(boundary.receipt_id), FailureReport(FailureKind.TIMEOUT))
    active = service.claim(value.receipt_id)
    target = tmp_path / "a702.sqlite"
    columns, expected = previous_attempt_copy(data.database, target)
    with pytest.raises(StorageError) as old:
        ScreeningTasks(target).get_receipt(boundary.receipt_id)
    assert old.value.reason == "upgrade_required"
    prefix = (
        "ALTER TABLE screening_requests ADD COLUMN"
        if "ddl" in stop
        else "UPDATE alembic_version"
    )
    if "failure" in stop:
        with fail_sql(prefix), pytest.raises(StorageError) as interrupted:
            upgrade_database(target)
        assert interrupted.value.reason == "upgrade_failed"
    elif stop.startswith("kill"):
        with paused_operation(
            "from pathlib import Path; import sys; "
            "from paper_radar.storage.database import upgrade_database; "
            "upgrade_database(Path(sys.argv[1]))",
            [str(target)],
            prefix,
        ) as process:
            process.kill()
            process.wait(timeout=15)
    if stop != "success":
        with closing(sqlite3.connect(target)) as connection:
            assert connection.execute(
                "SELECT version_num FROM alembic_version"
            ).fetchone() == ("a702_screening_attempts",)
            assert not connection.execute(
                "SELECT name FROM sqlite_master WHERE name='screening_successes'"
            ).fetchall()
            assert {
                name: connection.execute(
                    f"SELECT {','.join(columns[name])} FROM {name}"
                ).fetchall()
                for name in expected
            } == expected
    assert upgrade_database(target) == "feed05_composition"
    assert upgrade_database(target) == "feed05_composition"
    with closing(sqlite3.connect(target)) as connection:
        assert {
            name: connection.execute(
                f"SELECT {','.join(columns[name])} FROM {name}"
            ).fetchall()
            for name in expected
        } == expected
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()
        assert connection.execute("PRAGMA journal_mode").fetchone() == ("wal",)
        with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
            connection.execute("UPDATE screening_requests SET source='private_invalid'")
        connection.rollback()
    upgraded = ScreeningTasks(target, data.data_root, clock=lambda: NOW)
    assert upgraded.get_receipt(boundary.receipt_id) == boundary
    assert upgraded.get_receipt(value.receipt_id) == value
    assert upgraded.status(boundary.receipt_id).state == "retryable"
    assert upgraded.status(value.receipt_id).state == "running"
    assert upgraded.renew(active.renewal_handle) == active.expires_at
    assert upgraded.claim(boundary.receipt_id).attempt_no == 2
    upgraded.validate_all()
