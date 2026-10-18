"""本票非空升级、失败历史和多实例备份闭包。"""

import shutil
import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine

from paper_radar.backup import create_backup, restore_backup, verify_backup
from paper_radar.pi_supply import (
    SupplyError,
    list_supplies,
    rebuild_supply,
    show_supply,
    verify_supply,
)
from paper_radar.storage import database as database_module
from paper_radar.storage.artifacts import ArtifactStore
from paper_radar.storage.database import upgrade_database
from tests.pi_supply_support import Run, inputs, prepare


def test_nonempty_a401_migrates_without_changing_any_previous_fact(
    tmp_path: Path,
) -> None:
    source = inputs(tmp_path / "source")
    prepared = prepare(tmp_path / "source", source)
    old = tmp_path / "a401.sqlite3"
    config = Config()
    config.set_main_option(
        "script_location", str(Path(database_module.__file__).parent / "migrations")
    )
    engine = create_engine(f"sqlite:///{old}")
    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "a401_pi_supply")
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
                placeholders = ",".join("?" for _ in values[0])
                previous.executemany(
                    f"INSERT INTO {table} VALUES ({placeholders})", values
                )
    assert upgrade_database(old) == "a405_pi_cleanup_execution"
    assert show_supply(old, prepared.supply_id) == show_supply(
        source[0], prepared.supply_id
    )
    with sqlite3.connect(old) as connection:
        assert {
            table: connection.execute(f"SELECT * FROM {table}").fetchall()
            for table in tables
        } == expected


def test_nonempty_rebuild_and_check_history_survive_isolated_restore(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    source = inputs(root)
    first = prepare(root, source)
    node = show_supply(source[0], first.supply_id).installs[0].path / "node/bin/node"
    node.chmod(0o755)
    node.write_bytes(b"broken")
    verify_supply(source[0], first.supply_id, runner=Run())
    rebuild_supply(
        source[0],
        first.supply_id,
        root / "install",
        data_root=root / "data",
        config_root=root / "config",
        material_root=root / "materials",
        downloader=source[3],
        runner=Run(),
    )
    source[3].content = {
        url: b"bad archive" for url in source[3].content if url.endswith(".tar.xz")
    }
    with pytest.raises(SupplyError, match="node_checksum_mismatch"):
        rebuild_supply(
            source[0],
            first.supply_id,
            root / "install",
            data_root=root / "data",
            config_root=root / "config",
            material_root=root / "materials",
            downloader=source[3],
            runner=Run(),
        )
    record = show_supply(source[0], first.supply_id)
    ArtifactStore(source[0], root / "data").publish_single(
        "source_snapshot", [b"source"]
    )
    batch = create_backup(source[0], root / "data", tmp_path / "backups")
    assert verify_backup(batch.batch_dir).manifest.format_version == 1
    for directory in (root / "install").rglob("*"):
        if directory.is_dir():
            directory.chmod(0o700)
    shutil.rmtree(root / "install")
    restored = restore_backup(batch.batch_dir, tmp_path / "restored")
    assert (
        show_supply(restored.target_dir / "database.sqlite3", first.supply_id) == record
    )
    assert not (restored.target_dir / ".tools").exists()


@pytest.mark.parametrize(
    "column,value",
    [
        ("reason", "SECRET-uncontrolled"),
        ("created_at", "2026-10-18T00:00:00"),
        ("supply_id", "f" * 64),
    ],
)
def test_rebuild_failure_corruption_is_rejected_by_query_and_backup(
    tmp_path: Path,
    column: str,
    value: str,
) -> None:
    source = inputs(tmp_path)
    first = prepare(tmp_path, source)
    source[3].content = {
        url: b"bad archive" for url in source[3].content if url.endswith(".tar.xz")
    }
    with pytest.raises(SupplyError):
        rebuild_supply(
            source[0],
            first.supply_id,
            tmp_path / "install",
            data_root=tmp_path / "data",
            config_root=tmp_path / "config",
            material_root=tmp_path / "materials",
            downloader=source[3],
            runner=Run(),
        )
    with sqlite3.connect(source[0]) as connection:
        connection.execute(f"UPDATE pi_rebuild_failures SET {column}=?", (value,))
    with pytest.raises(SupplyError, match="supply_corrupt"):
        list_supplies(source[0])
    from paper_radar.backup import BackupError

    with pytest.raises(BackupError):
        create_backup(source[0], tmp_path / "data", tmp_path / "backups")
