"""B-E15 独立 D1: 中文冷帮助、参数隐私与文件日志执行守卫。"""

import json
from pathlib import Path

import pytest

from tests.config_test_support import run_cli
from tests.test_experiment_candidates_cli import invoke
from tests.test_experiment_exposure_cli import export

DELIVERED_EXECUTION_ENTRIES = ("export-exposure",)


def test_export_help_is_cold_and_complete(tmp_path: Path) -> None:
    result = run_cli(
        tmp_path, "experiment", "export-exposure", "--help", help_only=True
    )
    assert result.returncode == 0, result.stderr
    for fragment in (
        "参数",
        "副作用",
        "自动配额",
        "输出去向",
        "常见失败",
        "示例",
        "130",
        "强身份",
        "校准",
    ):
        assert fragment in result.stdout
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "arguments", [(), ("--root",), ("--private-unknown", "PRIVATE_ARGUMENT")]
)
def test_invalid_arguments_are_controlled_and_do_not_echo_private_input(
    arguments: tuple[str, ...],
) -> None:
    result = invoke("export-exposure", *arguments)
    assert result.exit_code == 2 and "invalid_arguments" in result.output
    assert "PRIVATE_ARGUMENT" not in result.output


@pytest.mark.parametrize("entry", DELIVERED_EXECUTION_ENTRIES)
def test_export_execution_injects_selected_root_file_sink(
    tmp_path: Path, entry: str
) -> None:
    root = tmp_path / "experiment"
    assert invoke("init", "--root", str(root)).exit_code == 0
    result = invoke(entry, "--root", str(root))
    assert result.exit_code == 0, result.output
    lines = [
        json.loads(line)
        for line in (root / "logs/runtime.jsonl").read_text().splitlines()
    ]
    assert [line["event"] for line in lines] == ["run_started", "run_finished"]
    assert all(line["component"] == "experiment" for line in lines)
    assert lines[0]["run_id"] == lines[1]["run_id"]
    assert lines[-1]["category"] == "completed"
    receipt = export(root)
    assert receipt == json.loads(result.stdout)
    assert str(root) not in result.output
