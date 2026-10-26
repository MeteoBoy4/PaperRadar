"""A10 的可信终态格式与只读查询。"""

import json
from pathlib import Path

import pytest

from scripts.a2_full_acceptance import acceptance_groups
from scripts.offline_evidence import file_sha256
from scripts.verification_run import VerificationRun, run_verification
from scripts.verification_status import query_status
from tests.a2_full_support import fake_checks, repository_copy
from tests.a10_acceptance_support import passed_receipt


def test_a10_status_format_and_real_receipt_registration(tmp_path: Path) -> None:
    from scripts.a2_test_receipt import TestReceipt
    from scripts.a10_scope import REQUIRED_TEST_MODULES
    from scripts.verification_status import CHECK_IDS_V1, SUPPORTED_GROUP_FORMATS

    assert SUPPORTED_GROUP_FORMATS[".a10.json"] == (1,)
    assert SUPPORTED_GROUP_FORMATS[".a2-full.json"] == (2,)
    assert CHECK_IDS_V1 == ("lockfile", "format", "lint", "types", "tests", "contracts")
    receipt = TestReceipt(tmp_path / "receipt.json", "synthetic")
    assert {name for name, _ in REQUIRED_TEST_MODULES} <= receipt.modules.keys()


def test_status_recognizes_a10_without_changing_historical_formats() -> None:
    from scripts.verification_status import SUPPORTED_GROUP_FORMATS

    assert SUPPORTED_GROUP_FORMATS[".a10.json"] == (1,)
    assert SUPPORTED_GROUP_FORMATS[".a2-full.json"] == (2,)


@pytest.fixture
def a10_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> VerificationRun:
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
        "missing_a10",
        "tampered_a10",
        "unknown_format",
        "boolean_format",
        "missing_terminal",
        "tampered_terminal",
        "incomplete",
    ],
)
def test_status_requires_same_a10_bytes_and_terminal(
    a10_run: VerificationRun, case: str
) -> None:
    run = a10_run
    path = run.output_dir / f"{run.run_id}.terminal.json"
    terminal = json.loads(path.read_bytes())
    a10_path, _ = run.conclusions["A10"]
    expected = "verified"
    if case == "changed_tree":
        target = run.root / "tests/a10_recovery_reader.py"
        target.write_bytes(target.read_bytes() + b"\n")
    elif case == "missing_a10":
        a10_path.unlink()
        expected = "material_unavailable"
    elif case == "tampered_a10":
        a10_path.write_text("{}")
        expected = "binding_mismatch"
    elif case in {"unknown_format", "boolean_format"}:
        value = json.loads(a10_path.read_bytes())
        value["format_version"] = 99 if case == "unknown_format" else True
        a10_path.write_text(json.dumps(value))
        next(
            group for group in terminal["groups"] if group["suffix"] == ".a10.json"
        ).update(sha256=file_sha256(a10_path), format_version=value["format_version"])
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
        a10 = run.conclusions["A10"][1]
        assert a10["a10_verified"] is True
        assert all(
            a10[key] is False
            for key in ("stage_a_verified", "live_verified", "rpc_verified")
        )
        assert "four_journal_live_5_to_10" in a10["not_assessed"]
        assert "source_stability_stage_b_gate" in a10["not_assessed"]
        assert "body_pdf_docling" in a10["not_assessed"]
        assert report["status"] == "passed"
        assert report["applicability"] == ("same" if case == "passed" else "different")
    else:
        assert report["status"] != "passed"
    assert before == {p: p.read_bytes() for p in run.output_dir.iterdir()}
