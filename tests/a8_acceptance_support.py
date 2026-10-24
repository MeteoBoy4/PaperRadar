"""A8 同次绑定链;合成回执只用于验证验收协议。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.offline_evidence import file_sha256
from scripts.verification_identity import RunIdentity, capture_identity
from tests import a7_acceptance_support

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
    Path,
    dict[str, Any],
    RunIdentity,
]


def passed_receipt(run_id: str) -> dict[str, Any]:
    from scripts.a8_scope import REQUIRED_TEST_CASE_COUNTS
    from scripts.a9_scope import REQUIRED_TEST_CASE_COUNTS as A9_COUNTS

    payload = a7_acceptance_support.passed_receipt(run_id)
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
            for name, count in {**REQUIRED_TEST_CASE_COUNTS, **A9_COUNTS}.items()
        }
    )
    return payload


def rebind(inputs: Inputs) -> None:
    base = (*inputs[:-3], inputs[-1])
    a7_acceptance_support.rebind(base)
    evidence = inputs[0]
    path, a7 = inputs[-3:-1]
    assert isinstance(path, Path) and isinstance(a7, dict)
    paths = {
        "evidence": evidence,
        "a1_conclusion": inputs[1],
        "a2_full_conclusion": inputs[3],
        "a3_conclusion": inputs[5],
        "a5_conclusion": inputs[7],
        "a6_conclusion": inputs[9],
        "pytest_receipt": evidence.with_suffix(".pytest.json"),
    }
    for label, source in paths.items():
        a7[label + "_sha256"] = file_sha256(source)
    path.write_text(json.dumps(a7))


def same_a8_run(tmp_path: Path, *, root: Path = ROOT) -> Inputs:
    from scripts.a7_acceptance import write_a7_conclusion

    base = a7_acceptance_support.same_a7_run(tmp_path, root=root)
    receipt = base[0].with_suffix(".pytest.json")
    receipt.write_text(json.dumps(passed_receipt(base[2]["run_id"])))
    a7_acceptance_support.rebind(base)
    path, a7 = write_a7_conclusion(
        root, *base[:-1], tmp_path, base[-1], expected_run_id=base[2]["run_id"]
    )
    assert a7["status"] == "passed", a7["reasons"]
    return (*base[:-1], path, a7, capture_identity(root))


def conclude(
    tmp_path: Path, inputs: Inputs, *, root: Path = ROOT, interrupted: bool = False
) -> tuple[Path, dict[str, Any]]:
    from scripts.a8_acceptance import write_a8_conclusion

    return write_a8_conclusion(
        root,
        *inputs[:-1],
        tmp_path,
        inputs[-1],
        expected_run_id="synthetic-full-a2",
        interrupted=interrupted,
    )
