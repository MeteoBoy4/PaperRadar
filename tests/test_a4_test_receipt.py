"""唯一 pytest 插件显式记录新增 A4 模块的实际执行。"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "mode", ["passed", "skipped", "deselected", "collect_only", "failed", "incomplete"]
)
def test_actual_a4_module_receipt_never_infers_execution_from_exit_zero(
    tmp_path: Path, mode: str
) -> None:
    root = Path(__file__).resolve().parents[1]
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    tests = tmp_path / "tests"
    tests.mkdir()
    body = (
        "raise KeyboardInterrupt"
        if mode == "incomplete"
        else "assert False, 'PRIVATE_BODY'"
        if mode == "failed"
        else "pass"
    )
    (tests / "test_pi_supply.py").write_text(
        "def test_first():\n    pass\n" + f"def test_second():\n    {body}\n",
        encoding="utf-8",
    )
    if mode == "skipped":
        (tmp_path / "conftest.py").write_text(
            "import pytest\ndef pytest_collection_modifyitems(items):\n"
            "    for item in items:\n"
            "        item.add_marker(pytest.mark.skip(reason='PRIVATE_REASON'))\n",
            encoding="utf-8",
        )
    receipt = tmp_path / "run.pytest.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "scripts.a2_test_receipt",
            *(
                ["-k", "first"]
                if mode == "deselected"
                else ["--collect-only"]
                if mode == "collect_only"
                else []
            ),
        ],
        cwd=tmp_path,
        env={
            **os.environ,
            "PYTHONPATH": str(root),
            "PAPER_RADAR_TEST_RUN_ID": "a4-fixture",
            "PAPER_RADAR_TEST_RECEIPT": str(receipt),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == (
        2 if mode == "incomplete" else 1 if mode == "failed" else 0
    ), result.stderr
    payload = json.loads(receipt.read_bytes())
    assert payload["run_id"] == "a4-fixture"
    assert payload["completed"] is (mode != "incomplete")
    assert payload["modules"]["tests/test_pi_supply.py"] == {
        "collected": 1 if mode == "deselected" else 2,
        "passed": 0
        if mode in {"collect_only", "skipped"}
        else 1
        if mode in {"failed", "incomplete", "deselected"}
        else 2,
        "failed": int(mode == "failed"),
        "skipped": 2 if mode == "skipped" else 0,
        "deselected": int(mode == "deselected"),
        "incomplete": 2 if mode == "collect_only" else int(mode == "incomplete"),
    }
    assert "PRIVATE" not in receipt.read_text()
