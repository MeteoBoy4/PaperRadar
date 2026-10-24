"""A9 的可信终态格式与只读查询。"""

import json
from pathlib import Path

import pytest

from scripts.a2_full_acceptance import acceptance_groups
from scripts.offline_evidence import file_sha256
from scripts.verification_run import VerificationRun, run_verification
from scripts.verification_status import query_status
from tests.a2_full_support import fake_checks, repository_copy
from tests.a9_acceptance_support import passed_receipt


def test_a9_status_format_and_real_receipt_registration(tmp_path: Path) -> None:
    from scripts.a2_test_receipt import TestReceipt
    from scripts.a9_scope import REQUIRED_TEST_MODULES
    from scripts.verification_status import CHECK_IDS_V1, SUPPORTED_GROUP_FORMATS

    assert SUPPORTED_GROUP_FORMATS[".a9.json"] == (1,)
    assert SUPPORTED_GROUP_FORMATS[".a2-full.json"] == (2,)
    assert CHECK_IDS_V1 == ("lockfile", "format", "lint", "types", "tests", "contracts")
    receipt = TestReceipt(tmp_path / "receipt.json", "synthetic")
    assert {name for name, _ in REQUIRED_TEST_MODULES} <= receipt.modules.keys()


def test_status_recognizes_a9_without_changing_historical_formats() -> None:
    from scripts.verification_status import SUPPORTED_GROUP_FORMATS

    assert SUPPORTED_GROUP_FORMATS[".a9.json"] == (1,)
    assert SUPPORTED_GROUP_FORMATS[".a2-full.json"] == (2,)


@pytest.fixture
def a9_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> VerificationRun:
    import os

    root = repository_copy(tmp_path / "repo")
    binary, log = fake_checks(tmp_path, monkeypatch, receipt=passed_receipt("fixture"))
    monkeypatch.setenv("PATH", f"{binary}:{os.environ['PATH']}")
    monkeypatch.setenv("A2_TEST_CHECK_LOG", str(log))
    return run_verification(root, tmp_path / "runs", acceptance_groups())


@pytest.mark.parametrize(
    "case",
    [
        "passed",
        "changed_tree",
        "missing_a9",
        "tampered_a9",
        "unknown_format",
        "boolean_format",
        "missing_terminal",
        "tampered_terminal",
        "incomplete",
    ],
)
def test_status_requires_same_a9_bytes_and_terminal(
    a9_run: VerificationRun, case: str
) -> None:
    run = a9_run
    path = run.output_dir / f"{run.run_id}.terminal.json"
    terminal = json.loads(path.read_bytes())
    a9_path, _ = run.conclusions["A9"]
    expected = "verified"
    if case == "changed_tree":
        target = run.root / "tests/read_support.py"
        target.write_bytes(target.read_bytes() + b"\n")
    elif case == "missing_a9":
        a9_path.unlink()
        expected = "material_unavailable"
    elif case == "tampered_a9":
        a9_path.write_text("{}")
        expected = "binding_mismatch"
    elif case in {"unknown_format", "boolean_format"}:
        value = json.loads(a9_path.read_bytes())
        value["format_version"] = 99 if case == "unknown_format" else True
        a9_path.write_text(json.dumps(value))
        next(
            group for group in terminal["groups"] if group["suffix"] == ".a9.json"
        ).update(sha256=file_sha256(a9_path), format_version=value["format_version"])
        path.write_text(json.dumps(terminal))
        expected = "unsupported_format"
    elif case == "missing_terminal":
        path.unlink()
        expected = "terminal_missing"
    elif case == "tampered_terminal":
        terminal["run_id"] = "historical"
        path.write_text(json.dumps(terminal))
        expected = "run_id_mismatch"
    elif case == "incomplete":
        terminal["interrupted"] = True
        path.write_text(json.dumps(terminal))
        expected = "interrupted"
    before = {p: p.read_bytes() for p in run.output_dir.iterdir()}
    report = query_status(run.root, run.output_dir, run.run_id)
    assert report["reason"] == expected
    if case in {"passed", "changed_tree"}:
        assert report["status"] == "passed"
        assert report["applicability"] == ("same" if case == "passed" else "different")
    else:
        assert report["status"] != "passed"
    assert before == {p: p.read_bytes() for p in run.output_dir.iterdir()}
