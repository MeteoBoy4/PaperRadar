"""离线验证入口的机器可读证据测试。"""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import signal
import subprocess
import sys
from collections.abc import Sequence
from itertools import pairwise
from pathlib import Path
from typing import Any, cast

import pytest

from paper_radar.contracts import ContractName, ContractVersion
from scripts import offline_evidence
from scripts.offline_evidence import (
    CONTRACT_NAMES,
    CONTRACT_VERSION,
    Check,
    default_checks,
    run_offline_verification,
)

ROOT = Path(__file__).resolve().parent.parent
SECRET = "synthetic-api-key-profile-abstract-fulltext-excerpt-prompt-response"


def _check(name: str, code: str, *, enabled: bool = True) -> Check:
    return Check(name, (sys.executable, "-c", code), enabled=enabled)


def _read(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text()))


def test_success_records_actual_scope_hashes_and_versions(tmp_path: Path) -> None:
    checks = (_check("fixture_pass", "pass"),)

    path, result = run_offline_verification(ROOT, checks, tmp_path)
    saved = _read(path)

    assert saved == result
    assert saved["format_version"] == 1
    assert saved["run_id"] == path.stem
    assert saved["overall"] == "passed"
    assert saved["completed"] is True
    assert saved["checks"] == [
        {"id": "fixture_pass", "status": "passed", "reason": "none", "exit_code": 0}
    ]
    assert saved["scope"] == {
        "issue": 12,
        "claim": "implemented_offline_checks_only",
        "full_a1_verified": False,
        "stage_a_verified": False,
        "not_assessed": [
            "business_pipeline",
            "live_sources",
            "llm",
            "pdf",
            "calibration",
        ],
    }
    assert (
        saved["lockfile_sha256"]
        == hashlib.sha256((ROOT / "uv.lock").read_bytes()).hexdigest()
    )
    assert (
        saved["code"]["commit"]
        == subprocess.run(
            ("git", "rev-parse", "HEAD"),
            cwd=ROOT,
            capture_output=True,
            check=True,
            text=True,
        ).stdout.strip()
    )
    assert isinstance(saved["code"]["dirty"], bool)
    boundary = next(item for item in saved["contracts"] if item["name"] == "boundary")
    assert boundary == {
        "name": "boundary",
        "version": "v1",
        "schema_sha256": hashlib.sha256(
            (ROOT / "contracts/screening/boundary/v1/schema.json").read_bytes()
        ).hexdigest(),
    }
    environment = saved["environment"]
    if environment["missing_reason"] is None:
        assert environment["python"] is not None
        assert environment["dependencies"]["pydantic"] is not None
    else:
        assert environment["missing_reason"] == "environment_unavailable"
        assert environment["python"] is None


def test_failure_and_skips_do_not_copy_previous_success_or_private_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    successful_path, _ = run_offline_verification(
        ROOT, (_check("first", "pass"),), tmp_path
    )
    failed_path, failed = run_offline_verification(
        ROOT,
        (
            _check("fixture_skip", "pass", enabled=False),
            _check("fixture_fail", f"print({SECRET!r}); raise SystemExit(7)"),
            _check("after_failure", "pass"),
        ),
        tmp_path,
    )

    assert failed_path != successful_path
    assert _read(successful_path)["overall"] == "passed"
    assert failed["overall"] == "failed"
    assert failed["checks"] == [
        {
            "id": "fixture_skip",
            "status": "not_run",
            "reason": "skipped",
            "exit_code": None,
        },
        {
            "id": "fixture_fail",
            "status": "failed",
            "reason": "exit_nonzero",
            "exit_code": 7,
            "help_zh": "请在本地单独运行该检查，查看具体失败项。",
        },
        {
            "id": "after_failure",
            "status": "not_run",
            "reason": "prior_failure",
            "exit_code": None,
        },
    ]
    assert SECRET not in failed_path.read_text()
    output = capsys.readouterr().out
    assert "处理：请在本地单独运行该检查" in output
    assert SECRET not in output


def test_launch_error_is_failed_and_following_check_is_not_run(tmp_path: Path) -> None:
    path, result = run_offline_verification(
        ROOT,
        (
            Check("missing_executable", (str(tmp_path / "absent"),)),
            _check("later", "pass"),
        ),
        tmp_path,
    )

    assert result["checks"] == [
        {
            "id": "missing_executable",
            "status": "failed",
            "reason": "launch_error",
            "exit_code": None,
            "help_zh": "请在本地单独运行该检查，查看具体失败项。",
        },
        {
            "id": "later",
            "status": "not_run",
            "reason": "prior_failure",
            "exit_code": None,
        },
    ]
    assert _read(path)["overall"] == "failed"


def test_missing_identity_fields_are_explicit_and_contract_scope_can_expand(
    tmp_path: Path,
) -> None:
    root = tmp_path / "empty-repository"
    root.mkdir()

    path, result = run_offline_verification(
        root,
        (_check("fixture_pass", "pass"),),
        tmp_path / "runs",
        contract_names=("boundary", "future-contract"),
    )

    assert result["code"] == {"commit": None, "dirty": None}
    assert result["lockfile_sha256"] is None
    assert result["environment"]["missing_reason"] == "environment_unavailable"
    assert result["contracts"] == [
        {"name": "boundary", "version": "v1", "schema_sha256": None},
        {"name": "future-contract", "version": "v1", "schema_sha256": None},
    ]
    assert _read(path) == result


