"""真实安装入口的备份帮助、中文结果、退出码和隐私。"""

import json
from pathlib import Path

import pytest

from tests.backup_support import populated, tree
from tests.config_test_support import run_cli


@pytest.mark.parametrize(
    "args", [[], ["backup"], ["backup", "create"], ["backup", "verify"]]
)
def test_backup_help_is_local_and_has_all_six_sections(
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
    assert "run-due" not in result.stdout
    assert tree(tmp_path) == before


def test_create_and_verify_report_only_identity_and_kind_summaries(
    tmp_path: Path,
) -> None:
    database, data_root, _ = populated(tmp_path / "source")
    output = tmp_path / "output"
    result = run_cli(
        tmp_path,
        "backup",
        "create",
        "--database",
        str(database),
        "--data-root",
        str(data_root),
        "--output",
        str(output),
    )
    assert result.returncode == 0, result.stderr
    (batch,) = output.iterdir()
    manifest = json.loads((batch / "manifest.json").read_bytes())
    assert batch.name in result.stdout
    assert "清单 SHA-256" in result.stdout
    assert "original_pdf" in result.stdout
    assert "SECRET" not in result.stdout + result.stderr
    assert all(
        item["artifact_id"] not in result.stdout for item in manifest["artifacts"]
    )
    (tmp_path / "source").rename(tmp_path / "unavailable")
    before = tree(batch)
    verified = run_cli(tmp_path, "backup", "verify", str(batch))
    assert verified.returncode == 0, verified.stderr
    assert verified.stdout == result.stdout
    assert tree(batch) == before


@pytest.mark.parametrize(
    "args",
    [
        ["create"],
        ["verify"],
        ["create", "--SECRET-invalid"],
        ["verify", "SECRET-invalid-batch"],
        ["SECRET-unknown"],
    ],
)
def test_input_errors_are_controlled_and_do_not_echo_values(
    tmp_path: Path, args: list[str]
) -> None:
    result = run_cli(tmp_path, "backup", *args)
    assert result.returncode == 2
    assert "SECRET" not in result.stdout + result.stderr
    assert "Traceback" not in result.stderr
    assert (
        "失败" in result.stderr
        or "参数错误" in result.stderr
        or "命令无效" in result.stderr
    )
