"""verify/rebuild 入口、真实失败与无 I/O 中文帮助。"""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from paper_radar.cli import app
from paper_radar.pi_supply import SupplyError, show_supply
from paper_radar.pi_supply.transport import HttpDownloader, ProcessRunner
from tests.config_test_support import run_cli
from tests.pi_supply_support import Run, inputs, prepare


@pytest.mark.parametrize("command", ["verify", "rebuild"])
def test_rebuild_and_verify_help_has_no_io(tmp_path: Path, command: str) -> None:
    result = run_cli(tmp_path, "pi", "supply", command, "--help", help_only=True)
    assert result.returncode == 0, result.stderr
    assert all(word in result.stdout for word in ["副作用", "配额", "示例", "输出"])
    assert not tuple(tmp_path.iterdir())
    if command == "rebuild":
        assert "联网" in result.stdout and "不是脱网" in result.stdout


@pytest.mark.parametrize("command", ["verify", "rebuild"])
def test_rebuild_and_verify_argument_errors_do_not_echo_input(
    tmp_path: Path, command: str
) -> None:
    result = run_cli(
        tmp_path, "pi", "supply", command, "SECRET-id", "--SECRET-flag", "SECRET-value"
    )
    assert result.returncode == 2
    assert "SECRET" not in result.stdout + result.stderr


def test_cli_verify_missing_tree_records_failure_and_show_exposes_history(
    tmp_path: Path,
) -> None:
    source = inputs(tmp_path)
    first = prepare(tmp_path, source)
    root = tmp_path / "install"
    moved = tmp_path / "offline-install"
    root.rename(moved)
    result = run_cli(
        tmp_path,
        "pi",
        "supply",
        "verify",
        first.supply_id,
        "--database",
        str(source[0]),
    )
    assert result.returncode == 2
    assert first.install_id in result.stdout and "passed=false" in result.stdout
    shown = run_cli(
        tmp_path, "pi", "supply", "show", first.supply_id, "--database", str(source[0])
    )
    assert shown.returncode == 0
    assert "passed=true" in shown.stdout and "passed=false" in shown.stdout


def test_cli_rebuild_success_and_failure_use_same_public_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = inputs(tmp_path)
    first = prepare(tmp_path, source)
    runner = Run()

    def download(
        _self: HttpDownloader, url: str, *, limit: int, proxy: str | None
    ) -> bytes:
        return source[3].fetch(url, limit=limit, proxy=proxy)

    def execute(
        _self: ProcessRunner,
        argv: tuple[str, ...],
        *,
        cwd: Path,
        env: dict[str, str],
        timeout: int,
        limit: int,
    ) -> bytes:
        return runner.run(argv, cwd=cwd, env=env, timeout=timeout, limit=limit)

    monkeypatch.setattr(HttpDownloader, "fetch", download)
    monkeypatch.setattr(ProcessRunner, "run", execute)
    args = [
        "pi",
        "supply",
        "rebuild",
        first.supply_id,
        "--database",
        str(source[0]),
        "--install-root",
        str(tmp_path / "install"),
        "--data-root",
        str(tmp_path / "data"),
        "--config-root",
        str(tmp_path / "config"),
        "--material-root",
        str(tmp_path / "materials"),
    ]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    assert "尚未激活" in result.output and "scope=install_check" in result.output
    source[3].content = {
        url: b"SECRET-corrupt-archive"
        for url in source[3].content
        if url.endswith(".tar.xz")
    }
    failed = CliRunner().invoke(app, args)
    assert failed.exit_code == 2 and "node_checksum_mismatch" in failed.output
    assert "SECRET" not in failed.output
    shown = CliRunner().invoke(
        app, ["pi", "supply", "show", first.supply_id, "--database", str(source[0])]
    )
    assert (
        shown.exit_code == 0
        and "operation=rebuild reason=node_checksum_mismatch" in shown.output
    )


@pytest.mark.parametrize("interrupted", [False, True])
def test_cli_verify_timeout_and_interrupt_are_controlled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    interrupted: bool,
) -> None:
    source = inputs(tmp_path)
    first = prepare(tmp_path, source)

    def fail(
        _self: ProcessRunner,
        argv: tuple[str, ...],
        *,
        cwd: Path,
        env: dict[str, str],
        timeout: int,
        limit: int,
    ) -> bytes:
        if interrupted:
            raise KeyboardInterrupt("SECRET-interrupt")
        raise SupplyError("process_timeout")

    monkeypatch.setattr(ProcessRunner, "run", fail)
    result = CliRunner().invoke(
        app, ["pi", "supply", "verify", first.supply_id, "--database", str(source[0])]
    )
    assert result.exit_code == (130 if interrupted else 2)
    assert "SECRET" not in result.output
    assert show_supply(source[0], first.supply_id).installs[0].checks[-1].reason == (
        "operation_interrupted" if interrupted else "process_timeout"
    )