def test_interruption_records_incomplete_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = subprocess.run

    def interrupt_fixture(
        args: Sequence[str], **kwargs: Any
    ) -> subprocess.CompletedProcess[Any]:
        if args == ("interrupt-fixture",):
            raise KeyboardInterrupt
        return original(args, **kwargs)

    monkeypatch.setattr("scripts.offline_evidence.subprocess.run", interrupt_fixture)
    path, result = run_offline_verification(
        ROOT,
        (Check("interrupted", ("interrupt-fixture",)), _check("later", "pass")),
        tmp_path,
    )

    assert result["completed"] is False
    assert result["overall"] == "incomplete"
    assert result["checks"] == [
        {
            "id": "interrupted",
            "status": "failed",
            "reason": "interrupted",
            "exit_code": None,
            "help_zh": "请在本地单独运行该检查，查看具体失败项。",
        },
        {
            "id": "later",
            "status": "not_run",
            "reason": "interrupted",
            "exit_code": None,
        },
    ]
    assert _read(path) == result


def test_plan_runs_only_registered_contracts() -> None:
    plan = default_checks()
    assert [check.id for check in plan] == [
        "lockfile",
        "format",
        "lint",
        "types",
        "tests",
        "contracts",
    ]
    command = plan[-1].command
    assert set(CONTRACT_NAMES) == {name.value for name in ContractName}
    assert {version.value for version in ContractVersion} == {CONTRACT_VERSION}
    assert command.count("--contract") == len(CONTRACT_NAMES)
    for name in CONTRACT_NAMES:
        assert ("--contract", name) in tuple(pairwise(command))
    for check in plan:
        assert shlex.join(check.command) in check.help_zh


def test_empty_plan_cannot_claim_success(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="至少一项"):
        run_offline_verification(ROOT, (), tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_shell_entrypoint_uses_locked_uv_and_preserves_bootstrap_exit_code(
    tmp_path: Path,
) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    wrapper = scripts / "check-offline"
    wrapper.write_bytes((ROOT / "scripts/check-offline").read_bytes())
    wrapper.chmod(0o755)
    binary_dir = tmp_path / "bin"
    binary_dir.mkdir()
    fake_uv = binary_dir / "uv"
    fake_uv.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$UV_ARGS_FILE"\nexit 23\n')
    fake_uv.chmod(0o755)
    arguments = tmp_path / "uv-args"

    result = subprocess.run(
        (str(wrapper),),
        cwd=tmp_path,
        env={
            **os.environ,
            "PATH": f"{binary_dir}:{os.environ['PATH']}",
            "UV_ARGS_FILE": str(arguments),
        },
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 23
    assert arguments.read_text().splitlines() == [
        "run",
        "--offline",
        "--locked",
        "python",
        "-m",
        "scripts.offline_evidence",
    ]


def test_interrupt_during_identity_collection_retains_parseable_incomplete_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def interrupt(_root: Path) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr("scripts.offline_evidence._git_metadata", interrupt)
    path, result = run_offline_verification(ROOT, (_check("later", "pass"),), tmp_path)

    assert result["overall"] == "incomplete"
    assert result["completed"] is False
    assert result["code"] == {"commit": None, "dirty": None}
    assert result["checks"][0]["status"] == "not_run"
    assert result["checks"][0]["reason"] == "interrupted"
    assert _read(path) == result


def test_interrupt_between_checks_preserves_completed_check_and_marks_rest_unrun(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_write = offline_evidence._write_evidence
    interrupted = False

    def interrupt_after_first(path: Path, evidence: dict[str, Any]) -> None:
        nonlocal interrupted
        original_write(path, evidence)
        if evidence["checks"][0]["status"] == "passed" and not interrupted:
            interrupted = True
            raise KeyboardInterrupt

    monkeypatch.setattr(offline_evidence, "_write_evidence", interrupt_after_first)
    path, result = run_offline_verification(
        ROOT, (_check("first", "pass"), _check("later", "pass")), tmp_path
    )

    assert result["overall"] == "incomplete"
    assert result["checks"][0]["status"] == "passed"
    assert result["checks"][1]["status"] == "not_run"
    assert result["checks"][1]["reason"] == "interrupted"
    assert _read(path) == result


def test_main_reports_failed_evidence_path_and_returns_nonzero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "failed.json"

    def failed_run(
        _root: Path, _checks: tuple[Check, ...], _output_dir: Path
    ) -> tuple[Path, dict[str, str]]:
        return path, {"overall": "failed"}

    monkeypatch.setattr(offline_evidence, "run_offline_verification", failed_run)
    monkeypatch.setattr(signal, "signal", lambda *_args: None)
    assert offline_evidence.main() == 1
    assert str(path) in capsys.readouterr().out
