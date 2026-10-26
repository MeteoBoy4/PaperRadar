"""A10 的独立同次验收协议, 不把合成回执当实际执行。"""

from pathlib import Path


def test_a10_is_required_with_exact_direct_dependencies() -> None:
    from scripts.a2_full_acceptance import acceptance_groups

    groups = {group.name: group for group in acceptance_groups()}
    assert "A10" in groups
    assert groups["A10"].required is True
    assert groups["A2-01"].required is False
    assert groups["A10"].suffix == ".a10.json"
    assert groups["A10"].dependencies == ("A1", "完整 A2", "A3", "A6")
    assert all(
        groups[name].required
        for name in ("A1", "完整 A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9")
    )


def test_real_receipt_records_a10_modules(tmp_path: Path) -> None:
    from scripts.a2_test_receipt import TestReceipt
    from scripts.a10_scope import REQUIRED_TEST_CASE_COUNTS

    receipt = TestReceipt(tmp_path / "receipt.json", "same-run")
    assert set(REQUIRED_TEST_CASE_COUNTS) <= receipt.modules.keys()


def test_real_pytest_plugin_records_execution_and_rejects_short_scope(
    tmp_path: Path,
) -> None:
    import json
    import os
    import subprocess
    import sys

    from scripts.a10_scope import REQUIRED_TEST_CASE_COUNTS
    from scripts.verification_checks import receipt_records

    target = tmp_path / "real.pytest.json"
    environment = dict(os.environ)
    environment.pop("PYTEST_ADDOPTS", None)
    environment.pop("PYTEST_PLUGINS", None)
    environment.update(
        PAPER_RADAR_TEST_RECEIPT=str(target),
        PAPER_RADAR_TEST_RUN_ID="actual-a10-subset",
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "scripts.a2_test_receipt",
            "tests/test_a10_acceptance.py::test_a10_is_required_with_exact_direct_dependencies",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        capture_output=True,
        check=False,
        timeout=60,
    )
    assert result.returncode == 0
    receipt = json.loads(target.read_bytes())
    assert receipt["completed"] is True and receipt["exit_code"] == 0
    assert receipt["modules"]["tests/test_a10_acceptance.py"] == dict(
        collected=1,
        passed=1,
        failed=0,
        skipped=0,
        deselected=0,
        incomplete=0,
    )
    assert any(
        row["result"] != "passed"
        for row in receipt_records(receipt["modules"], REQUIRED_TEST_CASE_COUNTS)
    )
