"""合成同次文件只用于验证 A9 接收协议,不冒称真实测试执行。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.offline_evidence import default_checks, file_sha256
from scripts.verification_identity import RunIdentity, capture_identity

ROOT = Path(__file__).resolve().parents[1]
Inputs = tuple[
    Path, Path, dict[str, Any], Path, dict[str, Any], Path, dict[str, Any], RunIdentity
]


def passed_receipt(run_id: str) -> dict[str, Any]:
    from scripts.a8_scope import REQUIRED_TEST_CASE_COUNTS as A8_COUNTS
    from scripts.a9_scope import REQUIRED_TEST_CASE_COUNTS
    from scripts.a10_scope import REQUIRED_TEST_CASE_COUNTS as A10_COUNTS
    from tests.a7_acceptance_support import passed_receipt as a7_receipt

    payload = a7_receipt(run_id)
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
            for name, count in {
                **A8_COUNTS,
                **REQUIRED_TEST_CASE_COUNTS,
                **A10_COUNTS,
            }.items()
        }
    )
    return payload


def rebind(inputs: Inputs) -> None:
    evidence, a1_path, a1, full_path, full, a3_path, a3, _ = inputs
    receipt = evidence.with_suffix(".pytest.json")
    a1["evidence_sha256"] = file_sha256(evidence)
    a1_path.write_text(json.dumps(a1))
    for path, value in ((full_path, full), (a3_path, a3)):
        value.update(
            evidence_sha256=file_sha256(evidence),
            a1_conclusion_sha256=file_sha256(a1_path),
            pytest_receipt_sha256=file_sha256(receipt),
        )
        if path == a3_path:
            value["a2_full_conclusion_sha256"] = file_sha256(full_path)
        path.write_text(json.dumps(value))


def same_a9_run(tmp_path: Path, *, root: Path = ROOT) -> Inputs:
    identity = capture_identity(root)
    run_id = "synthetic-a9"
    evidence = tmp_path / f"{run_id}.json"
    evidence.write_text(
        json.dumps(
            {
                "format_version": 1,
                "run_id": run_id,
                "scope": {
                    "issue": 12,
                    "claim": "implemented_offline_checks_only",
                    "full_a1_verified": False,
                    "stage_a_verified": False,
                },
                "completed": True,
                "overall": "passed",
                "code": identity.code,
                "lockfile_sha256": identity.lockfile_sha256,
                "checks": [
                    dict(id=check.id, status="passed", reason="none", exit_code=0)
                    for check in default_checks()
                ],
            }
        )
    )
    receipt = evidence.with_suffix(".pytest.json")
    receipt.write_text(json.dumps(passed_receipt(run_id)))
    a1_path = tmp_path / f"{run_id}.a1.json"
    full_path = tmp_path / f"{run_id}.a2-full.json"
    a3_path = tmp_path / f"{run_id}.a3.json"
    common = dict(
        run_id=run_id,
        status="passed",
        code=identity.code,
        worktree_sha256=identity.worktree_sha256,
        lockfile_sha256=identity.lockfile_sha256,
        evidence_file=evidence.name,
        evidence_sha256=file_sha256(evidence),
    )
    a1 = dict(
        common,
        format_version=1,
        scope="a1_screening_authoritative_contracts",
        issue=13,
        a1_verified=True,
    )
    full = dict(
        common,
        format_version=2,
        scope="a2_versioned_config_snapshots",
        issue=25,
        a2_verified=True,
        a1_conclusion_file=a1_path.name,
        pytest_receipt_file=receipt.name,
    )
    a3 = dict(
        common,
        format_version=1,
        scope="a3_artifact_backup_restore",
        issue=35,
        parent_issue=29,
        a3_verified=True,
        a1_conclusion_file=a1_path.name,
        a2_full_conclusion_file=full_path.name,
        pytest_receipt_file=receipt.name,
    )
    inputs = (evidence, a1_path, a1, full_path, full, a3_path, a3, identity)
    rebind(inputs)
    return inputs


def conclude(
    tmp_path: Path, inputs: Inputs, *, root: Path = ROOT, interrupted: bool = False
) -> tuple[Path, dict[str, Any]]:
    from scripts.a9_acceptance import write_a9_conclusion

    return write_a9_conclusion(
        root,
        *inputs[:-1],
        tmp_path,
        inputs[-1],
        expected_run_id="synthetic-a9",
        interrupted=interrupted,
    )
