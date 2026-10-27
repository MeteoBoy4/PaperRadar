"""冷进程中的新旧命令帮助; 沿用现有 socket/SQLite 拒绝哨兵。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "arguments",
    [
        ("fixture",),
        ("fixture", "register"),
        ("fixture", "check"),
        ("fixture", "list"),
        ("fixture", "show"),
        ("audit",),
        ("audit", "list"),
        ("audit", "show"),
        ("audit", "run"),
        ("audit", "resume"),
        ("audit", "replay"),
        ("db", "upgrade"),
        ("config", "compile"),
        ("backup", "create"),
        ("restore", "verify"),
        ("paper", "trace"),
        ("pi", "supply"),
        ("doctor",),
    ],
)
def test_installed_new_and_existing_commands_help_has_no_external_io(
    tmp_path: Path, arguments: tuple[str, ...]
) -> None:
    result = subprocess.run(
        [str(Path(sys.executable).with_name("paper-radar")), *arguments, "--help"],
        cwd=tmp_path,
        env={
            "PATH": os.environ["PATH"],
            "PYTHONPATH": str(Path(__file__).parent / "deny_external_io"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONIOENCODING": "utf-8",
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "示例" in result.stdout and "--help" in result.stdout
    assert list(tmp_path.iterdir()) == []
