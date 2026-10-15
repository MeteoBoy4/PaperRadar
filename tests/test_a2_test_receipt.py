"""实际 pytest 进程回执只保留固定模块计数。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("mode", ["passed", "skipped", "deselected", "failed"])
def test_actual_test_receipt_records_execution_instead_of_only_process_exit(
    tmp_path: Path,
    mode: str,
) -> None:
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_config_service.py").write_text(
        "def test_first():\n    pass\n"
        "def test_second():\n    "
        + ("assert False, 'PRIVATE_PROMPT_SECRET'" if mode == "failed" else "pass")
        + "\n",
        encoding="utf-8",
    )
    if mode == "skipped":
        (tmp_path / "conftest.py").write_text(
            "import pytest\ndef pytest_collection_modifyitems(items):\n"
            "    for item in items:\n"
            "        item.add_marker(pytest.mark.skip(reason='PRIVATE_SECRET'))\n",
            encoding="utf-8",
        )
    receipt = tmp_path / "run.pytest.json"
    result = subprocess.run(
        (
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "scripts.a2_test_receipt",
            "-q",
            *(["-k", "first"] if mode == "deselected" else []),
        ),
        cwd=tmp_path,
        env={
            **os.environ,
            "PYTHONPATH": str(ROOT),
            "PAPER_RADAR_TEST_RUN_ID": "fixture-run",
            "PAPER_RADAR_TEST_RECEIPT": str(receipt),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == (1 if mode == "failed" else 0), result.stderr
    payload = json.loads(receipt.read_bytes())
    assert payload["run_id"] == "fixture-run"
    assert payload["completed"] is True
    record = payload["modules"]["tests/test_config_service.py"]
    assert record == {
        "collected": 1 if mode == "deselected" else 2,
        "passed": 0
        if mode == "skipped"
        else 1
        if mode in {"failed", "deselected"}
        else 2,
        "failed": int(mode == "failed"),
        "skipped": 2 if mode == "skipped" else 0,
        "deselected": int(mode == "deselected"),
        "incomplete": 0,
    }
    assert "PRIVATE" not in receipt.read_text(encoding="utf-8")
