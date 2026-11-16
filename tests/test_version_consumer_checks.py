"""#207 独立 D1: 显式版本消费者目录的公共选择边界。"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.check_compatibility import select_tests

ROOT = Path(__file__).resolve().parents[1]


def test_version_groups_include_reviewed_consumers_and_all_is_ordered_union() -> None:
    required = {
        "renderer": {
            "tests/test_report_replay_projection.py",
            "tests/test_experiment_exposure_migrations.py",
            "tests/test_stage_b_report_renderer_migrations.py",
        },
        "source-guard": {
            "tests/test_live_bundle.py",
            "tests/test_live_epoch_upgrade.py",
            "tests/test_live_admission_source_guard.py",
            "tests/test_stage_b_review_source_history.py",
        },
        "migration": {
            "tests/test_experiment_exposure_migrations.py",
            "tests/test_stage_b_report_renderer_migrations.py",
            "tests/test_migration_expectations.py",
            "tests/test_backup_service.py",
        },
    }
    for group, consumers in required.items():
        assert consumers <= set(select_tests(group)), group
    ordered = tuple(
        dict.fromkeys(
            selector
            for group in ("acceptance", "cli", "renderer", "source-guard", "migration")
            for selector in select_tests(group)
        )
    )
    assert select_tests("all") == ordered


@pytest.mark.parametrize("group", ["renderer", "source-guard", "migration"])
@pytest.mark.parametrize("failure", [False, True])
def test_version_selection_runs_in_synthetic_root_without_external_io(
    tmp_path: Path, group: str, failure: bool
) -> None:
    selections = select_tests(group)
    for selector in selections:
        path = tmp_path / selector
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("def test_synthetic_consumer(): pass\n")
    if failure:
        (tmp_path / selections[0]).write_text(
            "def test_synthetic_consumer():\n"
            "    assert False, 'selected consumer failure'\n"
        )
    (tmp_path / "tests/test_unselected.py").write_text(
        "raise AssertionError('full suite fallback')\n"
    )
    (tmp_path / "conftest.py").write_text(
        "import builtins, io, os, socket, sqlite3\n"
        "from pathlib import Path\n"
        "def denied(*args, **kwargs):\n"
        "    raise AssertionError('external I/O forbidden')\n"
        "socket.socket.connect = denied\n"
        "socket.socket.connect_ex = denied\n"
        "socket.create_connection = denied\n"
        "sqlite3.connect = denied\n"
        "ORIGINAL = builtins.open\n"
        "def guarded(file, *args, **kwargs):\n"
        "    if isinstance(file, (str, bytes, os.PathLike)):\n"
        "        path = Path(os.fsdecode(file)).resolve()\n"
        "        if path == Path.home() or Path.home() in path.parents:\n"
        "            raise AssertionError('credential or real root access')\n"
        "    return ORIGINAL(file, *args, **kwargs)\n"
        "builtins.open = guarded\n"
        "io.open = guarded\n"
    )
    receipt = tmp_path / "outer-receipt.json"
    receipt.write_text("unchanged\n")
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            "from pathlib import Path; from scripts.check_compatibility import "
            "run_checks, select_tests; import sys; "
            "raise SystemExit(run_checks(Path.cwd(), select_tests(sys.argv[1])))",
            group,
        ],
        cwd=tmp_path,
        env={
            **os.environ,
            "PYTHONPATH": str(ROOT),
            "PAPER_RADAR_TEST_RECEIPT": str(receipt),
            "PAPER_RADAR_TEST_RUN_ID": "inherited-forbidden",
        },
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == (1 if failure else 0), result.stdout + result.stderr
    assert f"实际节点总数：{len(selections)}（已去重）" in result.stdout
    for selector in selections:
        assert f"实际选择：{selector}；节点数：1" in result.stdout
    assert (
        "结果：failed；退出码：1" if failure else "结果：passed；退出码：0"
    ) in result.stdout
    assert "full suite fallback" not in result.stdout + result.stderr
    assert receipt.read_text() == "unchanged\n"
    assert not (tmp_path / "verification-runs").exists()
