"""激活与显式scope诊断的中文、安全参数和无副作用帮助。"""

from pathlib import Path

import pytest

from tests.config_test_support import run_cli


@pytest.mark.parametrize("args", [["doctor"], ["pi", "supply", "activate"]])
def test_help_does_not_open_database_run_program_or_create_files(
    tmp_path: Path, args: list[str]
) -> None:
    result = run_cli(tmp_path, *args, "--help", help_only=True)
    assert result.returncode == 0, result.stderr
    assert all(word in result.stdout for word in ("副作用", "配额", "输出", "示例"))
    assert not tuple(tmp_path.iterdir())


@pytest.mark.parametrize(
    "args",
    [
        ["doctor"],
        [
            "doctor",
            "--scope",
            "SECRET-unknown",
            "--database",
            "missing.db",
            "--snapshot",
            "SECRET-snapshot",
        ],
        ["doctor", "--SECRET-invalid", "SECRET-value"],
        [
            "doctor",
            "--scope",
            "pi-supply",
            "--database",
            "missing.db",
            "--snapshot",
            "f" * 64,
        ],
        ["pi", "supply", "activate", "SECRET-id"],
    ],
)
def test_invalid_scope_missing_arguments_and_missing_database_fail_safely(
    tmp_path: Path, args: list[str]
) -> None:
    result = run_cli(tmp_path, *args)
    assert result.returncode == 2
    assert "SECRET" not in result.stdout + result.stderr
    assert not tuple(tmp_path.iterdir())
