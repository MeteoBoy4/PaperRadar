"""A2-01 独立结论复用同次证据并核对固定范围。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.a1_acceptance import capture_identity
from scripts.a2_acceptance import write_a2_conclusion
from scripts.offline_evidence import default_checks, file_sha256

ROOT = Path(__file__).resolve().parents[1]


def _same_run_inputs(tmp_path: Path) -> tuple[Path, Path, dict[str, Any]]:
    identity = capture_identity(ROOT)
    run_id = "synthetic-a2-run"
    evidence = {
        "run_id": run_id,
        "completed": True,
        "overall": "passed",
        "code": identity.code,
        "lockfile_sha256": identity.lockfile_sha256,
        "environment": {"python": "3.14.0"},
        "checks": [
            {"id": check.id, "status": "passed", "reason": "none", "exit_code": 0}
            for check in default_checks()
        ],
    }
    evidence_path = tmp_path / f"{run_id}.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    a1: dict[str, Any] = {
        "run_id": run_id,
        "status": "passed",
        "a1_verified": True,
        "evidence_sha256": file_sha256(evidence_path),
        "code": identity.code,
        "worktree_sha256": identity.worktree_sha256,
        "lockfile_sha256": identity.lockfile_sha256,
    }
    a1_path = tmp_path / f"{run_id}.a1.json"
    a1_path.write_text(json.dumps(a1), encoding="utf-8")
    return evidence_path, a1_path, a1


def test_a2_conclusion_binds_fixed_scope_and_same_run(tmp_path: Path) -> None:
    evidence_path, a1_path, a1 = _same_run_inputs(tmp_path)
    path, result = write_a2_conclusion(ROOT, evidence_path, a1_path, a1, tmp_path)
    assert result["status"] == "passed", result["reasons"]
    assert result["a2_01_verified"] is True
    assert result["evidence_sha256"] == a1["evidence_sha256"]
    assert result["migration_revision"] == "a201_profile_snapshot"
    assert result["snapshot_format_version"] == 1
    assert result["stage_projection_format_version"] is None
    assert json.loads(path.read_text(encoding="utf-8")) == result
    assert all(item["result"] == "passed" for item in result["test_modules"])
    assert all(item["result"] == "passed" for item in result["source_modules"])


def test_a2_conclusion_rejects_failed_a1(tmp_path: Path) -> None:
    evidence_path, a1_path, a1 = _same_run_inputs(tmp_path)
    a1["a1_verified"] = False
    a1["status"] = "failed"
    a1_path.write_text(json.dumps(a1), encoding="utf-8")
    _, result = write_a2_conclusion(ROOT, evidence_path, a1_path, a1, tmp_path)
    assert result["status"] == "failed"
    assert any(reason["code"] == "a1_not_passed" for reason in result["reasons"])


def test_a2_conclusion_rejects_changed_evidence(tmp_path: Path) -> None:
    evidence_path, a1_path, a1 = _same_run_inputs(tmp_path)
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    evidence["checks"][0]["status"] = "failed"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    _, result = write_a2_conclusion(ROOT, evidence_path, a1_path, a1, tmp_path)
    assert result["status"] == "failed"
    assert {reason["code"] for reason in result["reasons"]} >= {
        "binding_mismatch",
        "check_not_passed",
    }
