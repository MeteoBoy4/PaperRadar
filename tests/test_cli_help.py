from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _installed_entrypoint() -> Path:
    return Path(sys.executable).with_name("paper-radar")


def _visible_files(root: Path) -> set[Path]:
    return {path.relative_to(root) for path in root.rglob("*")}


def test_installed_entrypoint_has_complete_chinese_help(tmp_path: Path) -> None:
    deny_external_io = Path(__file__).parent / "deny_external_io"
    env = {
        "PATH": os.environ["PATH"],
        "PYTHONPATH": str(deny_external_io),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
    }

    before = _visible_files(tmp_path)
    result = subprocess.run(
        [str(_installed_entrypoint()), "--help"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert before == _visible_files(tmp_path)
    assert "当前用途" in result.stdout
    assert "参数与选项" in result.stdout
    assert "副作用" in result.stdout
    assert "自动配额" in result.stdout
    assert "输出去向" in result.stdout
    assert "常见失败" in result.stdout
    assert "paper-radar --help" in result.stdout
    assert "尚未提供论文处理命令" in result.stdout
    assert "contracts" not in result.stdout
    assert "run-due" not in result.stdout
