"""执行历史的当前备份回放、非空迁移和脱离原根恢复。"""

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine

from paper_radar.backup import BackupError, create_backup, restore_backup
from paper_radar.pi_supply import (
    SupplyError,
    create_cleanup_plan,
    execute_cleanup_plan,
    export_supply,
    list_cleanup_executions,
    rebuild_supply,
    show_cleanup_plan,
    show_supply,
)
from paper_radar.storage import database as database_module
from paper_radar.storage.database import upgrade_database
from tests.pi_cleanup_process_support import interrupted_execution
from tests.pi_supply_support import SupplyRoots, inputs, prepare


def test_nonempty_a404_upgrade_preserves_original_plan_bytes(tmp_path: Path) -> None:
    source = inputs(tmp_path / "source")
    first = prepare(tmp_path / "source", source)
    plan = create_cleanup_plan(
        source[0],
        data_root=tmp_path / "source/data",
        config_root=tmp_path / "source/config",
        material_root=tmp_path / "source/materials",
    )
    old = tmp_path / "a404.sqlite3"
    config = Config()
    config.set_main_option(
        "script_location", str(Path(database_module.__file__).parent / "migrations")
    )
    engine = create_engine(f"sqlite:///{old}")
    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "a404_pi_cleanup_plans")
        connection.commit()
    engine.dispose()
    with sqlite3.connect(source[0]) as original, sqlite3.connect(old) as previous:
        tables = [
            r[0]
            for r in previous.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name != 'alembic_version' ORDER BY name"
            )
        ]
        expected = {}
        for table in tables:
            values = original.execute(f"SELECT * FROM {table}").fetchall()
            expected[table] = values
            previous.execute(f"DELETE FROM {table}")
            if values:
                previous.executemany(
                    f"INSERT INTO {table} VALUES ({','.join('?' for _ in values[0])})",
                    values,
                )
    assert upgrade_database(old) == "feed06_language_provenance"
    assert show_cleanup_plan(old, plan.plan_id).canonical_bytes == plan.canonical_bytes
    assert show_supply(old, first.supply_id) == show_supply(source[0], first.supply_id)
    with sqlite3.connect(old) as connection:
        assert {
            table: connection.execute(f"SELECT * FROM {table}").fetchall()
            for table in tables
        } == expected


def test_completed_and_interrupted_execution_histories_survive_backup_restore(
    tmp_path: Path,
) -> None:
    source = inputs(tmp_path)
    first = prepare(tmp_path, source)
    roots: SupplyRoots = dict(
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
    )
    for _ in range(2):
        rebuild_supply(
            source[0],
            first.supply_id,
            tmp_path / "install",
            **roots,
            downloader=source[3],
            runner=source[4],
        )
    plan = create_cleanup_plan(source[0], **roots)
    with interrupted_execution(source[0], plan.plan_id, "renamed") as (process, _):
        process.kill()
        assert process.wait(timeout=10) < 0
    pending = create_cleanup_plan(source[0], **roots)
    assert execute_cleanup_plan(source[0], pending.plan_id).passed
    before = list_cleanup_executions(source[0])
    batch = create_backup(source[0], tmp_path / "data", tmp_path / "backups")
    restore = restore_backup(batch.batch_dir, tmp_path / "restored")
    (tmp_path / "install").rename(tmp_path / "unavailable-root")
    database = restore.target_dir / "database.sqlite3"
    assert list_cleanup_executions(database) == before
    export_supply(database, first.supply_id, tmp_path / "exported")
    assert (
        tmp_path / "exported" / first.supply_id / "package-lock.json"
    ).read_bytes() == show_supply(database, first.supply_id).materials[
        "package-lock.json"
    ]
    assert (
        show_cleanup_plan(database, plan.plan_id).canonical_bytes
        == plan.canonical_bytes
    )
    assert (
        show_supply(database, first.supply_id).manifest
        == show_supply(source[0], first.supply_id).manifest
    )


@pytest.mark.parametrize("mutation", ["phase", "reason", "time", "plan"])
def test_query_and_backup_reject_semantically_broken_execution_history(
    tmp_path: Path, mutation: str
) -> None:
    source = inputs(tmp_path)
    first = prepare(tmp_path, source)
    roots: SupplyRoots = dict(
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
    )
    rebuild_supply(
        source[0],
        first.supply_id,
        tmp_path / "install",
        **roots,
        downloader=source[3],
        runner=source[4],
    )
    plan = create_cleanup_plan(source[0], **roots)
    assert execute_cleanup_plan(source[0], plan.plan_id).passed
    with sqlite3.connect(source[0]) as connection:
        if mutation == "phase":
            connection.execute(
                "UPDATE pi_cleanup_progress SET phase='completed' WHERE phase='not_run'"
            )
        elif mutation == "reason":
            connection.execute(
                "UPDATE pi_cleanup_progress SET reason='cleanup_failed' "
                "WHERE phase='completed'"
            )
        elif mutation == "time":
            connection.execute(
                "UPDATE pi_cleanup_progress SET created_at='1900-01-01T00:00:00+00:00'"
            )
        else:
            empty = create_cleanup_plan(source[0], **roots)
            connection.execute(
                "UPDATE pi_cleanup_executions SET plan_id=?", (empty.plan_id,)
            )
    with pytest.raises(SupplyError, match="cleanup_history_invalid"):
        list_cleanup_executions(source[0])
    with pytest.raises(BackupError) as caught:
        create_backup(source[0], tmp_path / "data", tmp_path / "backup")
    assert caught.value.reason.value == "supply_invalid"
