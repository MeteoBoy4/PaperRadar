from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


def _installed_entrypoint() -> Path:
    return Path(sys.executable).with_name("paper-radar")


def _run_cli(cwd: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    env = {
        "PATH": os.environ["PATH"],
        "PYTHONPATH": str(Path(__file__).parent / "deny_external_io"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
    }
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


@pytest.mark.parametrize(
    "arguments",
    [
        ("--contract", "unknown", "--version", "v1"),
        ("--contract", "boundary", "--version", "../v1"),
    ],
)
def test_cli_rejects_unknown_selection_without_creating_target(
    tmp_path: Path,
    arguments: tuple[str, ...],
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
    assert "未知契约或无效声明版本" in result.stderr
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
    assert "写入失败" in result.stderr
    assert "已创建冻结契约" not in result.stdout
    assert target.read_text(encoding="utf-8") == "occupied"
