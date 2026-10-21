"""A4 同次材料及入口适配;历史 support 与业务判据保持各自身份。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts.a1_acceptance import capture_identity
from scripts.a3_acceptance import write_a3_conclusion
from scripts.offline_evidence import file_sha256
from scripts.verification_identity import RunIdentity
from tests import a3_acceptance_support

ROOT = Path(__file__).resolve().parents[1]
Inputs = tuple[
    Path, Path, dict[str, Any], Path, dict[str, Any], Path, dict[str, Any], RunIdentity
]


def passed_receipt(run_id: str) -> dict[str, Any]:
    from scripts.a4_scope import REQUIRED_TEST_CASE_COUNTS

    payload = a3_acceptance_support.passed_receipt(run_id)
    payload["modules"].update(
        {
            name: dict(
                collected=count,
                passed=count,
                failed=0,
                skipped=0,
                deselected=0,
                incomplete=0,
            )
            for name, count in REQUIRED_TEST_CASE_COUNTS.items()
        }
    )
    return payload


def fake_checks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    binary, log = a3_acceptance_support.fake_checks(tmp_path, monkeypatch)
    (tmp_path / "write_receipt.py").write_text(
        "import json, os\nfrom pathlib import Path\n"
        f"payload = {passed_receipt('fixture')!r}\n"
        'payload["run_id"] = os.environ["PAPER_RADAR_TEST_RUN_ID"]\n'
        'Path(os.environ["PAPER_RADAR_TEST_RECEIPT"]).write_text(json.dumps(payload))\n',
        encoding="utf-8",
    )
    return binary, log


def same_a4_run(tmp_path: Path, *, root: Path = ROOT) -> Inputs:
    evidence, a1_path, a1, full_path, full, baseline = (
        a3_acceptance_support.same_a3_run(tmp_path, root=root)
    )
    receipt = evidence.with_suffix(".pytest.json")
    receipt.write_text(json.dumps(passed_receipt(a1["run_id"])), encoding="utf-8")
    full["pytest_receipt_sha256"] = file_sha256(receipt)
    full_path.write_text(json.dumps(full), encoding="utf-8")
    a3_path, a3 = write_a3_conclusion(
        root,
        evidence,
        a1_path,
        a1,
        full_path,
        full,
        tmp_path,
        baseline,
        expected_run_id=a1["run_id"],
    )
    assert a3["status"] == "passed", a3["reasons"]
    return evidence, a1_path, a1, full_path, full, a3_path, a3, capture_identity(root)


def conclude(
    tmp_path: Path, inputs: Inputs, *, root: Path = ROOT, interrupted: bool = False
) -> tuple[Path, dict[str, Any]]:
    from scripts.a4_acceptance import write_a4_conclusion

    evidence, a1_path, a1, full_path, full, a3_path, a3, baseline = inputs
    return write_a4_conclusion(
        root,
        evidence,
        a1_path,
        a1,
        full_path,
        full,
        a3_path,
        a3,
        tmp_path,
        baseline,
        expected_run_id="synthetic-full-a2",
        interrupted=interrupted,
    )
