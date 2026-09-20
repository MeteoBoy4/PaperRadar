from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


def _installed_entrypoint() -> Path:
    return Path(sys.executable).with_name("paper-radar")


def _visible_files(root: Path) -> set[Path]:
    return {path.relative_to(root) for path in root.rglob("*")}


@pytest.mark.parametrize(
    ("arguments", "example"),
    [
        (["--help"], "paper-radar --help"),
        (["contracts", "--help"], "paper-radar contracts --help"),
        (
            ["contracts", "export", "--help"],
            "paper-radar contracts export --contract boundary --version v1",
        ),
    ],
)
def test_installed_entrypoint_has_complete_chinese_help_without_side_effects(
    tmp_path: Path,
    arguments: list[str],
    example: str,
) -> None:
    deny_external_io = Path(__file__).parent / "deny_external_io"
    env = {
        "PATH": os.environ["PATH"],
        "PYTHONPATH": str(deny_external_io),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
    }

    before = _visible_files(tmp_path)
    result = subprocess.run(
        [str(_installed_entrypoint()), *arguments],
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
    assert example in result.stdout
    assert "run-due" not in result.stdout
