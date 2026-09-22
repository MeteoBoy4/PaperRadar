"""A1 结论从本次证据和固定范围产生。"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest

from paper_radar.contracts import ContractCheckError, ContractCheckErrorCategory
from scripts import a1_acceptance
from scripts.offline_evidence import CONTRACT_NAMES, CONTRACT_VERSION, default_checks

ROOT = Path(__file__).resolve().parent.parent


def _case(tmp_path: Path) -> tuple[Path, Path, dict[str, Any]]:
    target = tmp_path / "contracts"
    shutil.copytree(ROOT / "contracts", target, dirs_exist_ok=True)
    evidence_path = tmp_path / "evidence" / "run-1.json"
    evidence_path.parent.mkdir()
    evidence: dict[str, Any] = {
        "format_version": 1,
        "run_id": "run-1",
        "scope": {
            "issue": 12,
            "claim": "implemented_offline_checks_only",
            "full_a1_verified": False,
            "stage_a_verified": False,
        },
        "completed": True,
        "overall": "passed",
        "code": a1_acceptance.capture_identity(ROOT).code,
        "lockfile_sha256": hashlib.sha256((ROOT / "uv.lock").read_bytes()).hexdigest(),
        "environment": {
            "python": "3.12.0",
            "dependencies": dict.fromkeys(
                ("pydantic", "typer", "pytest", "ruff", "mypy"), "1.0"
            ),
            "missing_reason": None,
        },
        "contracts": [
            {
                "name": name,
                "version": CONTRACT_VERSION,
                "schema_sha256": hashlib.sha256(
                    (
                        target / "screening" / name / CONTRACT_VERSION / "schema.json"
                    ).read_bytes()
                ).hexdigest(),
            }
            for name in CONTRACT_NAMES
        ],
        "checks": [
            {"id": check.id, "status": "passed", "reason": "none", "exit_code": 0}
            for check in default_checks()
        ],
    }
    evidence_path.write_text(json.dumps(evidence))
    return target, evidence_path, evidence


def _conclude(
    tmp_path: Path,
    target: Path,
    evidence_path: Path,
    *,
    baseline: a1_acceptance.RunIdentity | None = None,
) -> dict[str, Any]:
    path, result = a1_acceptance.write_a1_conclusion(
        ROOT,
        evidence_path,
        tmp_path / "conclusions",
        baseline or a1_acceptance.capture_identity(ROOT),
        contract_target=target,
        expected_run_id=evidence_path.stem,
    )
    assert cast(dict[str, Any], json.loads(path.read_text())) == result
    assert path.parent == tmp_path / "conclusions"
    return result


def _new_run(evidence_path: Path, evidence: dict[str, Any], run_id: str) -> Path:
    evidence["run_id"] = run_id
    path = evidence_path.with_name(f"{run_id}.json")
    path.write_text(json.dumps(evidence))
    return path


def test_full_fixed_scope_passes_with_current_evidence(tmp_path: Path) -> None:
    target, evidence_path, _ = _case(tmp_path)
    result = _conclude(tmp_path, target, evidence_path)

    assert result["status"] == "passed"
    assert result["a1_verified"] is True
    assert result["stage_a_verified"] is False
    assert result["required_checks"] == [check.id for check in default_checks()]
    assert result["required_contracts"] == list(CONTRACT_NAMES)
    assert "runtime_plan" in result["not_assessed"]
    assert (
        result["evidence_sha256"]
        == hashlib.sha256(evidence_path.read_bytes()).hexdigest()
    )


def test_missing_snapshot_and_version_drift_cannot_pass(tmp_path: Path) -> None:
    target, evidence_path, evidence = _case(tmp_path)
    (target / "screening" / "boundary" / "v1" / "schema.json").unlink()
    missing = _conclude(tmp_path, target, evidence_path)
    assert missing["status"] == "failed"
    assert any(reason["code"] == "snapshot_invalid" for reason in missing["reasons"])

    shutil.copy2(
        ROOT / "contracts/screening/boundary/v1/schema.json",
        target / "screening/boundary/v1/schema.json",
    )
    manifest = target / "screening" / "boundary" / "v1" / "manifest.json"
    payload = json.loads(manifest.read_text())
    payload["version"] = "v2"
    manifest.write_text(json.dumps(payload))
    evidence_path = _new_run(evidence_path, evidence, "run-2")
    drift = _conclude(tmp_path, target, evidence_path)
    assert drift["status"] == "failed"
    assert any(reason["code"] == "snapshot_invalid" for reason in drift["reasons"])


def test_skipped_check_and_batch_interruption_cannot_pass(tmp_path: Path) -> None:
    target, evidence_path, evidence = _case(tmp_path)
    evidence["checks"][2].update(status="not_run", reason="skipped", exit_code=None)
    evidence_path.write_text(json.dumps(evidence))
    skipped = _conclude(tmp_path, target, evidence_path)
    assert skipped["status"] == "failed"
    assert any(reason["code"] == "check_not_passed" for reason in skipped["reasons"])

    evidence["completed"] = False
    evidence["overall"] = "incomplete"
    evidence["checks"][-1].update(status="failed", reason="interrupted", exit_code=None)
    (target / "screening" / "reuse-assessment" / "v1" / "manifest.json").unlink()
    evidence_path = _new_run(evidence_path, evidence, "run-2")
    interrupted = _conclude(tmp_path, target, evidence_path)
    assert interrupted["status"] == "incomplete"


def test_repair_uses_new_evidence_and_changed_identity_fails(tmp_path: Path) -> None:
    target, evidence_path, evidence = _case(tmp_path)
    baseline = a1_acceptance.capture_identity(ROOT)
    evidence["contracts"][0]["schema_sha256"] = "0" * 64
    evidence_path.write_text(json.dumps(evidence))
    stale = _conclude(tmp_path, target, evidence_path, baseline=baseline)
    assert stale["status"] == "failed"
    assert any(
        reason["code"] == "snapshot_hash_mismatch" for reason in stale["reasons"]
    )

    evidence["contracts"][0]["schema_sha256"] = hashlib.sha256(
        (target / "screening" / "boundary" / "v1" / "schema.json").read_bytes()
    ).hexdigest()
    evidence_path = _new_run(evidence_path, evidence, "run-2")
    repaired = _conclude(tmp_path, target, evidence_path, baseline=baseline)
    assert repaired["status"] == "passed"
    assert repaired["evidence_sha256"] != stale["evidence_sha256"]

    changed = a1_acceptance.RunIdentity(
        code=baseline.code,
        lockfile_sha256="0" * 64,
        worktree_sha256=baseline.worktree_sha256,
    )
    evidence_path = _new_run(evidence_path, evidence, "run-3")
    outdated = _conclude(tmp_path, target, evidence_path, baseline=changed)
    assert outdated["status"] == "failed"
    assert any(reason["code"] == "identity_changed" for reason in outdated["reasons"])


def test_missing_required_check_rejects_a1(tmp_path: Path) -> None:
    target, evidence_path, evidence = _case(tmp_path)
    evidence["checks"].pop(0)
    evidence_path.write_text(json.dumps(evidence))

    result = _conclude(tmp_path, target, evidence_path)
    assert result["status"] == "failed"
    assert any(reason["code"] == "check_scope_mismatch" for reason in result["reasons"])


def test_shell_help_does_not_create_evidence(tmp_path: Path) -> None:
    subprocess.run(("git", "init", "-q", str(tmp_path)), check=True)
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    wrapper = scripts / "check-offline"
    wrapper.write_bytes((ROOT / "scripts/check-offline").read_bytes())
    wrapper.chmod(0o755)
    result = subprocess.run(
        (str(wrapper), "--help"),
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "A1" in result.stdout
    assert "[离线检查]" not in result.stdout
    assert "[A1 验收]" not in result.stdout
    assert not (tmp_path / "verification-runs").exists()


def test_worktree_identity_detects_executable_mode_change(tmp_path: Path) -> None:
    subprocess.run(("git", "init", "-q", str(tmp_path)), check=True)
    script = tmp_path / "script.sh"
    script.write_text("#!/bin/sh\nexit 0\n")
    os.chmod(script, 0o644)
    subprocess.run(("git", "add", "script.sh"), cwd=tmp_path, check=True)
    first = a1_acceptance.capture_identity(tmp_path).worktree_sha256

    os.chmod(script, 0o755)
    second = a1_acceptance.capture_identity(tmp_path).worktree_sha256

    assert first is not None
    assert second is not None
    assert first != second


def test_deleted_tracked_file_keeps_a_deterministic_worktree_hash(
    tmp_path: Path,
) -> None:
    subprocess.run(("git", "init", "-q", str(tmp_path)), check=True)
    tracked = tmp_path / "tracked.txt"
    tracked.write_text("fixture")
    subprocess.run(("git", "add", "tracked.txt"), cwd=tmp_path, check=True)
    before = a1_acceptance.capture_identity(tmp_path).worktree_sha256

    tracked.unlink()
    after = a1_acceptance.capture_identity(tmp_path).worktree_sha256

    assert before is not None
    assert after is not None
    assert before != after


def test_unreadable_evidence_reports_only_its_direct_cause(tmp_path: Path) -> None:
    target, evidence_path, _ = _case(tmp_path)
    evidence_path.write_text("{")

    result = _conclude(tmp_path, target, evidence_path)
    assert result["status"] == "failed"
    assert [reason["code"] for reason in result["reasons"]] == ["evidence_unavailable"]


def test_invalid_contract_selection_has_specific_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target, evidence_path, _ = _case(tmp_path)

    def invalid_selection(*_args: object) -> None:
        raise ContractCheckError(
            ContractCheckErrorCategory.INVALID_SELECTION, "fixture"
        )

    monkeypatch.setattr(a1_acceptance, "check_frozen_contracts", invalid_selection)
    result = _conclude(tmp_path, target, evidence_path)

    assert result["status"] == "failed"
    assert any(
        reason["code"] == "contract_scope_mismatch" for reason in result["reasons"]
    )
    assert not any(reason["code"] == "snapshot_invalid" for reason in result["reasons"])


def test_fixed_entry_plan_pairs_new_evidence_and_conclusion_for_each_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(("git", "init", "-q", str(root)), check=True)
    shutil.copytree(ROOT / "contracts", root / "contracts")
    shutil.copytree(
        ROOT / "tests",
        root / "tests",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    shutil.copy2(ROOT / "uv.lock", root / "uv.lock")
    shutil.copy2(ROOT / "pyproject.toml", root / "pyproject.toml")
    subprocess.run(("git", "add", "."), cwd=root, check=True)
    subprocess.run(
        (
            "git",
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ),
        cwd=root,
        check=True,
    )
    binary_dir = tmp_path / "bin"
    binary_dir.mkdir()
    fake_uv = binary_dir / "uv"
    environment_json = json.dumps(
        {
            "python": "3.14.0",
            "dependencies": dict.fromkeys(
                ("pydantic", "typer", "pytest", "ruff", "mypy"), "1"
            ),
        }
    )
    fake_uv.write_text(
        "#!/bin/sh\n"
        'case "$*" in\n'
        f'  *"python -c"*) printf "%s\\n" \'{environment_json}\' ;;\n'
        '  *" pytest"*) '
        'printf "%s" "${PYTEST_ADDOPTS-unset}" > "$A1_TEST_PYTEST_ENV_FILE" ;;\n'
        '  *"contracts check"*) '
        'if [ "${A1_TEST_INTERRUPT:-}" = 1 ]; then kill -TERM $$; fi ;;\n'
        "esac\nexit 0\n"
    )
    fake_uv.chmod(0o755)
    monkeypatch.setenv("PATH", f"{binary_dir}:{os.environ['PATH']}")
    marker = tmp_path / "pytest-addopts"
    monkeypatch.setenv("A1_TEST_PYTEST_ENV_FILE", str(marker))
    monkeypatch.setenv("PYTEST_ADDOPTS", "-k no_such_case")
    output_dir = tmp_path / "runs"

    def run() -> tuple[Path, dict[str, Any]]:
        path, conclusion = a1_acceptance.run_a1_verification(root, output_dir)
        assert (output_dir / f"{conclusion['run_id']}.json").exists()
        assert json.loads(path.read_text()) == conclusion
        return path, conclusion

    _, normal = run()
    assert normal["status"] == "passed"
    assert len(normal["checks"]) == 6
    assert len(normal["contracts"]) == 4
    assert normal["environment"]["python"] == "3.14.0"
    assert marker.read_text() == "unset"

    required = root / "tests/test_contract_export.py"
    required.unlink()
    _, missing_test = run()
    assert missing_test["status"] == "failed"
    assert any(
        reason["code"] == "test_scope_mismatch" for reason in missing_test["reasons"]
    )
    shutil.copy2(ROOT / "tests/test_contract_export.py", required)
    required.write_bytes(required.read_bytes() + b"\n")
    _, drifted_test = run()
    assert drifted_test["status"] == "failed"
    assert any(
        reason["code"] == "test_scope_mismatch" for reason in drifted_test["reasons"]
    )
    shutil.copy2(ROOT / "tests/test_contract_export.py", required)

    original_capture = a1_acceptance.capture_identity
    capture_calls = 0

    def interrupt_after_checks(path: Path) -> a1_acceptance.RunIdentity:
        nonlocal capture_calls
        capture_calls += 1
        if capture_calls == 2:
            raise KeyboardInterrupt
        return original_capture(path)

    with monkeypatch.context() as scoped:
        scoped.setattr(a1_acceptance, "capture_identity", interrupt_after_checks)
        _, interrupted_after_checks = run()
    assert interrupted_after_checks["status"] == "incomplete"
    assert any(
        reason["code"] == "run_incomplete"
        for reason in interrupted_after_checks["reasons"]
    )

    schema = root / "contracts/screening/boundary/v1/schema.json"
    schema.unlink()
    _, missing = run()
    assert missing["status"] == "failed"

    shutil.copy2(ROOT / "contracts/screening/boundary/v1/schema.json", schema)
    manifest = root / "contracts/screening/boundary/v1/manifest.json"
    manifest.write_text(
        manifest.read_text().replace('"version": "v1"', '"version": "v2"')
    )
    _, drift = run()
    assert drift["status"] == "failed"

    shutil.copy2(ROOT / "contracts/screening/boundary/v1/manifest.json", manifest)
    original_checks = default_checks
    with monkeypatch.context() as scoped:
        scoped.setattr(
            a1_acceptance,
            "default_checks",
            lambda: tuple(
                replace(check, enabled=False) if check.id == "lint" else check
                for check in original_checks()
            ),
        )
        _, skipped = run()
    assert skipped["status"] == "failed"
    assert any(reason["code"] == "check_not_passed" for reason in skipped["reasons"])

    snapshot = root / "contracts/screening/decision-reasons/v1/schema.json"
    snapshot.unlink()
    monkeypatch.setenv("A1_TEST_INTERRUPT", "1")
    _, interrupted = run()
    monkeypatch.delenv("A1_TEST_INTERRUPT")
    assert interrupted["status"] == "incomplete"

    shutil.copy2(ROOT / "contracts/screening/decision-reasons/v1/schema.json", snapshot)
    _, repaired = run()
    assert repaired["status"] == "passed"
    assert (
        len(
            {
                normal["run_id"],
                missing_test["run_id"],
                drifted_test["run_id"],
                interrupted_after_checks["run_id"],
                missing["run_id"],
                drift["run_id"],
                skipped["run_id"],
                interrupted["run_id"],
                repaired["run_id"],
            }
        )
        == 9
    )
