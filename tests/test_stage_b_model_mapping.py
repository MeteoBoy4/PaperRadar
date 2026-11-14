"""B-E6 独立 D1:无 prompt 映射探测的 CLI 与合成 RPC 边界。"""

import json
from pathlib import Path

import pytest

from tests.config_test_support import run_cli

DELIVERED_EXECUTION_ENTRIES = ("probe-models",)


def test_probe_help_is_local_and_describes_refresh_side_effects(tmp_path: Path) -> None:
    result = run_cli(tmp_path, "experiment", "probe-models", "--help", help_only=True)
    assert result.returncode == 0, result.stderr
    for text in (
        "参数",
        "副作用",
        "刷新",
        "自动配额",
        "输出去向",
        "常见失败",
        "130",
        "示例",
    ):
        assert text in result.stdout
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("command", DELIVERED_EXECUTION_ENTRIES)
def test_cli_probes_independent_slots_without_business_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    from tests.model_mapping_support import invoke, prepared
    from tests.test_doctor_process import logical

    args = prepared(tmp_path, monkeypatch)
    root = Path(args[1])
    before = logical(root / "paper-radar.sqlite3")
    result = invoke(command, *args)
    assert result.exit_code == 0, (result.output, result.exception)
    assert json.loads(result.stdout) == [
        {
            "slot": "screening",
            "state": "mapping_settable",
            "reason": "mapping_state_matched",
        },
        {
            "slot": "reading",
            "state": "mapping_settable",
            "reason": "mapping_state_matched",
        },
    ]
    assert logical(root / "paper-radar.sqlite3") == before
    log = (root / "logs/runtime.jsonl").read_text()
    assert '"run_started"' in log and '"run_finished"' in log
    for private in (
        "PRIVATE_WAIVER",
        "PRIVATE_EGRESS",
        "UNREAD_SYNTHETIC_CREDENTIAL_SENTINEL",
        "screening-mapping-model",
        "reading-mapping-model",
    ):
        assert private not in result.output + log


@pytest.mark.parametrize(
    "mode,reason",
    [("model_rejected", "model_rejected"), ("unsupported", "thinking_unsupported")],
)
def test_cli_rejects_exact_mapping_without_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, reason: str
) -> None:
    from tests.model_mapping_support import invoke, prepared
    from tests.test_doctor_process import logical

    args = prepared(tmp_path, monkeypatch, mode)
    database = Path(args[1]) / "paper-radar.sqlite3"
    before = logical(database)
    result = invoke("probe-models", *args, "--slot", "reading")
    assert result.exit_code == 2, result.output
    assert json.loads(result.stdout) == [
        {"slot": "reading", "state": "failed", "reason": reason}
    ]
    assert "§7.8" in result.stderr
    assert logical(database) == before


@pytest.mark.parametrize("gate", ["egress", "strict", "isolation", "install_root"])
def test_cli_denies_before_authentication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, gate: str
) -> None:
    from typing import NoReturn

    from typer.testing import CliRunner

    from paper_radar.cli import app
    from paper_radar.pi_execution.errors import ExecutionError
    from tests.model_mapping_support import invoke, prepared
    from tests.pi_execution_service_support import deny_default_live_io

    args = prepared(tmp_path, monkeypatch)
    root, snapshot = args[1], args[3]
    expected = ""
    if gate == "egress":
        revoked = invoke(
            "egress-authorize",
            "--root",
            root,
            "--snapshot",
            snapshot,
            "--stage",
            "boundary",
            "--reason",
            "owner revoke other scopes",
        )
        assert revoked.exit_code == 0, revoked.output
        expected = "egress_scope_mismatch"
    elif gate == "strict":
        disabled = CliRunner().invoke(
            app,
            [
                "live-evidence",
                "owner-waiver",
                "--database",
                str(Path(root) / "paper-radar.sqlite3"),
                "--disable",
                "--reason",
                "owner strict",
            ],
        )
        assert disabled.exit_code == 0, disabled.output
        deny_default_live_io(tmp_path, monkeypatch)
        expected = "evidence_missing"
    elif gate == "isolation":

        def unavailable() -> NoReturn:
            raise ExecutionError("isolation_unavailable")

        monkeypatch.setattr(
            "paper_radar.pi_execution.launcher.isolation_capability", unavailable
        )
        expected = "isolation_unavailable"
    else:
        args[-1] = str(tmp_path / "wrong-install")
        expected = "install_unavailable"

    def forbidden(*args: object, **kwargs: object) -> NoReturn:
        pytest.fail("前置拒绝之后执行了认证或 Pi 子进程")

    monkeypatch.setattr("subprocess.Popen", forbidden)
    result = invoke("probe-models", *args)
    assert result.exit_code == 2 and expected in result.output, result.output


@pytest.mark.parametrize("fail_cleanup", [False, True])
def test_cli_reclaims_owned_temporary_roots_and_reports_cleanup_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fail_cleanup: bool
) -> None:
    import shutil
    import tempfile
    from typing import Any

    from tests.model_mapping_support import invoke, prepared

    args = prepared(tmp_path, monkeypatch)
    create, delete = tempfile.mkdtemp, shutil.rmtree
    owned: list[Path] = []
    rejected = False

    def temporary(*args: Any, **kwargs: Any) -> str:
        created = create(*args, **kwargs)
        assert isinstance(created, str)
        path = Path(created)
        if path.name.startswith(("paper-radar-auth-", "paper-radar-pi-")):
            owned.append(path)
        return created

    def remove(path: str | Path, *args: Any, **kwargs: Any) -> None:
        nonlocal rejected
        if (
            fail_cleanup
            and Path(path).name.startswith("paper-radar-pi-")
            and not rejected
        ):
            rejected = True
            raise OSError("PRIVATE_FILESYSTEM_FAILURE")
        delete(path, *args, **kwargs)

    monkeypatch.setattr(tempfile, "mkdtemp", temporary)
    monkeypatch.setattr(shutil, "rmtree", remove)
    result = invoke("probe-models", *args, "--slot", "screening")
    assert result.exit_code == (2 if fail_cleanup else 0), result.output
    if fail_cleanup:
        assert "transport_error" in result.output or "cleanup_failed" in result.output
        assert "mapping_settable" not in result.output
    assert len(owned) == 2 and all(not path.exists() for path in owned)
    assert "PRIVATE_FILESYSTEM_FAILURE" not in result.output


def test_cli_interrupt_is_130_with_safe_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typing import NoReturn

    from tests.model_mapping_support import invoke, prepared

    args = prepared(tmp_path, monkeypatch)

    def interrupted(*args: object, **kwargs: object) -> NoReturn:
        raise KeyboardInterrupt("PRIVATE_INTERRUPT")

    monkeypatch.setattr("subprocess.Popen", interrupted)
    result = invoke("probe-models", *args)
    assert result.exit_code == 130 and "interrupted" in result.output
    log = (Path(args[1]) / "logs/runtime.jsonl").read_text()
    assert any(json.loads(line)["event"] == "interrupted" for line in log.splitlines())
    assert "PRIVATE_INTERRUPT" not in log + result.output
