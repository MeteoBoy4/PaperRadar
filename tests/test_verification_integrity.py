"""完整公开入口继续拒绝实际执行不足与发布前回执替换。"""

from __future__ import annotations

import json
import os
import shlex
import sys
from pathlib import Path

import pytest

from scripts.a2_full_acceptance import run_full_verification
from tests.a2_full_support import repository_copy
from tests.a5_acceptance_support import fake_checks


@pytest.mark.parametrize("mode", ["collect_only", "deselected"])
def test_zero_pytest_exit_cannot_replace_actual_fixed_test_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    root = repository_copy(tmp_path / "repo")
    binary, log = fake_checks(tmp_path)
    uv = binary / "uv"
    invocation = (
        f"{shlex.quote(sys.executable)} "
        f"{shlex.quote(str(tmp_path / 'write_receipt.py'))}"
    )
    options = (
        "--collect-only"
        if mode == "collect_only"
        else "-k test_unselected_profile_is_savable_but_not_ready"
    )
    uv.write_text(
        uv.read_text(encoding="utf-8").replace(
            invocation,
            f"{shlex.quote(sys.executable)} -m pytest -q "
            f"-p scripts.a2_test_receipt {options}",
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("PATH", f"{binary}:{os.environ['PATH']}")
    monkeypatch.setenv("A2_TEST_CHECK_LOG", str(log))
    output = tmp_path / "runs"
    _, full = run_full_verification(root, output)
    evidence = json.loads((output / full["evidence_file"]).read_bytes())
    assert evidence["overall"] == "passed"
    assert full["status"] == "failed"
    assert not full["a2_verified"]
    assert "test_execution_not_passed" in {r["code"] for r in full["reasons"]}
    a4 = json.loads(next(output.glob("*.a4.json")).read_bytes())
    assert a4["status"] == "failed" and not a4["a4_verified"]
    assert "test_execution_not_passed" in {reason["code"] for reason in a4["reasons"]}
    a5 = json.loads(next(output.glob("*.a5.json")).read_bytes())
    assert a5["status"] == "failed" and not a5["a5_verified"]
    assert "test_execution_not_passed" in {reason["code"] for reason in a5["reasons"]}
    assert len(log.read_text(encoding="utf-8").splitlines()) == 6


def test_receipt_replacement_before_final_publication_cannot_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = repository_copy(tmp_path / "repo")
    binary, log = fake_checks(tmp_path)
    monkeypatch.setenv("PATH", f"{binary}:{os.environ['PATH']}")
    monkeypatch.setenv("A2_TEST_CHECK_LOG", str(log))
    output = tmp_path / "runs"
    original = Path.read_bytes
    reads = 0

    def replace_after_read(path: Path) -> bytes:
        nonlocal reads
        raw = original(path)
        if path.parent == output and path.name.endswith(".pytest.json"):
            reads += 1
            if reads == 2:
                path.write_bytes(b'{"secret":"PRIVATE_RECEIPT_MARKER"}')
        return raw

    monkeypatch.setattr(Path, "read_bytes", replace_after_read)
    path, full = run_full_verification(root, output)
    assert full["status"] == "failed"
    assert not full["a2_verified"]
    assert "binding_mismatch" in {r["code"] for r in full["reasons"]}
    assert "PRIVATE_RECEIPT_MARKER" not in path.read_text(encoding="utf-8")
