"""只读开发入口的退出码、帮助、脱敏及收集模式。"""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMAND = ROOT / "scripts/audit-verification-scope"


def _protected_bytes() -> dict[str, str]:
    paths = (
        subprocess.check_output(
            ["git", "ls-files", "-z"],
            cwd=ROOT,
        )
        .decode()
        .split("\0")
    )
    files = [ROOT / path for path in paths if path]
    files.extend((ROOT / "verification-runs").glob("*"))
    files.append(ROOT / ".git/index")
    return {
        str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.is_file()
    }


def test_default_cli_preserves_registered_material_evidence_and_git_index() -> None:
    before = _protected_bytes()
    process = subprocess.run(
        [str(COMMAND), "--json"],
        cwd="/tmp",
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    report = json.loads(process.stdout)
    assert report["exit_code"] == 0
    assert report["collection"]["reason"] == "not_requested"
    assert report["order"] == [
        "scripts/a1_scope.py",
        "scripts/a2_scope.py",
        "scripts/a2_full_scope.py",
        "scripts/a3_scope.py",
        "scripts/a4_scope.py",
        "scripts/a5_scope.py",
    ]
    assert before == _protected_bytes()


def test_cli_collection_does_not_write_official_receipt(tmp_path: Path) -> None:
    receipt = tmp_path / "formal.json"
    receipt.write_text("unchanged")
    environment = dict(
        os.environ,
        PAPER_RADAR_TEST_RECEIPT=str(receipt),
        PAPER_RADAR_TEST_RUN_ID="SECRET-RUN",
    )
    process = subprocess.run(
        [str(COMMAND), "--collect", "--json"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    report = json.loads(process.stdout)
    assert report["collection"]["reason"] == "ok"
    assert report["collection"]["execution"] == "not_run"
    assert sum(report["collection"]["modules"].values()) == 2519
    assert receipt.read_text() == "unchanged"
    assert "SECRET" not in process.stdout + process.stderr


def test_cli_help_and_invalid_arguments_do_not_echo_arguments() -> None:
    help_result = subprocess.run(
        [str(COMMAND), "--help"], capture_output=True, text=True, check=False
    )
    assert help_result.returncode == 0
    assert "只读" in help_result.stdout
    assert "验收通过" in help_result.stdout
    invalid = subprocess.run(
        [str(COMMAND), "--SECRET-OPTION"], capture_output=True, text=True, check=False
    )
    assert invalid.returncode == 2
    assert "SECRET" not in invalid.stdout + invalid.stderr


def test_cli_reports_drift_and_missing_material_without_file_contents(
    tmp_path: Path,
) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in (
        "__init__.py",
        "audit-verification-scope",
        "audit_verification_scope.py",
        "verification_scope_audit.py",
        "verification_scope_registry.py",
        "verification_scope_collection.py",
    ):
        shutil.copy2(ROOT / "scripts" / name, scripts / name)
    (tmp_path / ".venv").symlink_to(ROOT / ".venv", target_is_directory=True)
    (scripts / "a2_full_acceptance.py").write_text(
        "from types import SimpleNamespace\n"
        "from scripts.future_acceptance import write_group\n"
        "def acceptance_groups():\n"
        "    return (SimpleNamespace(name='A2-01', write=write_group),)\n"
    )
    (scripts / "future_acceptance.py").write_text(
        "from scripts.future_scope import (REQUIRED_TEST_MODULES, "
        "REQUIRED_SOURCE_MODULES, REQUIRED_FIXTURE_FILES)\n"
        "def write_group(): pass\n"
    )
    digest = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    (scripts / "future_scope.py").write_text(
        f"REQUIRED_TEST_MODULES = (('tests/test_missing.py', '{digest}'),)\n"
        f"REQUIRED_SOURCE_MODULES = (('scripts/support.py', '{digest}'),)\n"
        f"REQUIRED_FIXTURE_FILES = (('vector.json', '{digest}'),)\n"
    )
    (scripts / "support.py").write_text("SECRET-SOURCE")
    (tmp_path / "vector.json").write_text("SECRET-VECTOR")
    command = scripts / "audit-verification-scope"
    process = subprocess.run(
        [str(command), "--json"], capture_output=True, text=True, check=False
    )
    assert process.returncode == 1
    report = json.loads(process.stdout)
    assert [(r["role"], r["reason"]) for r in report["files"]] == [
        ("test", "missing_file"),
        ("support", "hash_drift"),
        ("fixture", "hash_drift"),
    ]
    text_result = subprocess.run(
        [str(command)], capture_output=True, text=True, check=False
    )
    assert text_result.returncode == 1
    assert "人工修改 scope" in text_result.stdout
    assert (
        "SECRET"
        not in process.stdout + process.stderr + text_result.stdout + text_result.stderr
    )
