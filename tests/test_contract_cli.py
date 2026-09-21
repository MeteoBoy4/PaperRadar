from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

import pytest

from paper_radar.contracts import (
    ContractName,
    ContractVersion,
    build_frozen_contract,
)
from tests.contract_snapshot_support import (
    canonical_json_bytes,
    filesystem_fingerprint,
    install_self_consistent_schema,
    self_consistent_huge_integer_schema,
)

_CHECK_COMMAND = ("contracts", "check", "--contract", "boundary", "--version", "v1")

_ALL_CONTRACTS = (
    "boundary",
    "value-prediction",
    "reuse-assessment",
    "decision-reasons",
)
_ALL_CONTRACT_ARGUMENTS = tuple(
    argument for name in reversed(_ALL_CONTRACTS) for argument in ("--contract", name)
)
_UNKNOWN_CONTRACT_GUIDANCE = (
    "未知契约；当前支持："
    "boundary、value-prediction、reuse-assessment、decision-reasons。"
)


def _installed_entrypoint() -> Path:
    return Path(sys.executable).with_name("paper-radar")


def _run_cli(
    cwd: Path,
    *arguments: str,
    extra_env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": os.environ["PATH"],
        "PYTHONPATH": str(Path(__file__).parent / "deny_external_io"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
    }
    if extra_env is not None:
        env.update(extra_env)
    return subprocess.run(
        [str(_installed_entrypoint()), *arguments],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_real_cli_exports_deterministic_snapshot_and_repeat_is_noop(
    tmp_path: Path,
) -> None:
    first_target = tmp_path / "first"
    second_target = tmp_path / "second"
    command = (
        "contracts",
        "export",
        "--contract",
        "boundary",
        "--version",
        "v1",
    )
    historical = first_target / "screening" / "boundary" / "v0" / "schema.json"
    historical.parent.mkdir(parents=True)
    historical.write_text("historical snapshot", encoding="utf-8")

    first = _run_cli(tmp_path, *command, "--target", str(first_target))
    schema = first_target / "screening" / "boundary" / "v1" / "schema.json"
    manifest = schema.with_name("manifest.json")

    assert first.returncode == 0, first.stderr
    assert "已创建冻结契约" in first.stdout
    assert "SHA-256" in first.stdout
    mtimes = (schema.stat().st_mtime_ns, manifest.stat().st_mtime_ns)

    repeated = _run_cli(tmp_path, *command, "--target", str(first_target))
    other_process = _run_cli(tmp_path, *command, "--target", str(second_target))

    assert repeated.returncode == 0, repeated.stderr
    assert "内容一致，未改写" in repeated.stdout
    assert (schema.stat().st_mtime_ns, manifest.stat().st_mtime_ns) == mtimes
    assert other_process.returncode == 0, other_process.stderr
    other_schema = second_target / "screening" / "boundary" / "v1" / "schema.json"
    assert other_schema.read_bytes() == schema.read_bytes()
    assert other_schema.with_name("manifest.json").read_bytes() == manifest.read_bytes()
    assert historical.read_text(encoding="utf-8") == "historical snapshot"


def test_real_cli_batch_export_uses_declaration_order_and_repeat_is_noop(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    command = (
        "contracts",
        "export",
        "--contract",
        "decision-reasons",
        "--contract",
        "boundary",
        "--contract",
        "reuse-assessment",
        "--contract",
        "value-prediction",
        "--version",
        "v1",
        "--target",
        str(target),
    )

    first = _run_cli(tmp_path, *command)

    assert first.returncode == 0, first.stderr
    output_positions = [first.stdout.index(name) for name in _ALL_CONTRACTS]
    assert output_positions == sorted(output_positions)
    snapshot_files = {
        name: (
            target / "screening" / name / "v1" / "schema.json",
            target / "screening" / name / "v1" / "manifest.json",
        )
        for name in _ALL_CONTRACTS
    }
    mtimes = {
        name: tuple(path.stat().st_mtime_ns for path in paths)
        for name, paths in snapshot_files.items()
    }

    repeated = _run_cli(tmp_path, *command)

    assert repeated.returncode == 0, repeated.stderr
    assert repeated.stdout.count("内容一致，未改写") == len(_ALL_CONTRACTS)
    assert {
        name: tuple(path.stat().st_mtime_ns for path in paths)
        for name, paths in snapshot_files.items()
    } == mtimes


def test_real_cli_batch_export_recovers_after_second_publish_fails(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    existing = _run_cli(
        tmp_path,
        "contracts",
        "export",
        "--contract",
        "reuse-assessment",
        "--version",
        "v1",
        "--target",
        str(target),
    )
    assert existing.returncode == 0, existing.stderr
    reuse_snapshot = target / "screening" / "reuse-assessment" / "v1"
    reuse_mtimes = tuple(
        (reuse_snapshot / filename).stat().st_mtime_ns
        for filename in ("schema.json", "manifest.json")
    )
    command = (
        "contracts",
        "export",
        *(argument for name in _ALL_CONTRACTS for argument in ("--contract", name)),
        "--version",
        "v1",
        "--target",
        str(target),
    )

    interrupted = _run_cli(
        tmp_path,
        *command,
        extra_env={"PAPER_RADAR_TEST_FAIL_PUBLISH_NUMBER": "2"},
    )

    assert interrupted.returncode == 2
    assert "boundary v1：已创建冻结契约" in interrupted.stdout
    assert "value-prediction v1：未完成 [write_failed]" in interrupted.stderr
    assert "reuse-assessment v1：冻结契约内容一致，未改写" in interrupted.stdout
    assert "decision-reasons v1：未完成" in interrupted.stderr
    assert "synthetic-secret-second-publish" not in (
        interrupted.stdout + interrupted.stderr
    )
    boundary_snapshot = target / "screening" / "boundary" / "v1"
    boundary_mtimes = tuple(
        (boundary_snapshot / filename).stat().st_mtime_ns
        for filename in ("schema.json", "manifest.json")
    )
    assert sorted(path.name for path in (target / "screening").iterdir()) == [
        "boundary",
        "reuse-assessment",
        "value-prediction",
    ]
    assert list((target / "screening" / "value-prediction").iterdir()) == []

    recovered = _run_cli(tmp_path, *command)

    assert recovered.returncode == 0, recovered.stderr
    assert "boundary v1：冻结契约内容一致，未改写" in recovered.stdout
    assert (
        tuple(
            (boundary_snapshot / filename).stat().st_mtime_ns
            for filename in ("schema.json", "manifest.json")
        )
        == boundary_mtimes
    )
    assert (
        tuple(
            (reuse_snapshot / filename).stat().st_mtime_ns
            for filename in ("schema.json", "manifest.json")
        )
        == reuse_mtimes
    )
    for name in _ALL_CONTRACTS:
        snapshot = target / "screening" / name / "v1"
        schema_bytes = (snapshot / "schema.json").read_bytes()
        manifest = json.loads((snapshot / "manifest.json").read_bytes())
        expected = build_frozen_contract(ContractName(name), ContractVersion.V1)
        assert hashlib.sha256(schema_bytes).hexdigest() == expected.schema_sha256
        assert manifest["schema_sha256"] == expected.schema_sha256
        assert f"SHA-256: {expected.schema_sha256}" in recovered.stdout


@pytest.mark.parametrize(
    ("existing_state", "expected_error"),
    [
        ("damaged", "damaged_snapshot"),
        ("version_mismatch", "version_mismatch"),
        ("content_conflict", "content_conflict"),
    ],
)
def test_real_cli_batch_preflight_rejects_existing_problem_before_any_write(
    tmp_path: Path,
    existing_state: str,
    expected_error: str,
) -> None:
    target = tmp_path / "target"
    decision_command = (
        "contracts",
        "export",
        "--contract",
        "decision-reasons",
        "--version",
        "v1",
        "--target",
        str(target),
    )
    created = _run_cli(tmp_path, *decision_command)
    assert created.returncode == 0, created.stderr
    snapshot = target / "screening" / "decision-reasons" / "v1"
    schema_path = snapshot / "schema.json"
    manifest_path = snapshot / "manifest.json"
    if existing_state == "damaged":
        schema_path.write_text('{"synthetic-secret-batch": true}\n', encoding="utf-8")
    else:
        schema = json.loads(schema_path.read_bytes())
        manifest = json.loads(manifest_path.read_bytes())
        if existing_state == "version_mismatch":
            schema["x-paper-radar-contract"]["version"] = "v2"
            manifest["version"] = "v2"
        else:
            schema["description"] = "同版本的另一份有效内容"
        changed_schema = canonical_json_bytes(schema)
        schema_path.write_bytes(changed_schema)
        manifest["schema_sha256"] = hashlib.sha256(changed_schema).hexdigest()
        manifest_path.write_bytes(canonical_json_bytes(manifest))
    before = filesystem_fingerprint(target)

    result = _run_cli(
        tmp_path,
        "contracts",
        "export",
        *(argument for name in _ALL_CONTRACTS for argument in ("--contract", name)),
        "--version",
        "v1",
        "--target",
        str(target),
    )

    assert result.returncode == 2
    assert expected_error in result.stderr
    assert result.stderr.count("未完成") == len(_ALL_CONTRACTS)
    assert "synthetic-secret-batch" not in result.stdout + result.stderr
    assert filesystem_fingerprint(target) == before


@pytest.mark.parametrize(
    "contracts",
    [("unknown", "boundary"), ("boundary", "boundary")],
)
def test_real_cli_batch_rejects_illegal_selection_before_creating_target(
    tmp_path: Path,
    contracts: tuple[str, str],
) -> None:
    target = tmp_path / "target"

    result = _run_cli(
        tmp_path,
        "contracts",
        "export",
        *(argument for name in contracts for argument in ("--contract", name)),
        "--version",
        "v1",
        "--target",
        str(target),
    )

    assert result.returncode == 2
    assert "invalid_selection" in result.stderr
    assert not target.exists()


def test_real_cli_batch_reports_unwritable_target_without_partial_success(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    target.mkdir(mode=0o500)
    try:
        result = _run_cli(
            tmp_path,
            "contracts",
            "export",
            *(argument for name in _ALL_CONTRACTS for argument in ("--contract", name)),
            "--version",
            "v1",
            "--target",
            str(target),
        )
    finally:
        target.chmod(0o700)

    assert result.returncode == 2
    assert "write_failed" in result.stderr
    assert result.stderr.count("未完成") == len(_ALL_CONTRACTS)
    assert list(target.iterdir()) == []


@pytest.mark.parametrize("contract_name", _ALL_CONTRACTS)
def test_each_contract_can_be_exported_repeated_checked_and_detects_conflict(
    tmp_path: Path,
    contract_name: str,
) -> None:
    first_target = tmp_path / "first"
    second_target = tmp_path / "second"
    command = (
        "contracts",
        "export",
        "--contract",
        contract_name,
        "--version",
        "v1",
    )

    created = _run_cli(tmp_path, *command, "--target", str(first_target))
    snapshot_dir = first_target / "screening" / contract_name / "v1"
    schema_path = snapshot_dir / "schema.json"
    manifest_path = snapshot_dir / "manifest.json"
    assert created.returncode == 0, created.stderr
    original_bytes = (schema_path.read_bytes(), manifest_path.read_bytes())
    original_mtimes = (schema_path.stat().st_mtime_ns, manifest_path.stat().st_mtime_ns)

    repeated = _run_cli(tmp_path, *command, "--target", str(first_target))
    independent = _run_cli(tmp_path, *command, "--target", str(second_target))
    before_check = filesystem_fingerprint(first_target)
    checked = _run_cli(
        tmp_path,
        "contracts",
        "check",
        "--contract",
        contract_name,
        "--version",
        "v1",
        "--target",
        str(first_target),
    )

    assert repeated.returncode == 0, repeated.stderr
    assert "内容一致，未改写" in repeated.stdout
    assert original_mtimes == (
        schema_path.stat().st_mtime_ns,
        manifest_path.stat().st_mtime_ns,
    )
    assert independent.returncode == 0, independent.stderr
    other_snapshot = second_target / "screening" / contract_name / "v1"
    assert (other_snapshot / "schema.json").read_bytes() == original_bytes[0]
    assert (other_snapshot / "manifest.json").read_bytes() == original_bytes[1]
    assert checked.returncode == 0, checked.stderr
    assert f"{contract_name} v1" in checked.stdout
    assert filesystem_fingerprint(first_target) == before_check

    schema = json.loads(schema_path.read_bytes())
    manifest = json.loads(manifest_path.read_bytes())
    schema["description"] = "同版本的另一份内部一致内容"
    changed_schema = canonical_json_bytes(schema)
    schema_path.write_bytes(changed_schema)
    manifest["schema_sha256"] = hashlib.sha256(changed_schema).hexdigest()
    manifest_path.write_bytes(canonical_json_bytes(manifest))
    conflicting_bytes = (schema_path.read_bytes(), manifest_path.read_bytes())

    conflict = _run_cli(tmp_path, *command, "--target", str(first_target))
    drift = _run_cli(
        tmp_path,
        "contracts",
        "check",
        "--contract",
        contract_name,
        "--version",
        "v1",
        "--target",
        str(first_target),
    )

    assert conflict.returncode != 0
    assert "content_conflict" in conflict.stderr
    assert drift.returncode != 0
    assert "content_drift" in drift.stderr
    assert (schema_path.read_bytes(), manifest_path.read_bytes()) == conflicting_bytes


@pytest.mark.parametrize(
    ("arguments", "expected_error"),
    [
        (
            ("--contract", "unknown", "--version", "v1"),
            _UNKNOWN_CONTRACT_GUIDANCE,
        ),
        (
            ("--contract", "boundary", "--version", "../v1"),
            "无效声明版本；当前支持：v1",
        ),
    ],
)
def test_cli_rejects_unknown_selection_without_creating_target(
    tmp_path: Path,
    arguments: tuple[str, ...],
    expected_error: str,
) -> None:
    target = tmp_path / "target"

    result = _run_cli(
        tmp_path,
        "contracts",
        "export",
        *arguments,
        "--target",
        str(target),
    )

    assert result.returncode != 0
    assert expected_error in result.stderr
    assert "Traceback" not in result.stderr
    assert not target.exists()


def test_cli_reports_output_failure_without_claiming_success(tmp_path: Path) -> None:
    target = tmp_path / "not-a-directory"
    target.write_text("occupied", encoding="utf-8")

    result = _run_cli(
        tmp_path,
        "contracts",
        "export",
        "--contract",
        "boundary",
        "--version",
        "v1",
        "--target",
        str(target),
    )

    assert result.returncode != 0
    assert "目标路径包含非目录项" in result.stderr
    assert "已创建冻结契约" not in result.stdout
    assert target.read_text(encoding="utf-8") == "occupied"


@pytest.mark.parametrize(
    ("existing_state", "expected_error"),
    [
        ("damaged", "damaged_snapshot"),
        ("version_mismatch", "version_mismatch"),
        ("content_conflict", "content_conflict"),
    ],
)
def test_real_cli_reports_existing_snapshot_problem_without_overwrite(
    tmp_path: Path,
    existing_state: str,
    expected_error: str,
) -> None:
    target = tmp_path / "target"
    command = (
        "contracts",
        "export",
        "--contract",
        "boundary",
        "--version",
        "v1",
        "--target",
        str(target),
    )
    created = _run_cli(tmp_path, *command)
    assert created.returncode == 0, created.stderr
    snapshot_dir = target / "screening" / "boundary" / "v1"
    schema_path = snapshot_dir / "schema.json"
    manifest_path = snapshot_dir / "manifest.json"

    if existing_state == "damaged":
        schema_path.write_text('{"tampered": true}\n', encoding="utf-8")
    else:
        schema = json.loads(schema_path.read_bytes())
        manifest = json.loads(manifest_path.read_bytes())
        if existing_state == "version_mismatch":
            schema["x-paper-radar-contract"]["version"] = "v2"
            manifest["version"] = "v2"
        else:
            schema["description"] = "同版本的另一份有效内容"
        changed_schema = canonical_json_bytes(schema)
        schema_path.write_bytes(changed_schema)
        manifest["schema_sha256"] = hashlib.sha256(changed_schema).hexdigest()
        manifest_path.write_bytes(canonical_json_bytes(manifest))

    before = (schema_path.read_bytes(), manifest_path.read_bytes())
    result = _run_cli(tmp_path, *command)

    assert result.returncode != 0
    assert expected_error in result.stderr
    assert "已创建冻结契约" not in result.stdout
    assert (schema_path.read_bytes(), manifest_path.read_bytes()) == before


def test_real_cli_rejects_path_escape_without_writing_outside_target(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    outside = tmp_path / "outside"
    target.mkdir()
    outside.mkdir()
    (target / "screening").symlink_to(outside, target_is_directory=True)

    result = _run_cli(
        tmp_path,
        "contracts",
        "export",
        "--contract",
        "boundary",
        "--version",
        "v1",
        "--target",
        str(target),
    )

    assert result.returncode != 0
    assert "path_escape" in result.stderr
    assert list(outside.iterdir()) == []


def test_real_cli_interruption_keeps_history_and_leaves_no_partial_snapshot(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    historical = target / "screening" / "boundary" / "v0" / "schema.json"
    historical.parent.mkdir(parents=True)
    historical.write_text("historical snapshot", encoding="utf-8")

    result = _run_cli(
        tmp_path,
        "contracts",
        "export",
        "--contract",
        "boundary",
        "--version",
        "v1",
        "--target",
        str(target),
        extra_env={"PAPER_RADAR_TEST_INTERRUPT_PUBLISH": "1"},
    )

    version_parent = target / "screening" / "boundary"
    assert result.returncode != 0
    assert "write_failed" in result.stderr
    assert "synthetic-secret-cli-interruption" not in result.stderr
    assert "已创建冻结契约" not in result.stdout
    assert historical.read_text(encoding="utf-8") == "historical snapshot"
    assert {path.name for path in version_parent.iterdir()} == {"v0"}


def _export_valid_snapshot(tmp_path: Path, target: Path) -> Path:
    command = (
        "contracts",
        "export",
        "--contract",
        "boundary",
        "--version",
        "v1",
        "--target",
        str(target),
    )
    created = _run_cli(tmp_path, *command)
    assert created.returncode == 0, created.stderr
    return target / "screening" / "boundary" / "v1"


def test_real_cli_check_confirms_snapshot_without_writing(tmp_path: Path) -> None:
    target = tmp_path / "target"
    _export_valid_snapshot(tmp_path, target)
    before = filesystem_fingerprint(target)

    result = _run_cli(tmp_path, *_CHECK_COMMAND, "--target", str(target))

    assert result.returncode == 0, result.stderr
    assert "冻结契约一致" in result.stdout
    assert "boundary v1" in result.stdout
    assert "SHA-256" in result.stdout
    assert filesystem_fingerprint(target) == before


def test_real_cli_batch_check_reports_all_successes_in_declaration_order(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    exported = _run_cli(
        tmp_path,
        "contracts",
        "export",
        *(argument for name in _ALL_CONTRACTS for argument in ("--contract", name)),
        "--version",
        "v1",
        "--target",
        str(target),
    )
    assert exported.returncode == 0, exported.stderr
    before = filesystem_fingerprint(target)

    result = _run_cli(
        tmp_path,
        "contracts",
        "check",
        *_ALL_CONTRACT_ARGUMENTS,
        "--version",
        "v1",
        "--target",
        str(target),
    )

    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert len(lines) == len(_ALL_CONTRACTS)
    assert [line.split()[0] for line in lines] == [
        f"contract={name}" for name in _ALL_CONTRACTS
    ]
    assert all("version=v1 result=passed error_category=none" in line for line in lines)
    assert all("SHA-256" in line for line in lines)
    assert filesystem_fingerprint(target) == before


def test_real_cli_batch_check_reports_mixed_results_before_nonzero_exit(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    exported = _run_cli(
        tmp_path,
        "contracts",
        "export",
        *(argument for name in _ALL_CONTRACTS for argument in ("--contract", name)),
        "--version",
        "v1",
        "--target",
        str(target),
    )
    assert exported.returncode == 0, exported.stderr
    boundary = target / "screening" / "boundary" / "v1"
    (boundary / "schema.json").write_text(
        '{"synthetic-secret-cli-batch-check": true}\n',
        encoding="utf-8",
    )
    value = target / "screening" / "value-prediction" / "v1"
    (value / "manifest.json").unlink()
    before = filesystem_fingerprint(target)

    result = _run_cli(
        tmp_path,
        "contracts",
        "check",
        *_ALL_CONTRACT_ARGUMENTS,
        "--version",
        "v1",
        "--target",
        str(target),
    )

    assert result.returncode == 2
    lines = [
        line for line in result.stderr.splitlines() if line.startswith("contract=")
    ]
    assert [line.split()[0] for line in lines] == [
        f"contract={name}" for name in _ALL_CONTRACTS
    ]
    assert "result=failed error_category=damaged_snapshot" in lines[0]
    assert "result=failed error_category=missing_snapshot" in lines[1]
    assert all("result=passed error_category=none" in line for line in lines[2:])
    assert "synthetic-secret-cli-batch-check" not in result.stdout + result.stderr
    assert filesystem_fingerprint(target) == before


def test_real_cli_batch_check_reports_every_failure_without_creating_target(
    tmp_path: Path,
) -> None:
    target = tmp_path / "absent"

    result = _run_cli(
        tmp_path,
        "contracts",
        "check",
        *_ALL_CONTRACT_ARGUMENTS,
        "--version",
        "v1",
        "--target",
        str(target),
    )

    assert result.returncode == 2
    lines = [
        line for line in result.stderr.splitlines() if line.startswith("contract=")
    ]
    assert len(lines) == len(_ALL_CONTRACTS)
    assert all(
        "result=failed error_category=missing_snapshot" in line for line in lines
    )
    assert not target.exists()


def test_real_cli_batch_check_rejects_unknown_selection_before_any_result(
    tmp_path: Path,
) -> None:
    target = tmp_path / "absent"

    result = _run_cli(
        tmp_path,
        "contracts",
        "check",
        "--contract",
        "boundary",
        "--contract",
        "unknown",
        "--version",
        "v1",
        "--target",
        str(target),
    )

    assert result.returncode == 2
    assert "invalid_selection" in result.stderr
    assert "result=passed" not in result.stdout + result.stderr
    assert "result=failed" not in result.stdout + result.stderr
    assert not target.exists()


def test_real_cli_check_on_missing_snapshot_creates_nothing(tmp_path: Path) -> None:
    target = tmp_path / "absent"

    result = _run_cli(tmp_path, *_CHECK_COMMAND, "--target", str(target))

    assert result.returncode != 0
    assert "missing_snapshot" in result.stderr
    assert "Traceback" not in result.stderr
    assert not target.exists()


@pytest.mark.parametrize(
    ("existing_state", "expected_error"),
    [
        ("damaged", "damaged_snapshot"),
        ("missing_manifest", "missing_snapshot"),
        ("version_mismatch", "version_mismatch"),
        ("content_drift", "content_drift"),
    ],
)
def test_real_cli_check_reports_snapshot_problem_without_writing(
    tmp_path: Path,
    existing_state: str,
    expected_error: str,
) -> None:
    target = tmp_path / "target"
    snapshot_dir = _export_valid_snapshot(tmp_path, target)
    schema_path = snapshot_dir / "schema.json"
    manifest_path = snapshot_dir / "manifest.json"

    if existing_state == "damaged":
        schema_path.write_text('{"tampered": true}\n', encoding="utf-8")
    elif existing_state == "missing_manifest":
        manifest_path.unlink()
    else:
        schema = json.loads(schema_path.read_bytes())
        manifest = json.loads(manifest_path.read_bytes())
        if existing_state == "version_mismatch":
            schema["x-paper-radar-contract"]["version"] = "v2"
            manifest["version"] = "v2"
        else:
            schema["description"] = "同版本的另一份有效内容"
        changed_schema = canonical_json_bytes(schema)
        schema_path.write_bytes(changed_schema)
        manifest["schema_sha256"] = hashlib.sha256(changed_schema).hexdigest()
        manifest_path.write_bytes(canonical_json_bytes(manifest))

    before = filesystem_fingerprint(target)
    result = _run_cli(tmp_path, *_CHECK_COMMAND, "--target", str(target))

    assert result.returncode != 0
    assert expected_error in result.stderr
    assert "Traceback" not in result.stderr
    assert "冻结契约一致" not in result.stdout
    assert filesystem_fingerprint(target) == before


def test_real_cli_check_reports_unreadable_snapshot_without_writing(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    snapshot_dir = _export_valid_snapshot(tmp_path, target)
    schema_path = snapshot_dir / "schema.json"
    schema_path.chmod(0o000)
    try:
        before = filesystem_fingerprint(target)

        result = _run_cli(tmp_path, *_CHECK_COMMAND, "--target", str(target))

        assert result.returncode != 0
        assert "unreadable_snapshot" in result.stderr
        assert "Traceback" not in result.stderr
        assert filesystem_fingerprint(target) == before
    finally:
        schema_path.chmod(0o600)


def test_real_cli_check_errors_do_not_leak_snapshot_content(tmp_path: Path) -> None:
    target = tmp_path / "target"
    snapshot_dir = _export_valid_snapshot(tmp_path, target)
    (snapshot_dir / "schema.json").write_text(
        '{"synthetic-secret-contract-check": "sk-test-123"}\n',
        encoding="utf-8",
    )

    result = _run_cli(tmp_path, *_CHECK_COMMAND, "--target", str(target))

    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "damaged_snapshot" in result.stderr
    assert "synthetic-secret-contract-check" not in output
    assert "sk-test-123" not in output


def test_real_cli_check_maps_malformed_json_to_damaged_without_traceback(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    snapshot_dir = _export_valid_snapshot(tmp_path, target)
    (snapshot_dir / "schema.json").write_bytes(b'{"x": "\\ud800"}')
    before = filesystem_fingerprint(target)

    result = _run_cli(tmp_path, *_CHECK_COMMAND, "--target", str(target))

    assert result.returncode != 0
    assert "damaged_snapshot" in result.stderr
    assert "Traceback" not in result.stderr
    assert "UnicodeEncodeError" not in result.stderr
    assert filesystem_fingerprint(target) == before


def test_real_cli_check_reports_directory_permission_denied_without_traceback(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    _export_valid_snapshot(tmp_path, target)
    screening = target / "screening"
    before = filesystem_fingerprint(target)
    original_mode = stat.S_IMODE(screening.stat().st_mode)
    screening.chmod(0o000)
    try:
        result = _run_cli(tmp_path, *_CHECK_COMMAND, "--target", str(target))
    finally:
        screening.chmod(original_mode)

    assert result.returncode != 0
    assert "unreadable_snapshot" in result.stderr
    assert "Traceback" not in result.stderr
    assert filesystem_fingerprint(target) == before


def test_real_cli_check_rejects_huge_integer_when_interpreter_limit_disabled(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    snapshot_dir = _export_valid_snapshot(tmp_path, target)
    install_self_consistent_schema(
        snapshot_dir,
        self_consistent_huge_integer_schema(),
    )
    before = filesystem_fingerprint(target)

    result = _run_cli(
        tmp_path,
        *_CHECK_COMMAND,
        "--target",
        str(target),
        extra_env={"PYTHONINTMAXSTRDIGITS": "0"},
    )

    assert result.returncode != 0
    assert "damaged_snapshot" in result.stderr
    assert "Traceback" not in result.stderr
    assert filesystem_fingerprint(target) == before


def test_real_cli_check_rejects_unknown_selection_without_touching_target(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"

    result = _run_cli(
        tmp_path,
        "contracts",
        "check",
        "--contract",
        "unknown",
        "--version",
        "v1",
        "--target",
        str(target),
    )

    assert result.returncode != 0
    assert "invalid_selection" in result.stderr
    assert _UNKNOWN_CONTRACT_GUIDANCE in result.stderr
    assert "Traceback" not in result.stderr
    assert not target.exists()
