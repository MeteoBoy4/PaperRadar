"""清理计划 CLI 的副作用、原字节查询和参数边界。"""

from pathlib import Path

from tests.config_test_support import run_cli
from tests.pi_supply_support import SupplyRoots, inputs, prepare


def test_gc_dry_run_explains_plan_write_and_show_cross_process(tmp_path: Path) -> None:
    from paper_radar.pi_supply import list_cleanup_plans

    source = inputs(tmp_path)
    prepare(tmp_path, source)
    result = run_cli(
        tmp_path,
        "pi",
        "supply",
        "gc",
        "--dry-run",
        "--database",
        str(source[0]),
        "--data-root",
        str(tmp_path / "data"),
        "--config-root",
        str(tmp_path / "config"),
        "--material-root",
        str(tmp_path / "materials"),
    )
    assert result.returncode == 0, result.stderr
    assert "保存计划但不删除" in result.stdout
    plan = list_cleanup_plans(source[0])[0]
    assert f"plan_id={plan.plan_id}" in result.stdout
    result = run_cli(
        tmp_path,
        "pi",
        "supply",
        "show-plan",
        plan.plan_id,
        "--database",
        str(source[0]),
    )
    assert result.returncode == 0, result.stderr
    assert f"facts_version={plan.facts_version}" in result.stdout
    raw = run_cli(
        tmp_path,
        "pi",
        "supply",
        "show-plan",
        plan.plan_id,
        "--database",
        str(source[0]),
        "--canonical",
    )
    assert raw.returncode == 0
    assert raw.stdout.encode().rstrip(b"\n") == plan.canonical_bytes


def test_help_is_pure_and_unsafe_gc_arguments_are_rejected(tmp_path: Path) -> None:
    source = inputs(tmp_path)
    prepare(tmp_path, source)
    before = source[0].read_bytes()
    result = run_cli(tmp_path, "pi", "supply", "gc", "--help")
    assert result.returncode == 0
    assert "保存计划但不删除" in result.stdout
    assert source[0].read_bytes() == before
    for option in ("--force", "/tmp/SECRET", "*"):
        result = run_cli(tmp_path, "pi", "supply", "gc", option)
        assert result.returncode == 2
        assert "SECRET" not in result.stderr
    result = run_cli(
        tmp_path, "pi", "supply", "show-plan", "not-an-id", "--database", str(source[0])
    )
    assert result.returncode == 2
    assert "cleanup_plan_missing" in result.stderr


def test_execute_cross_process_and_saved_item_results(tmp_path: Path) -> None:
    from paper_radar.pi_supply import (
        create_cleanup_plan,
        list_cleanup_executions,
        rebuild_supply,
    )

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
    before = source[0].read_bytes()
    for args in [
        ("--execute", "/tmp/SECRET"),
        ("--execute", "*"),
        ("--execute", plan.plan_id, "--force"),
        ("--execute", plan.plan_id, "--dry-run"),
        ("--execute", plan.plan_id, "--data-root", "/tmp/SECRET"),
    ]:
        rejected = run_cli(
            tmp_path, "pi", "supply", "gc", "--database", str(source[0]), *args
        )
        assert rejected.returncode == 2
        assert "SECRET" not in rejected.stderr + rejected.stdout
        assert source[0].read_bytes() == before
    result = run_cli(
        tmp_path,
        "pi",
        "supply",
        "gc",
        "--execute",
        plan.plan_id,
        "--database",
        str(source[0]),
    )
    assert result.returncode == 0, result.stderr
    execution = list_cleanup_executions(source[0])[0]
    assert f"run_id={execution.run_id}" in result.stdout
    assert "phase=completed reason=passed" in result.stdout
    history = run_cli(
        tmp_path,
        "pi",
        "supply",
        "show-plan",
        plan.plan_id,
        "--database",
        str(source[0]),
    )
    assert history.returncode == 0 and f"run_id={execution.run_id}" in history.stdout
