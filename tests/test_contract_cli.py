from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

import pytest

from tests.contract_snapshot_support import canonical_json_bytes


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


@pytest.mark.parametrize(
    ("arguments", "expected_error"),
    [
        (
            ("--contract", "unknown", "--version", "v1"),
            "未知契约；当前支持：boundary",
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
