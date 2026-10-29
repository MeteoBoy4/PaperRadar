"""激活事实随备份完整恢复;缺根后的修复须显式重建和激活。"""

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine

from paper_radar.backup import BackupError, create_backup, restore_backup
from paper_radar.pi_supply import (
    activate_supply,
    activation_history,
    doctor_supply,
    rebuild_supply,
    show_supply,
)
from paper_radar.storage import database as database_module
from paper_radar.storage.database import upgrade_database
from tests.pi_supply_support import Run, inputs, prepare


def test_nonempty_previous_revision_upgrade_preserves_previous_facts(
    tmp_path: Path,
) -> None:
    source = inputs(tmp_path / "source")
    prepared = prepare(tmp_path / "source", source)
    old = tmp_path / "a402.sqlite3"
    config = Config()
    config.set_main_option(
        "script_location", str(Path(database_module.__file__).parent / "migrations")
    )
    engine = create_engine(f"sqlite:///{old}")
    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "a402_pi_rebuild_failures")
        connection.commit()
    engine.dispose()
    with sqlite3.connect(source[0]) as original, sqlite3.connect(old) as previous:
        tables = [
            row[0]
            for row in previous.execute(
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
    assert upgrade_database(old) == "feed05_composition"
    assert show_supply(old, prepared.supply_id) == show_supply(
        source[0], prepared.supply_id
    )
    assert activation_history(old) == ()
    with sqlite3.connect(old) as connection:
        assert {
            table: connection.execute(f"SELECT * FROM {table}").fetchall()
            for table in tables
        } == expected


def test_restore_keeps_current_when_original_root_healthy_then_rebuilds_in_new_root(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    source = inputs(root)
    first = prepare(root, source)
    activate_supply(source[0], first.supply_id, source[1])
    activate_supply(source[0], first.supply_id, source[1])
    history = activation_history(source[0])
    batch = create_backup(source[0], root / "data", tmp_path / "backups")
    restored = restore_backup(batch.batch_dir, tmp_path / "restored")
    database = restored.target_dir / "database.sqlite3"
    assert activation_history(database) == history
    assert doctor_supply(
        database, source[1]
    ).passed  # 不加恢复标记,不强制重建完好实例。
    (root / "install").rename(root / "unavailable-original-root")
    report = doctor_supply(database, source[1])
    assert not report.passed and "install_unavailable" in report.blockers
    second = rebuild_supply(
        database,
        first.supply_id,
        tmp_path / "new-root",
        data_root=restored.target_dir / "data",
        config_root=tmp_path / "new-config",
        material_root=tmp_path / "new-materials",
        downloader=source[3],
        runner=Run(),
    )
    assert not doctor_supply(database, source[1]).passed
    selected = activate_supply(database, first.supply_id, source[1])
    report = doctor_supply(database, source[1])
    assert selected.install_id == second.install_id and report.passed
    assert report.present_count == 1
    assert any(item.present is False for item in report.instances)
    assert activation_history(database)[:2] == history


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE pi_activation_events SET root_path='/SECRET-invalid-root'",
        "UPDATE pi_activation_events SET snapshot_id=substr(snapshot_id,1,8)",
        "UPDATE pi_activation_events SET install_id='00000000000000000000000000000000'",
        "DELETE FROM pi_current_selection",
        "UPDATE pi_current_selection SET activation_id=1",
    ],
)
def test_backup_and_doctor_reject_corrupt_activation_closure(
    tmp_path: Path, statement: str
) -> None:
    from paper_radar.pi_supply import SupplyError

    source = inputs(tmp_path)
    prepared = prepare(tmp_path, source)
    activate_supply(source[0], prepared.supply_id, source[1])
    activate_supply(source[0], prepared.supply_id, source[1])
    with sqlite3.connect(source[0]) as connection:
        connection.execute(statement)
    with pytest.raises(SupplyError, match="supply_corrupt") as caught:
        doctor_supply(source[0], source[1])
    assert "SECRET" not in str(caught.value)
    with pytest.raises(BackupError) as backup:
        create_backup(source[0], tmp_path / "data", tmp_path / "backups")
    expected = (
        "database_invalid"
        if ("substr" in statement or "00000000" in statement)
        else "supply_invalid"
    )
    assert backup.value.reason.value == expected
