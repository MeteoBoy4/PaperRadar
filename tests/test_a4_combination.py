"""非空完整生命周期在清理后保留材料与审计,隔离恢复不复活实例。"""

from pathlib import Path

import pytest

from paper_radar.backup import create_backup, restore_backup, verify_backup
from paper_radar.pi_supply import (
    SupplyError,
    acquire_install,
    activate_supply,
    activation_history,
    available_installs,
    create_cleanup_plan,
    doctor_supply,
    execute_cleanup_plan,
    export_supply,
    list_cleanup_executions,
    list_cleanup_plans,
    rebuild_supply,
    show_supply,
    verify_supply,
)
from paper_radar.storage.artifacts import ArtifactStore
from tests.pi_supply_support import SupplyRoots, inputs, prepare
from tests.restore_support import history_view


def test_full_lifecycle_cleanup_export_and_isolated_restore(tmp_path: Path) -> None:
    root = tmp_path / "source"
    source = inputs(root)
    database, snapshot, _, download, runner = source
    roots: SupplyRoots = dict(
        data_root=root / "data",
        config_root=root / "config",
        material_root=root / "materials",
    )
    first = prepare(root, source)
    assert all(
        item.passed for item in verify_supply(database, first.supply_id, runner=runner)
    )
    second = rebuild_supply(
        database,
        first.supply_id,
        root / "install",
        **roots,
        downloader=download,
        runner=runner,
    )
    assert first.install_id != second.install_id
    selected = activate_supply(database, first.supply_id, snapshot)
    assert selected.install_id == second.install_id
    report = doctor_supply(database, snapshot)
    assert report.passed and "rpc_compatibility" in report.not_assessed
    record = show_supply(database, first.supply_id)
    retired_path = next(
        item.path for item in record.installs if item.install_id == first.install_id
    )
    with acquire_install(database, first.supply_id, first.install_id):
        protected = create_cleanup_plan(database, **roots)
        assert protected.candidates == ()
        assert "in_flight" in next(
            item.protection
            for item in protected.items
            if item.install_id == first.install_id
        )
    plan = create_cleanup_plan(database, **roots)
    assert [item.install_id for item in plan.candidates] == [first.install_id]
    execution = execute_cleanup_plan(database, plan.plan_id)
    assert execution.passed and execution.items[0].phase == "completed"
    assert not retired_path.exists()
    assert [
        item.install_id for item in available_installs(database, first.supply_id)
    ] == [second.install_id]
    assert show_supply(database, first.supply_id) == record
    export_supply(database, first.supply_id, root / "materials")
    expected = {
        path.relative_to(root / "materials"): path.read_bytes()
        for path in (root / "materials").rglob("*")
        if path.is_file()
    }
    assert len(expected) == 7
    ArtifactStore(database, root / "data").publish_single(
        "original_pdf", [b"retained source PDF"]
    )
    facts = history_view(database, root / "data")
    plans, executions = list_cleanup_plans(database), list_cleanup_executions(database)
    history = activation_history(database)
    batch = create_backup(database, root / "data", tmp_path / "backups")
    assert verify_backup(batch.batch_dir) == batch
    root.rename(tmp_path / "unavailable-source")
    restored = restore_backup(batch.batch_dir, tmp_path / "restored")
    restored_db = restored.target_dir / "database.sqlite3"
    assert history_view(restored_db, restored.target_dir) == facts
    assert show_supply(restored_db, first.supply_id) == record
    assert list_cleanup_plans(restored_db) == plans
    assert list_cleanup_executions(restored_db) == executions
    assert activation_history(restored_db) == history
    assert not doctor_supply(restored_db, snapshot).passed
    assert available_installs(restored_db, first.supply_id) == ()
    with (
        pytest.raises(SupplyError, match="install_unavailable"),
        acquire_install(restored_db, first.supply_id, first.install_id),
    ):
        pytest.fail("restore must not revive retired installation")
    target = tmp_path / "restored-materials"
    export_supply(restored_db, first.supply_id, target)
    assert {
        path.relative_to(target): path.read_bytes()
        for path in target.rglob("*")
        if path.is_file()
    } == expected
