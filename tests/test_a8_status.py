"""A8 由既有只读终态协议查询。"""

import json
from pathlib import Path

import pytest

from scripts.a2_full_acceptance import acceptance_groups
from scripts.offline_evidence import file_sha256
from scripts.verification_run import VerificationRun, run_verification
from scripts.verification_status import query_status
from tests.a2_full_support import fake_checks, repository_copy
from tests.a8_acceptance_support import passed_receipt


def test_status_recognizes_a8_without_changing_historical_formats() -> None:
    from scripts.verification_status import SUPPORTED_GROUP_FORMATS

    assert SUPPORTED_GROUP_FORMATS[".a8.json"] == (1,)
    assert SUPPORTED_GROUP_FORMATS[".a2-full.json"] == (2,)


@pytest.fixture
def a8_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> VerificationRun:
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
        "missing_a8",
        "tampered_a8",
        "unknown_format",
        "boolean_format",
        "missing_terminal",
        "tampered_terminal",
        "incomplete",
    ],
)
def test_status_requires_same_a8_bytes_and_terminal(
    a8_run: VerificationRun, case: str
) -> None:
    run = a8_run
    path = run.output_dir / f"{run.run_id}.terminal.json"
    terminal = json.loads(path.read_bytes())
    a8_path, _ = run.conclusions["A8"]
    expected = "verified"
    if case == "changed_tree":
        target = run.root / "tests/a8_rpc_support.py"
        target.write_bytes(target.read_bytes() + b"\n")
    elif case == "missing_a8":
        a8_path.unlink()
        expected = "material_unavailable"
    elif case == "tampered_a8":
        a8_path.write_text("{}")
        expected = "binding_mismatch"
    elif case in {"unknown_format", "boolean_format"}:
        value = json.loads(a8_path.read_bytes())
        value["format_version"] = 99 if case == "unknown_format" else True
        a8_path.write_text(json.dumps(value))
        next(
            group for group in terminal["groups"] if group["suffix"] == ".a8.json"
        ).update(sha256=file_sha256(a8_path), format_version=value["format_version"])
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
