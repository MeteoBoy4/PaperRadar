"""清理计划 CLI 的副作用、原字节查询和参数边界。"""

from pathlib import Path

from tests.config_test_support import run_cli
from tests.pi_supply_support import inputs, prepare


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
