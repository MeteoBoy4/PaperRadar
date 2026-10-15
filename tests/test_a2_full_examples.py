"""固定合成示例通过公共服务与真实 CLI 验证。"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from paper_radar.config import (
    StageName,
    check_config,
    compile_config,
    diff_config_snapshots,
    load_config_snapshot,
    project_config,
    upgrade_database,
)
from tests.a2_full_support import ROOT
from tests.config_test_support import run_cli


@pytest.mark.parametrize(
    "name",
    [
        "settings",
        "settings-boundary",
        "settings-value",
        "settings-reuse",
        "settings-extraction",
        "settings-read",
        "settings-pi",
        "settings-journals",
    ],
)
def test_fixed_examples_check_compile_replay_and_diff_without_changing_materials(
    tmp_path: Path,
    name: str,
) -> None:
    materials = tmp_path / "materials"
    shutil.copytree(ROOT / "examples", materials)
    original = {p: p.read_bytes() for p in materials.rglob("*") if p.is_file()}
    database = tmp_path / "acceptance.sqlite3"
    upgrade_database(database)
    settings = materials / "config" / f"{name}.yaml"
    checked = check_config(settings, database)
    saved = compile_config(settings, database)
    assert saved == checked
    assert load_config_snapshot(database, saved.snapshot_id) == saved
    semantics = project_config(saved)
    assert len(semantics.projections) == 6
    assert saved.stages[StageName.READ].status == "not_ready"
    assert not diff_config_snapshots(
        database, saved.snapshot_id, saved.snapshot_id
    ).snapshot_changed
    assert {p: p.read_bytes() for p in original} == original
    shutil.rmtree(materials)
    assert load_config_snapshot(database, saved.snapshot_id) == saved


def test_real_config_cli_uses_the_independent_network_sentinel_and_temp_database(
    tmp_path: Path,
) -> None:
    shutil.copytree(ROOT / "examples", tmp_path / "materials")
    settings = tmp_path / "materials/config/settings-pi.yaml"
    database = tmp_path / "acceptance.sqlite3"
    assert (
        run_cli(tmp_path, "db", "upgrade", "--database", str(database)).returncode == 0
    )
    args = ("--settings", str(settings), "--database", str(database))
    check = run_cli(tmp_path, "config", "check", *args)
    compile = run_cli(tmp_path, "config", "compile", *args)
    assert check.returncode == compile.returncode == 0
    snapshot = check_config(settings, database)
    diff = run_cli(
        tmp_path,
        "config",
        "diff",
        snapshot.snapshot_id,
        snapshot.snapshot_id,
        "--database",
        str(database),
    )
    assert diff.returncode == 0
    assert "无差异" in diff.stdout
    for prompt in (tmp_path / "materials/prompts").rglob("*.md"):
        assert (
            prompt.read_text(encoding="utf-8").strip()
            not in check.stdout + compile.stdout + diff.stdout
        )
