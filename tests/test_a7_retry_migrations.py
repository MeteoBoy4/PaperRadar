"""非空 FK 环开启外键升级;DDL/插入/版本戳故障全部回滚。"""

import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event

from paper_radar.papers import PaperFacts
from paper_radar.screening_tasks import (
    FailureKind,
    FailureReport,
    ScreeningTasks,
    SuccessCandidate,
    SuccessReceipt,
)
from paper_radar.storage import database as database_module
from paper_radar.storage.database import upgrade_database
from paper_radar.storage.errors import StorageError
from tests.a7_registration_support import archive, request_for
from tests.artifact_support import fail_sql, paused_operation
from tests.test_paper_mapping import screening_fields
from tests.test_paper_service import observation

NOW = datetime(2026, 1, 1, tzinfo=UTC)
RAW = b'{"boundary":"in_scope","reason_zh":"Atmospheric prediction is studied."}'


def previous_success_copy(
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
            command.upgrade(config, "a703_screening_success")
            connection.commit()
    finally:
        engine.dispose()
    with (
        closing(sqlite3.connect(source)) as original,
        closing(sqlite3.connect(target)) as old,
    ):
        names = [
            row[0]
            for row in old.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name!='alembic_version' ORDER BY name"
            )
        ]
        columns = {
            name: [row[1] for row in old.execute(f"PRAGMA table_info({name})")]
            for name in names
        }
        expected = {
            name: original.execute(
                f"SELECT {','.join(columns[name])} FROM {name}"
            ).fetchall()
            for name in names
        }
        for name, rows in expected.items():
            old.execute(f"DELETE FROM {name}")
            if rows:
                old.executemany(
                    f"INSERT INTO {name} VALUES ({','.join('?' for _ in rows[0])})",
                    rows,
                )
        old.commit()
    return columns, expected


@pytest.mark.parametrize("phase", ["success", "cut_cycle", "drop", "restore", "stamp"])
@pytest.mark.parametrize("interrupt", ["error", "kill"])
def test_nonempty_success_cycle_upgrade_is_atomic_with_foreign_keys_enabled(
    tmp_path: Path,
    phase: str,
    interrupt: str,
) -> None:
    root = tmp_path / "source"
    root.mkdir()
    data = archive(root)
    service = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    succeeded = service.register(request_for(data))
    accepted = service.submit(
        service.claim(succeeded.receipt_id), SuccessCandidate(RAW, input_tokens=0)
    )
    assert isinstance(accepted, SuccessReceipt)
    cached = service.register(request_for(data, scheduled_day="2026-01-02"))
    assert cached.cached_success_id == accepted.success_id
    active = service.register(
        request_for(data, stage="value", original_title_is_zh=False)
    )
    service.claim(active.receipt_id)
    second = PaperFacts(data.database, data.data_root).submit(
        observation(doi="10.1234/failure", fields=screening_fields())
    )
    failed = service.register(request_for(data, paper_id=second.paper_id))
    service.submit(service.claim(failed.receipt_id), SuccessCandidate(b"{"))
    service.fail(service.claim(failed.receipt_id), FailureReport(FailureKind.CANCELLED))
    target = tmp_path / "a703.sqlite"
    columns, expected = previous_success_copy(data.database, target)
    assert expected["screening_successes"] and expected["screening_attempts"]
    with closing(sqlite3.connect(target)) as connection:
        before_schema = connection.execute(
            "SELECT type,name,sql FROM sqlite_master ORDER BY type,name"
        ).fetchall()
    prefix = {
        "cut_cycle": "UPDATE screening_requests SET cached_success_id=NULL",
        "drop": "DROP TABLE screening_requests",
        "restore": "INSERT INTO screening_attempts",
        "stamp": "UPDATE alembic_version",
    }.get(phase)
    if prefix is not None:
        if interrupt == "error":
            with fail_sql(prefix), pytest.raises(StorageError) as error:
                upgrade_database(target)
            assert error.value.reason == "upgrade_failed"
        else:
            with paused_operation(
                "from pathlib import Path; import sys; "
                "from paper_radar.storage.database import upgrade_database; "
                "upgrade_database(Path(sys.argv[1]))",
                [str(target)],
                prefix,
            ) as process:
                process.kill()
                process.wait(timeout=15)
        with closing(sqlite3.connect(target)) as connection:
            assert connection.execute(
                "SELECT version_num FROM alembic_version"
            ).fetchone() == ("a703_screening_success",)
            assert (
                connection.execute(
                    "SELECT type,name,sql FROM sqlite_master ORDER BY type,name"
                ).fetchall()
                == before_schema
            )
            assert {
                name: connection.execute(
                    f"SELECT {','.join(columns[name])} FROM {name}"
                ).fetchall()
                for name in expected
            } == expected
    checked = []

    def observe(connection, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
        if statement.startswith(
            (
                "DROP TABLE screening_",
                "INSERT INTO screening_",
                "UPDATE screening_requests",
            )
        ):
            checked.append(
                cursor.connection.execute("PRAGMA foreign_keys").fetchone()[0]
            )

    event.listen(Engine, "before_cursor_execute", observe)
    try:
        assert upgrade_database(target) == "feed06_language_provenance"
        assert upgrade_database(target) == "feed06_language_provenance"
    finally:
        event.remove(Engine, "before_cursor_execute", observe)
    assert checked and set(checked) == {1}
    with closing(sqlite3.connect(target)) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        assert {
            name: connection.execute(
                f"SELECT {','.join(columns[name])} FROM {name}"
            ).fetchall()
            for name in expected
        } == expected
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()
        with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
            connection.execute("UPDATE screening_requests SET source='invalid'")
        connection.rollback()
        with pytest.raises(
            sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"
        ):
            connection.execute(
                "UPDATE screening_tasks SET parent_task_id='missing' WHERE task_id=?",
                (failed.task_id,),
            )
        connection.rollback()
    upgraded = ScreeningTasks(target, data.data_root, clock=lambda: NOW)
    assert upgraded.get_receipt(cached.receipt_id) == cached
    assert upgraded.status(active.receipt_id).state == "running"
    assert upgraded.status(failed.receipt_id).state == "failed"
    upgraded.validate_all()
