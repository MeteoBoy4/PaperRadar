"""计划历史完整回放、上一版本迁移和备份恢复。"""

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine

from paper_radar.backup import BackupError, create_backup, restore_backup
from paper_radar.pi_supply import (
    SupplyError,
    activate_supply,
    create_cleanup_plan,
    show_cleanup_plan,
    show_supply,
)
from paper_radar.storage import database as database_module
from paper_radar.storage.database import upgrade_database
from tests.pi_supply_support import inputs, prepare


def test_plan_remains_original_history_after_new_activation_and_restore(
    tmp_path: Path,
) -> None:
    source = inputs(tmp_path)
    installed = prepare(tmp_path, source)
    plan = create_cleanup_plan(
        source[0],
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
    )
    activate_supply(source[0], installed.supply_id, source[1])
    assert (
        show_cleanup_plan(source[0], plan.plan_id).canonical_bytes
        == plan.canonical_bytes
    )
    backup = create_backup(source[0], tmp_path / "data", tmp_path / "backups")
    restored = restore_backup(backup.batch_dir, tmp_path / "restore")
    (tmp_path / "install").rename(tmp_path / "moved-root")
    recovered = show_cleanup_plan(
        restored.target_dir / "database.sqlite3", plan.plan_id
    )
    assert recovered.canonical_bytes == plan.canonical_bytes
    assert recovered.facts_version == plan.facts_version


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE pi_cleanup_plans SET payload=CAST(payload || ' ' AS BLOB)",
        "UPDATE pi_cleanup_plans SET plan_id="
        "'0000000000000000000000000000000000000000000000000000000000000000'",
        "UPDATE pi_cleanup_plans SET created_at='2026-01-01T00:00:00+00:00'",
    ],
)
def test_query_and_backup_reject_plan_byte_identity_tampering(
    tmp_path: Path, statement: str
) -> None:
    source = inputs(tmp_path)
    prepare(tmp_path, source)
    plan = create_cleanup_plan(
        source[0],
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
    )
    with sqlite3.connect(source[0]) as connection:
        connection.execute(statement)
    with pytest.raises(SupplyError, match="cleanup_plan_invalid"):
        show_cleanup_plan(source[0], plan.plan_id)
    with pytest.raises(BackupError) as caught:
        create_backup(source[0], tmp_path / "data", tmp_path / "backups")
    assert caught.value.reason.value == "supply_invalid"


def test_upgrade_nonempty_a403_preserves_selection_and_all_previous_rows(
    tmp_path: Path,
) -> None:
    source = inputs(tmp_path / "source")
    installed = prepare(tmp_path / "source", source)
    activate_supply(source[0], installed.supply_id, source[1])
    old = tmp_path / "a403.sqlite3"
    config = Config()
    config.set_main_option(
        "script_location", str(Path(database_module.__file__).parent / "migrations")
    )
    engine = create_engine(f"sqlite:///{old}")
    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "a403_pi_activation")
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
    assert upgrade_database(old) == "a602_feed_discovery"
    assert show_supply(old, installed.supply_id) == show_supply(
        source[0], installed.supply_id
    )
    with sqlite3.connect(old) as connection:
        assert {
            table: connection.execute(f"SELECT * FROM {table}").fetchall()
            for table in tables
        } == expected


@pytest.mark.parametrize(
    "mutation", ["protection", "current_reference", "format", "path"]
)
def test_self_consistent_plan_still_requires_semantic_closure(
    tmp_path: Path, mutation: str
) -> None:
    import json

    from paper_radar.config.identity import canonical_json, sha256

    source = inputs(tmp_path)
    installed = prepare(tmp_path, source)
    activate_supply(source[0], installed.supply_id, source[1])
    plan = create_cleanup_plan(
        source[0],
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
    )
    payload = json.loads(plan.canonical_bytes)
    if mutation == "protection":
        payload["items"][0]["protection"] = []
        payload["items"][0]["disposition"] = "candidate"
    elif mutation == "current_reference":
        payload["facts"]["pi_current_selection"][0]["activation_id"] = 9999
        payload["facts_version"] = sha256(canonical_json(payload["facts"]))
    elif mutation == "format":
        payload["format_version"] = True
    else:
        payload["items"][0]["relative_path"] = "../outside"
    raw = canonical_json(payload)
    identity = sha256(raw)
    with sqlite3.connect(source[0]) as connection:
        connection.execute(
            "UPDATE pi_cleanup_plans SET payload=?, plan_id=?", (raw, identity)
        )
    with pytest.raises(SupplyError, match="cleanup_plan_invalid"):
        show_cleanup_plan(source[0], identity)
    with pytest.raises(BackupError) as caught:
        create_backup(source[0], tmp_path / "data", tmp_path / "backups")
    assert caught.value.reason.value == "supply_invalid"


