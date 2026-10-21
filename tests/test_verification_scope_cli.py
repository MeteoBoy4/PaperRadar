"""只读开发入口的退出码、帮助、脱敏及收集模式。"""

import hashlib
import importlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.a2_full_acceptance import acceptance_groups
from scripts.verification_scope_registry import load_scopes

ROOT = Path(__file__).resolve().parents[1]
COMMAND = ROOT / "scripts/audit-verification-scope"


@pytest.fixture
def isolated_repository(tmp_path: Path) -> Path:
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
        "REQUIRED_TEST_CASE_COUNTS)\n"
        "def write_group(): pass\n"
    )
    return tmp_path


def _register_tests(root: Path, counts: str) -> Path:
    tests = root / "tests"
    tests.mkdir()
    source = (
        "import pytest\n"
        "@pytest.mark.parametrize('value', ['SECRET-ONE', 'SECRET-TWO'])\n"
        "def test_sample(value): raise AssertionError('must not execute')\n"
    )
    (tests / "test_sample.py").write_text(source)
    digest = hashlib.sha256(source.encode()).hexdigest()
    scope = root / "scripts/future_scope.py"
    scope.write_text(
        f"REQUIRED_TEST_MODULES = (('tests/test_sample.py', '{digest}'),)\n"
        f"REQUIRED_TEST_CASE_COUNTS = {counts}\n"
    )
    return scope


@pytest.mark.parametrize("counts", ["{}", "{'tests/test_sample.py': True}"])
def test_collect_reports_missing_or_invalid_counts_without_changing_scope(
    isolated_repository: Path,
    counts: str,
) -> None:
    scope = _register_tests(isolated_repository, counts)
    before = scope.read_bytes()
    command = isolated_repository / "scripts/audit-verification-scope"
    process = subprocess.run(
        [str(command), "--collect", "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    report = json.loads(process.stdout)
    assert process.returncode == 1
    assert report["collection"]["modules"] == {"tests/test_sample.py": 2}
    assert report["counts"] == []
    assert scope.read_bytes() == before
    assert "SECRET" not in process.stdout + process.stderr


def test_stale_count_key_cannot_expand_collection_scope(
    isolated_repository: Path,
) -> None:
    _register_tests(isolated_repository, "{'unregistered_test.py': 7}")
    command = isolated_repository / "scripts/audit-verification-scope"
    process = subprocess.run(
        [str(command), "--collect", "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    report = json.loads(process.stdout)
    assert process.returncode == 1
    assert report["collection"]["reason"] == "count_mismatch"
    assert report["collection"]["modules"] == {"tests/test_sample.py": 2}


def test_collection_measures_parameter_changes_before_hash_rebinding(
    isolated_repository: Path,
) -> None:
    scope = _register_tests(isolated_repository, "{'tests/test_sample.py': 2}")
    before = scope.read_bytes()
    test_file = isolated_repository / "tests/test_sample.py"
    test_file.write_text(
        test_file.read_text().replace(
            "'SECRET-TWO'",
            "'SECRET-TWO', 'SECRET-THREE'",
        )
    )
    command = isolated_repository / "scripts/audit-verification-scope"
    process = subprocess.run(
        [str(command), "--collect", "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    report = json.loads(process.stdout)
    assert process.returncode == 1
    assert report["files"][0]["reason"] == "hash_drift"
    assert report["collection"]["reason"] == "count_mismatch"
    assert report["collection"]["modules"] == {"tests/test_sample.py": 3}
    assert report["counts"][0]["expected_cases"] == 2
    assert scope.read_bytes() == before
    assert "SECRET" not in process.stdout + process.stderr


def test_collection_failure_does_not_blame_all_counted_groups(
    isolated_repository: Path,
) -> None:
    _register_tests(isolated_repository, "{'tests/test_sample.py': 2}")
    (isolated_repository / "conftest.py").write_text(
        "raise RuntimeError('SECRET-COLLECTION-FAILURE')\n"
    )
    command = isolated_repository / "scripts/audit-verification-scope"
    process = subprocess.run(
        [str(command), "--collect", "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    report = json.loads(process.stdout)
    assert process.returncode == 1
    assert report["collection"]["reason"] == "collection_failed"
    assert report["affected_groups"] == []
    assert "SECRET" not in process.stdout + process.stderr


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
    assert set(report["order"]) == {scope.path for scope in load_scopes(ROOT)}
    for path, downstream in report["downstream"].items():
        assert all(
            report["order"].index(path) < report["order"].index(p) for p in downstream
        )
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
    expected: dict[str, int] = {}
    for group in acceptance_groups():
        writer = importlib.import_module(group.write.__module__)
        expected.update(getattr(writer, "REQUIRED_TEST_CASE_COUNTS", {}))
    assert report["collection"]["modules"] == expected
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
    assert "unknown_argument" in invalid.stderr
    invalid_value = subprocess.run(
        [str(COMMAND), "--json=SECRET-VALUE"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert invalid_value.returncode == 2
    assert "invalid_option_value" in invalid_value.stderr
    assert "SECRET" not in invalid_value.stdout + invalid_value.stderr


def test_cli_reports_drift_and_missing_material_without_file_contents(
    isolated_repository: Path,
) -> None:
    tmp_path = isolated_repository
    scripts = tmp_path / "scripts"
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
