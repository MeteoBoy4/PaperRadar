"""安装后入口、中文 help 的无 I/O 与参数/失败脱敏。"""

import json
from pathlib import Path

import pytest

from tests.config_test_support import run_cli
from tests.pi_supply_support import inputs, prepare


@pytest.mark.parametrize(
    "args",
    [
        ["pi"],
        ["pi", "supply"],
        ["pi", "supply", "prepare"],
        ["pi", "supply", "list"],
        ["pi", "supply", "show"],
    ],
)
def test_new_help_is_chinese_and_has_no_network_or_database_io(
    tmp_path: Path, args: list[str]
) -> None:
    result = run_cli(tmp_path, *args, "--help", help_only=True)
    assert result.returncode == 0, result.stderr
    assert "副作用" in result.stdout and "配额" in result.stdout
    assert "示例" in result.stdout and "输出" in result.stdout
    assert not tuple(tmp_path.iterdir())


@pytest.mark.parametrize(
    "args",
    [
        ["pi", "SECRET-command"],
        ["pi", "supply", "SECRET-command"],
        ["pi", "supply", "prepare", "--SECRET-invalid", "SECRET-value"],
        ["pi", "supply", "list", "--SECRET-invalid", "SECRET-value"],
    ],
)
def test_argument_failure_redacts_all_user_values(
    tmp_path: Path, args: list[str]
) -> None:
    result = run_cli(tmp_path, *args)
    assert result.returncode == 2
    assert "SECRET" not in result.stdout + result.stderr


def test_cross_process_queries_do_not_need_installed_pi_or_material_sources(
    tmp_path: Path,
) -> None:
    import shutil

    source = inputs(tmp_path)
    prepared = prepare(tmp_path, source)
    # 现场树损坏/缺失不能妨碍历史回查, 输出明确检查仅为历史记录。
    install = tmp_path / "install"
    for directory in install.rglob("*"):
        if directory.is_dir():
            directory.chmod(0o700)
    shutil.rmtree(install)
    source[2].unlink()
    result = run_cli(tmp_path, "pi", "supply", "list", "--database", str(source[0]))
    assert result.returncode == 0 and prepared.supply_id in result.stdout
    assert "历史登记" in result.stdout and "未核验现场" in result.stdout
    assert "First supply" not in result.stdout
    shown = run_cli(
        tmp_path,
        "pi",
        "supply",
        "show",
        prepared.supply_id,
        "--database",
        str(source[0]),
    )
    assert shown.returncode == 0, shown.stderr
    assert (
        json.loads(shown.stdout.splitlines()[0])["d5"]["basis"]
        == "First supply, no baseline"
    )
    assert "install_check" in shown.stdout and "未核验现场" in shown.stdout


def test_pi_group_help_only_describes_its_supply_child(tmp_path: Path) -> None:
    result = run_cli(tmp_path, "pi", "--help", help_only=True)
    assert result.returncode == 0
    assert "supply" in result.stdout
    assert "prepare 准备" not in result.stdout
    assert "pi supply --help" in result.stdout


@pytest.mark.parametrize("decision", ["may_change", "unknown"])
def test_show_and_doctor_disclose_required_d5_semantic_review(
    tmp_path: Path, decision: str
) -> None:
    from paper_radar.pi_supply import activate_supply
    from tests.pi_supply_support import encoded

    source = inputs(tmp_path)
    payload = json.loads(source[2].read_bytes())
    payload["d5"]["decision"] = decision
    source[2].write_bytes(encoded(payload))
    prepared = prepare(tmp_path, source)
    activate_supply(source[0], prepared.supply_id, source[1])
    for arguments in (
        ["pi", "supply", "show", prepared.supply_id],
        ["doctor", "--scope", "pi-supply", "--snapshot", source[1]],
    ):
        result = run_cli(tmp_path, *arguments, "--database", str(source[0]))
        assert "需要后续相关语义评估" in result.stdout
        assert "不代表校准兼容" in result.stdout
