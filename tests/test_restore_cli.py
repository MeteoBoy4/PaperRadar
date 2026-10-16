"""真实安装入口的恢复帮助、副作用与受控隐私输出。"""

from pathlib import Path

import pytest

from tests.backup_support import tree
from tests.config_test_support import run_cli


@pytest.mark.parametrize("args", [["restore"], ["restore", "verify"]])
def test_restore_help_is_local_and_explicit_about_writing_a_copy(
    tmp_path: Path, args: list[str]
) -> None:
    before = tree(tmp_path)
    result = run_cli(tmp_path, *args, "--help", help_only=True)
    assert result.returncode == 0, result.stderr
    for heading in (
        "当前用途",
        "参数与选项",
        "副作用",
        "自动配额",
        "输出去向",
        "常见失败",
        "示例",
    ):
        assert heading in result.stdout
    assert "写入完整副本" in result.stdout
    assert "父目录" in result.stdout and "staging" in result.stdout
    assert "不是" in result.stdout and "快照 ID" in result.stdout
    assert tree(tmp_path) == before


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["verify"],
        ["verify", "SECRET-invalid"],
        ["verify", "SECRET-invalid", "--target", "SECRET-target"],
        ["verify", "--SECRET-invalid"],
        ["--SECRET-invalid"],
        ["SECRET-unknown"],
    ],
)
def test_restore_input_and_business_errors_never_echo_private_values(
    tmp_path: Path, args: list[str]
) -> None:
    result = run_cli(tmp_path, "restore", *args)
    assert result.returncode == 2
    assert "SECRET" not in result.stdout + result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("phase", ["copy_fail", "publish_fail"])
def test_real_cli_io_failures_are_controlled_and_private(
    tmp_path: Path, phase: str
) -> None:
    import os
    import subprocess
    import sys

    from paper_radar.backup import create_backup
    from tests.backup_support import populated

    database, data_root, _ = populated(tmp_path / "source")
    batch = create_backup(database, data_root, tmp_path / "backups")
    before = tree(batch.batch_dir)
    target = tmp_path / "restored"
    result = subprocess.run(
        [
            str(Path(sys.executable).with_name("paper-radar")),
            "restore",
            "verify",
            str(batch.batch_dir),
            "--target",
            str(target),
        ],
        env={
            "PATH": os.environ["PATH"],
            "PYTHONPATH": str(Path(__file__).parent / "restore_process"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "A3_RESTORE_PHASE": phase,
        },
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "恢复失败" in result.stderr
    assert "SECRET" not in result.stdout + result.stderr
    assert "Traceback" not in result.stderr
    assert tree(batch.batch_dir) == before
    assert not target.exists()
    assert not list(tmp_path.glob(".restore-staging-*"))
