"""A3 入口适配;仅改临时回执脚本,保留历史 A2 support 原字节。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts.a1_acceptance import capture_identity
from scripts.a2_full_acceptance import write_full_a2_conclusion
from scripts.verification_identity import RunIdentity
from tests import a2_full_support
from tests.test_a2_full_acceptance import same_run

ROOT = Path(__file__).resolve().parents[1]


def passed_receipt(run_id: str) -> dict[str, Any]:
    from scripts.a3_scope import REQUIRED_TEST_CASE_COUNTS

    payload = a2_full_support.passed_receipt(run_id)
    modules = payload["modules"]
    assert isinstance(modules, dict)
    modules.update(
        {
            name: {
                "collected": count,
                "passed": count,
                "failed": 0,
                "skipped": 0,
                "deselected": 0,
                "incomplete": 0,
            }
            for name, count in REQUIRED_TEST_CASE_COUNTS.items()
        }
    )
    return payload


def fake_checks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    binary, log = a2_full_support.fake_checks(tmp_path, monkeypatch)
    (tmp_path / "write_receipt.py").write_text(
        "import json, os\nfrom pathlib import Path\n"
        f"payload = {passed_receipt('fixture')!r}\n"
        'payload["run_id"] = os.environ["PAPER_RADAR_TEST_RUN_ID"]\n'
        'Path(os.environ["PAPER_RADAR_TEST_RECEIPT"]).write_text(json.dumps(payload))\n',
        encoding="utf-8",
    )
    return binary, log


def same_a3_run(
    tmp_path: Path,
    *,
    root: Path = ROOT,
) -> tuple[Path, Path, dict[str, Any], Path, dict[str, Any], RunIdentity]:
    evidence, a1_path, a1 = same_run(tmp_path)
    identity = capture_identity(root)
    raw_evidence = json.loads(evidence.read_bytes())
    raw_evidence.update(code=identity.code, lockfile_sha256=identity.lockfile_sha256)
    evidence.write_text(json.dumps(raw_evidence), encoding="utf-8")
    from scripts.offline_evidence import file_sha256

    a1.update(
        issue=13,
        evidence_file=evidence.name,
        evidence_sha256=file_sha256(evidence),
        code=identity.code,
        worktree_sha256=identity.worktree_sha256,
        lockfile_sha256=identity.lockfile_sha256,
    )
    a1_path.write_text(json.dumps(a1), encoding="utf-8")
    evidence.with_suffix(".pytest.json").write_text(
        json.dumps(passed_receipt(a1["run_id"])), encoding="utf-8"
    )
    full_path, full = write_full_a2_conclusion(root, evidence, a1_path, a1, tmp_path)
    assert full["status"] == "passed", full["reasons"]
    return evidence, a1_path, a1, full_path, full, capture_identity(root)


def conclude(
    tmp_path: Path,
    inputs: tuple[Path, Path, dict[str, Any], Path, dict[str, Any], RunIdentity],
    *,
    root: Path = ROOT,
    interrupted: bool = False,
) -> tuple[Path, dict[str, Any]]:
    from scripts.a3_acceptance import write_a3_conclusion

    evidence, a1_path, a1, full_path, full, baseline = inputs
    return write_a3_conclusion(
        root,
        evidence,
        a1_path,
        a1,
        full_path,
        full,
        tmp_path,
        baseline,
        expected_run_id="synthetic-full-a2",
        interrupted=interrupted,
    )
