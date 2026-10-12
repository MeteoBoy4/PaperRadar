"""真实 CLI 的 adapter 状态、脱敏与无 I/O 帮助。"""

from pathlib import Path

import pytest

from tests.config_adapter_support import adapter_inputs
from tests.config_test_support import run_cli


def test_cli_reports_adapter_slots_without_exposing_system_prompt(
    tmp_path: Path,
) -> None:
    settings, _, db = adapter_inputs(tmp_path)
    result = run_cli(
        tmp_path, "config", "check", "--settings", str(settings), "--database", str(db)
    )
    assert result.returncode == 0, result.stderr
    for slot in ("screening", "reuse_assessment", "reading"):
        assert f"adapters.{slot}：configured" in result.stdout
    assert "Pi 执行就绪" in result.stdout
    assert "不证明" in result.stdout
    assert "Frozen effective" not in result.stdout + result.stderr


@pytest.mark.parametrize("command", ["check", "compile"])
def test_cli_rejects_illegal_pi_policy_without_echoing_input(
    tmp_path: Path, command: str
) -> None:
    settings, path, db = adapter_inputs(tmp_path)
    path.write_text(path.read_text() + "policy:\n  agent_retry: PRIVATE_MARKER\n")
    result = run_cli(
        tmp_path, "config", command, "--settings", str(settings), "--database", str(db)
    )
    assert result.returncode == 2
    assert "adapter.policy.agent_retry" in result.stderr
    assert "PRIVATE_MARKER" not in result.stdout + result.stderr


@pytest.mark.parametrize(
    "args", [(), ("config",), ("config", "check"), ("config", "compile")]
)
def test_help_has_no_config_database_or_external_io(
    tmp_path: Path, args: tuple[str, ...]
) -> None:
    result = run_cli(tmp_path, *args, "--help", help_only=True)
    assert result.returncode == 0, result.stderr
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("command", ["check", "compile"])
@pytest.mark.parametrize("slot", ["screening", "reuse_assessment", "reading"])
def test_cli_rejects_dangling_adapter_selection_with_an_actionable_slot(
    tmp_path: Path, command: str, slot: str
) -> None:
    settings, _, db = adapter_inputs(tmp_path)
    settings.write_text(
        settings.read_text().replace(f"{slot}: pi-v1", f"{slot}: pi-absent")
    )
    result = run_cli(
        tmp_path, "config", command, "--settings", str(settings), "--database", str(db)
    )
    assert result.returncode == 2
    assert f"adapters.{slot}" in result.stderr
    assert "无法读取文件" in result.stderr
    assert "请检查路径和权限" in result.stderr
    assert "Frozen effective" not in result.stdout + result.stderr