def test_registered_retired_trash_is_separate_from_unknown_trash(
    tmp_path: Path,
) -> None:
    from paper_radar.pi_supply import rebuild_supply
    from tests.pi_supply_support import Run

    source = inputs(tmp_path)
    first = prepare(tmp_path, source)
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
    args = dict(
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
    )
    plan = create_cleanup_plan(source[0], **args)
    assert plan.candidates[0].install_id == first.install_id
    # 模拟执行票在退役commit后移动成功、尚未删除的真实持久化历史。
    with sqlite3.connect(source[0]) as connection:
        connection.execute(
            "INSERT INTO pi_install_retirements VALUES (?, ?, ?)",
            (first.install_id, plan.plan_id, "2099-01-01T00:00:00+00:00"),
        )
    original = next(
        i
        for i in show_supply(source[0], first.supply_id).installs
        if i.install_id == first.install_id
    ).path
    trash = tmp_path / "install/.trash"
    trash.mkdir()
    original.chmod(0o755)
    original.parent.chmod(0o755)
    original.rename(trash / first.install_id)
    (trash / ("0" * 32)).mkdir()
    pending = create_cleanup_plan(source[0], **args)
    assert [i.install_id for i in pending.retired_pending] == [first.install_id]
    assert pending.retired_pending[0].relative_path == f".trash/{first.install_id}"
    assert pending.retired_pending[0].disposition == "candidate"
    assert [i.relative_path for i in pending.manual] == [".trash/" + "0" * 32]
    assert (
        show_cleanup_plan(source[0], plan.plan_id).canonical_bytes
        == plan.canonical_bytes
    )
    batch = create_backup(source[0], tmp_path / "data", tmp_path / "backups")
    restored = restore_backup(batch.batch_dir, tmp_path / "restored")
    assert (
        show_cleanup_plan(
            restored.target_dir / "database.sqlite3", pending.plan_id
        ).canonical_bytes
        == pending.canonical_bytes
    )


def test_retired_original_and_trash_collision_is_not_a_cleanup_candidate(
    tmp_path: Path,
) -> None:
    import shutil

    from paper_radar.pi_supply import rebuild_supply
    from tests.pi_supply_support import Run

    source = inputs(tmp_path)
    first = prepare(tmp_path, source)
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
    args = dict(
        data_root=tmp_path / "data",
        config_root=tmp_path / "config",
        material_root=tmp_path / "materials",
    )
    original_plan = create_cleanup_plan(source[0], **args)
    original = next(
        i
        for i in show_supply(source[0], first.supply_id).installs
        if i.install_id == first.install_id
    ).path
    with sqlite3.connect(source[0]) as connection:
        connection.execute(
            "INSERT INTO pi_install_retirements VALUES (?, ?, ?)",
            (first.install_id, original_plan.plan_id, "2099-01-01T00:00:00+00:00"),
        )
    trash = tmp_path / "install/.trash"
    trash.mkdir()
    shutil.copytree(original, trash / first.install_id, symlinks=True)
    plan = create_cleanup_plan(source[0], **args)
    assert plan.candidates == ()
    pending = plan.retired_pending[0]
    assert pending.reason == "publication_conflict"
    assert pending.disposition == "unverifiable"
    assert plan.manual[0].relative_path == f".trash/{first.install_id}"
    assert original.exists() and (trash / first.install_id).exists()
