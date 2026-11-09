"""Pi 执行诊断的显式选择、四态及冷进程无副作用。"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.pi_execution_service_support import service_inputs
from tests.test_doctor_process import inventory, invoke, logical


def execute(
    root: Path, *args: str, code: str | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", code]
        if code
        else [str(Path(sys.executable).with_name("paper-radar")), "doctor", *args],
        cwd=root,
        env={
            "PATH": os.environ["PATH"],
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": str(Path(__file__).parent / "doctor_pi_exec_guard"),
            "PI_DOCTOR_HELP": "1" if code or "--help" in args else "0",
            "PI_DOCTOR_CREDENTIAL": str(root / "credentials/auth.json"),
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )


def test_help_lists_explicit_execution_selection_without_io(tmp_path: Path) -> None:
    result = invoke(tmp_path, "--help")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "basic/config/pi-supply/pi-exec" in result.stdout
    assert "--credentials-dir" in result.stdout
    assert "Cwd/Live" in result.stdout


def test_selected_execution_reports_missing_live_without_side_effects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, receipt, credentials = service_inputs(tmp_path, monkeypatch)
    before_tree, before_db = inventory(tmp_path), logical(service.database)
    result = execute(
        tmp_path,
        "--scope",
        "pi-exec",
        "--database",
        str(service.database),
        "--snapshot",
        receipt.snapshot_id[:12],
        "--credentials-dir",
        str(credentials),
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert "scope=pi-exec result=failed executable=false" in result.stdout
    assert "check=selection result=passed reason=configuration_valid" in result.stdout
    assert (
        "check=credentials_metadata result=passed reason=metadata_valid"
        in result.stdout
    )
    assert "check=admission result=invalid reason=ledger_untrusted" in result.stdout
    assert (
        "check=authentication result=not_assessed reason=authentication_not_assessed"
        in result.stdout
    )
    assert "Cwd" in result.stdout and "Live" in result.stdout
    for secret in (
        "oauth-test-only-sensitive-sentinel",
        "real-model",
        "Frozen effective Pi system prompt",
    ):
        assert secret not in result.stdout + result.stderr
    assert inventory(tmp_path) == before_tree
    assert logical(service.database) == before_db
    assert service.tasks.status(receipt.receipt_id).used_attempts == 0


@pytest.mark.parametrize(
    "args",
    [
        ("--scope", "pi-exec", "--database", "SECRET"),
        ("--scope", "pi-exec", "--database", "SECRET", "--snapshot", "SECRET"),
        ("--scope", "pi-exec", "--database", "SECRET", "--credentials-dir", "SECRET"),
        ("--scope", "pi-exec", "--snapshot", "SECRET", "--credentials-dir", "SECRET"),
        (
            "--scope",
            "pi-exec",
            "--database",
            "SECRET",
            "--snapshot",
            "SECRET",
            "--credentials-dir",
            "SECRET",
            "--settings",
            "SECRET",
        ),
        (
            "--scope",
            "pi-exec",
            "--database",
            "SECRET",
            "--snapshot",
            "SECRET",
            "--credentials-dir",
            "SECRET",
            "--cwd",
            "SECRET",
        ),
        ("--scope", "basic", "--database", "SECRET", "--credentials-dir", "SECRET"),
        (
            "--scope",
            "config",
            "--database",
            "SECRET",
            "--snapshot",
            "SECRET",
            "--credentials-dir",
            "SECRET",
        ),
        (
            "--scope",
            "pi-supply",
            "--database",
            "SECRET",
            "--snapshot",
            "SECRET",
            "--credentials-dir",
            "SECRET",
        ),
        ("--scope", "SECRET", "--database", "SECRET"),
        (),
    ],
)
def test_usage_rejects_implicit_or_cross_scope_selection_without_echo(
    tmp_path: Path, args: tuple[str, ...]
) -> None:
    result = execute(tmp_path, *args)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "SECRET" not in result.stdout + result.stderr
    assert (
        "--help" in result.stdout + result.stderr
        or "选择" in result.stderr
        or "范围" in result.stderr
    )
    assert inventory(tmp_path) == ()


@pytest.mark.parametrize(
    "code,args", [("import paper_radar.cli", ()), (None, ("--help",))]
)
def test_import_and_help_do_not_import_execution_or_probe(
    tmp_path: Path, code: str | None, args: tuple[str, ...]
) -> None:
    result = execute(tmp_path, *args, code=code)
    assert result.returncode == 0, result.stdout + result.stderr
    assert inventory(tmp_path) == ()


@pytest.mark.parametrize(
    "problem,state,reason",
    [
        ("missing_credentials", "missing", "credentials_missing"),
        ("missing_auth", "missing", "credentials_missing"),
        ("credentials_mode", "invalid", "credentials_invalid"),
        ("credentials_link", "invalid", "credentials_invalid"),
        ("auth_link", "invalid", "credentials_invalid"),
        ("install", "missing", "install_unavailable"),
        ("snapshot", "invalid", "content_invalid"),
    ],
)
def test_missing_or_invalid_fact_keeps_diagnostic_readonly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    problem: str,
    state: str,
    reason: str,
) -> None:
    service, receipt, credentials = service_inputs(tmp_path, monkeypatch)
    if problem == "missing_credentials":
        credentials.rename(tmp_path / "unavailable-credentials")
    elif problem == "missing_auth":
        (credentials / "auth.json").unlink()
    elif problem == "credentials_mode":
        credentials.chmod(0o755)
    elif problem == "credentials_link":
        credentials.rename(tmp_path / "real-credentials")
        credentials.symlink_to(tmp_path / "real-credentials", target_is_directory=True)
    elif problem == "auth_link":
        (credentials / "auth.json").rename(credentials / "real-auth")
        (credentials / "auth.json").symlink_to(credentials / "real-auth")
    elif problem == "install":
        service.roots.install_root.rename(tmp_path / "unavailable-install")
    before_tree, before_db = inventory(tmp_path), logical(service.database)
    result = execute(
        tmp_path,
        "--scope",
        "pi-exec",
        "--database",
        str(service.database),
        "--snapshot",
        "f" * 64 if problem == "snapshot" else receipt.snapshot_id,
        "--credentials-dir",
        str(credentials),
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert f"result={state} reason={reason}" in result.stdout
    assert "oauth-test-only-sensitive-sentinel" not in result.stdout + result.stderr
    assert inventory(tmp_path) == before_tree
    assert logical(service.database) == before_db
    assert service.tasks.status(receipt.receipt_id).used_attempts == 0


def test_snapshot_explicit_sampling_is_invalid_in_diagnostic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, receipt, credentials = service_inputs(tmp_path, monkeypatch, legacy=True)
    result = execute(
        tmp_path,
        "--scope",
        "pi-exec",
        "--database",
        str(service.database),
        "--snapshot",
        receipt.snapshot_id,
        "--credentials-dir",
        str(credentials),
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert (
        "check=admission result=invalid reason=sampling_mapping_unavailable"
        in result.stdout
    )
    assert "oauth-test-only-sensitive-sentinel" not in result.stdout + result.stderr


@pytest.mark.parametrize(
    "problem,state,reason",
    [
        ("empty", "passed", "cwd_metadata_valid"),
        ("missing", "missing", "cwd_missing"),
        ("polluted", "invalid", "cwd_not_empty"),
        ("link", "invalid", "cwd_invalid"),
    ],
)
def test_cwd_checks_share_execution_policy_and_do_not_grant_admission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    problem: str,
    state: str,
    reason: str,
) -> None:
    from paper_radar.doctor.pi_exec import execution_checks

    service, receipt, credentials = service_inputs(tmp_path, monkeypatch)
    cwd = tmp_path / "cwd"
    if problem == "missing":
        cwd.rmdir()
    elif problem == "polluted":
        (cwd / "project-context").write_text("SECRET")
    elif problem == "link":
        cwd.rename(tmp_path / "real-cwd")
        cwd.symlink_to(tmp_path / "real-cwd", target_is_directory=True)
    monkeypatch.setattr("paper_radar.doctor.pi_exec.EXECUTION_CWD", cwd)
    before = inventory(tmp_path)
    checks = execution_checks(service.database, receipt.snapshot_id, credentials)
    selected = {check.name: check for check in checks}
    assert selected["cwd"].result.value == state
    assert selected["cwd"].reason == reason
    assert selected["admission"].result.value == "invalid"
    assert selected["admission"].reason == "ledger_untrusted"
    assert selected["authentication"].result.value == "not_assessed"
    assert inventory(tmp_path) == before


@pytest.mark.parametrize(
    "problem,state,reason",
    [
        ("model_missing", "missing", "screening_configuration_missing"),
        ("provider", "invalid", "auth_mode_unsupported"),
        ("protocol", "invalid", "protocol_unsupported"),
        ("snapshot_corrupt", "invalid", "content_invalid"),
    ],
)
def test_snapshot_facts_do_not_become_execution_permission(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    problem: str,
    state: str,
    reason: str,
) -> None:
    import sqlite3

    import yaml

    from paper_radar.config import compile_config

    service, receipt, credentials = service_inputs(tmp_path, monkeypatch)
    snapshot_id = receipt.snapshot_id
    if problem == "snapshot_corrupt":
        with sqlite3.connect(service.database) as connection:
            connection.execute(
                "UPDATE runtime_config_snapshots SET payload_json=? "
                "WHERE snapshot_id=?",
                ("SECRET", snapshot_id),
            )
    else:
        settings = tmp_path / "config/settings.yaml"
        if problem == "protocol":
            old = tmp_path / "config/adapters/pi-v1.yaml"
            (old.parent / "pi-v2.yaml").write_text(
                old.read_text()
                .replace("version: pi-v1", "version: pi-v2")
                .replace("1.4.0", "1.4.99")
            )
            settings.write_text(
                settings.read_text().replace("screening: pi-v1", "screening: pi-v2")
            )
        else:
            source = tmp_path / "config/models/models-v2.yaml"
            models = yaml.safe_load(source.read_text())
            models["version"] = "models-v3"
            if problem == "model_missing":
                models["screening"] = None
            else:
                models["screening"]["provider"] = "SECRET"
            (source.parent / "models-v3.yaml").write_text(yaml.safe_dump(models))
            settings.write_text(settings.read_text().replace("models-v2", "models-v3"))
        snapshot_id = compile_config(settings, service.database).snapshot_id
    before_tree, before_db = inventory(tmp_path), logical(service.database)
    result = execute(
        tmp_path,
        "--scope",
        "pi-exec",
        "--database",
        str(service.database),
        "--snapshot",
        snapshot_id,
        "--credentials-dir",
        str(credentials),
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert f"result={state} reason={reason}" in result.stdout
    assert "SECRET" not in result.stdout + result.stderr
    assert inventory(tmp_path) == before_tree
    assert logical(service.database) == before_db
