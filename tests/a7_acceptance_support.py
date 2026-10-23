"""A7 同次绑定链;合成回执仅用于验证验收协议。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.offline_evidence import file_sha256
from scripts.verification_identity import RunIdentity, capture_identity
from tests import a6_acceptance_support

ROOT = Path(__file__).resolve().parents[1]
Inputs = tuple[
    Path,
    Path,
    dict[str, Any],
    Path,
    dict[str, Any],
    Path,
    dict[str, Any],
    Path,
    dict[str, Any],
    Path,
    dict[str, Any],
    RunIdentity,
]


def passed_receipt(run_id: str) -> dict[str, Any]:
    from scripts.a7_scope import REQUIRED_TEST_CASE_COUNTS

    payload = a6_acceptance_support.passed_receipt(run_id)
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


def rebind(inputs: Inputs) -> None:
    evidence, a1_path, a1, full_path, full, a3_path, a3, a5_path, a5, a6_path, a6, _ = (
        inputs
    )
    receipt = evidence.with_suffix(".pytest.json")
    a1["evidence_sha256"] = file_sha256(evidence)
    a1_path.write_text(json.dumps(a1))
    for path, value in ((full_path, full), (a3_path, a3), (a5_path, a5), (a6_path, a6)):
        value.update(
            evidence_sha256=file_sha256(evidence),
            a1_conclusion_sha256=file_sha256(a1_path),
            pytest_receipt_sha256=file_sha256(receipt),
        )
        if path != full_path:
            value["a2_full_conclusion_sha256"] = file_sha256(full_path)
        if path in (a5_path, a6_path):
            value["a3_conclusion_sha256"] = file_sha256(a3_path)
        if path == a6_path:
            value["a5_conclusion_sha256"] = file_sha256(a5_path)
        path.write_text(json.dumps(value))


def same_a7_run(tmp_path: Path, *, root: Path = ROOT) -> Inputs:
    from scripts.a6_acceptance import write_a6_conclusion

    base = a6_acceptance_support.same_a6_run(tmp_path, root=root)
    evidence, a1, baseline = base[0], base[2], base[-1]
    receipt = evidence.with_suffix(".pytest.json")
    receipt.write_text(json.dumps(passed_receipt(a1["run_id"])))
    a6_acceptance_support.rebind(base)
    a6_path, a6 = write_a6_conclusion(
        root, *base[:-1], tmp_path, baseline, expected_run_id=a1["run_id"]
    )
    assert a6["status"] == "passed", a6["reasons"]
    return (*base[:-1], a6_path, a6, capture_identity(root))


def conclude(
    tmp_path: Path, inputs: Inputs, *, root: Path = ROOT, interrupted: bool = False
) -> tuple[Path, dict[str, Any]]:
    from scripts.a7_acceptance import write_a7_conclusion

    return write_a7_conclusion(
        root,
        *inputs[:-1],
        tmp_path,
        inputs[-1],
        expected_run_id="synthetic-full-a2",
        interrupted=interrupted,
    )
