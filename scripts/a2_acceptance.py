"""从同一次离线证据导出独立的 Issue #16 A2-01 结论。"""

from __future__ import annotations

import importlib.metadata
import json
import os
import uuid
from enum import StrEnum
from pathlib import Path
from typing import Any

from scripts.a1_acceptance import capture_identity
from scripts.a2_scope import (
    ISSUE,
    MIGRATION_REVISION,
    NOT_IMPLEMENTED,
    REQUIRED_DEPENDENCIES,
    REQUIRED_SOURCE_MODULES,
    REQUIRED_TEST_MODULES,
    SCOPE,
    SNAPSHOT_FORMAT_VERSION,
)
from scripts.offline_evidence import default_checks, file_sha256


class A2ReasonCode(StrEnum):
    EVIDENCE_UNAVAILABLE = "evidence_unavailable"
    BINDING_MISMATCH = "binding_mismatch"
    A1_NOT_PASSED = "a1_not_passed"
    CHECK_NOT_PASSED = "check_not_passed"
    SCOPE_DRIFT = "scope_drift"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    MIGRATION_UNAVAILABLE = "migration_unavailable"
    FORMAT_DRIFT = "format_drift"
    IDENTITY_CHANGED = "identity_changed"


_REASON_HELP = {
    A2ReasonCode.EVIDENCE_UNAVAILABLE: "本次离线证据无法读取；请重跑完整入口。",
    A2ReasonCode.BINDING_MISMATCH: "A1 结论与同次证据不一致；请重跑完整入口。",
    A2ReasonCode.A1_NOT_PASSED: "本次 A1 结论未通过；请先修复其原因。",
    A2ReasonCode.CHECK_NOT_PASSED: "本次完整离线检查未全部通过；请查看证据。",
    A2ReasonCode.SCOPE_DRIFT: "A2 固定测试或源码缺失、字节漂移；请审查并更新范围清单。",
    A2ReasonCode.DEPENDENCY_UNAVAILABLE: "A2 依赖版本不可得；请检查锁定环境。",
    A2ReasonCode.MIGRATION_UNAVAILABLE: (
        "迁移 head 不符合 A2 固定范围；请检查迁移脚本。"
    ),
    A2ReasonCode.FORMAT_DRIFT: "快照格式版本不符合 A2 固定范围；请审查格式变更。",
    A2ReasonCode.IDENTITY_CHANGED: "HEAD、工作树或 lockfile 在检查期间变化；请重跑。",
}


def _reason(code: A2ReasonCode, item: str | None = None) -> dict[str, str]:
    return {
        "code": code.value,
        "message_zh": _REASON_HELP[code],
        **({"item": item} if item is not None else {}),
    }


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _scope_files(
    root: Path,
    required: tuple[tuple[str, str], ...],
    reasons: list[dict[str, str]],
) -> list[dict[str, str | None]]:
    result = []
    for relative, expected in required:
        actual = file_sha256(root / relative)
        matched = actual == expected
        result.append(
            {
                "path": relative,
                "expected_sha256": expected,
                "actual_sha256": actual,
                "result": "passed" if matched else "failed",
            }
        )
        if not matched:
            reasons.append(_reason(A2ReasonCode.SCOPE_DRIFT, relative))
    return result


def _dependency_versions(reasons: list[dict[str, str]]) -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for name in REQUIRED_DEPENDENCIES:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
            reasons.append(_reason(A2ReasonCode.DEPENDENCY_UNAVAILABLE, name))
    return versions


def _format_and_revision(
    reasons: list[dict[str, str]],
) -> tuple[int | None, str | None]:
    try:
        from paper_radar.config.compile import FORMAT_VERSION
    except ImportError:
        snapshot_format = None
    else:
        snapshot_format = FORMAT_VERSION
    if snapshot_format != SNAPSHOT_FORMAT_VERSION:
        reasons.append(_reason(A2ReasonCode.FORMAT_DRIFT))

    try:
        from paper_radar.storage.database import current_revision

        revision = current_revision()
    except Exception:
        revision = None
    if revision != MIGRATION_REVISION:
        reasons.append(_reason(A2ReasonCode.MIGRATION_UNAVAILABLE))
    return snapshot_format, revision


def write_a2_conclusion(
    root: Path,
    evidence_path: Path,
    a1_path: Path,
    a1_conclusion: dict[str, Any],
    output_dir: Path,
) -> tuple[Path, dict[str, Any]]:
    """A2 仅评估本票范围。结论绑定 A1 使用的同一份离线证据。"""
    reasons: list[dict[str, str]] = []
    run_id = a1_conclusion["run_id"]
    evidence = _load_json(evidence_path)
    evidence_hash = file_sha256(evidence_path)
    saved_a1 = _load_json(a1_path)
    a1_hash = file_sha256(a1_path)
    if evidence is None or evidence_hash is None:
        reasons.append(_reason(A2ReasonCode.EVIDENCE_UNAVAILABLE))
        evidence = {}
    if (
        saved_a1 != a1_conclusion
        or a1_hash is None
        or a1_path.name != f"{run_id}.a1.json"
        or evidence_path.name != f"{run_id}.json"
        or evidence.get("run_id") != run_id
        or a1_conclusion.get("evidence_sha256") != evidence_hash
    ):
        reasons.append(_reason(A2ReasonCode.BINDING_MISMATCH))
    if a1_conclusion.get("a1_verified") is not True:
        reasons.append(_reason(A2ReasonCode.A1_NOT_PASSED))
    checks = evidence.get("checks")
    expected_checks = [check.id for check in default_checks()]
    if (
        evidence.get("completed") is not True
        or evidence.get("overall") != "passed"
        or not isinstance(checks, list)
        or [item.get("id") if isinstance(item, dict) else None for item in checks]
        != expected_checks
        or any(
            not isinstance(item, dict)
            or item.get("status") != "passed"
            or item.get("reason") != "none"
            or item.get("exit_code") != 0
            for item in checks
        )
    ):
        reasons.append(_reason(A2ReasonCode.CHECK_NOT_PASSED))

    test_files = _scope_files(root, REQUIRED_TEST_MODULES, reasons)
    source_files = _scope_files(root, REQUIRED_SOURCE_MODULES, reasons)
    dependencies = _dependency_versions(reasons)
    snapshot_format, revision = _format_and_revision(reasons)
    current = capture_identity(root)
    if (
        current.code["commit"] is None
        or current.code["dirty"] is None
        or current.lockfile_sha256 is None
        or current.worktree_sha256 is None
        or evidence.get("code") != current.code
        or evidence.get("lockfile_sha256") != current.lockfile_sha256
        or a1_conclusion.get("code") != current.code
        or a1_conclusion.get("lockfile_sha256") != current.lockfile_sha256
        or a1_conclusion.get("worktree_sha256") != current.worktree_sha256
    ):
        reasons.append(_reason(A2ReasonCode.IDENTITY_CHANGED))

    status = "passed" if not reasons else "failed"
    if (
        a1_conclusion.get("status") == "incomplete"
        or evidence.get("overall") == "incomplete"
    ):
        status = "incomplete"
    result: dict[str, Any] = {
        "format_version": 1,
        "run_id": run_id,
        "scope": SCOPE,
        "issue": ISSUE,
        "evidence_file": evidence_path.name,
        "evidence_sha256": evidence_hash,
        "a1_conclusion_file": a1_path.name,
        "a1_conclusion_sha256": a1_hash,
        "required_checks": expected_checks,
        "required_test_modules": [
            {"path": path, "sha256": digest} for path, digest in REQUIRED_TEST_MODULES
        ],
        "required_source_modules": [
            {"path": path, "sha256": digest} for path, digest in REQUIRED_SOURCE_MODULES
        ],
        "test_modules": test_files,
        "source_modules": source_files,
        "environment": {
            "python": evidence.get("environment", {}).get("python")
            if isinstance(evidence.get("environment"), dict)
            else None,
            "dependencies": dependencies,
        },
        "migration_revision": revision,
        "snapshot_format_version": snapshot_format,
        "stage_projection_format_version": None,
        "calibration_baseline_format_version": None,
        "not_implemented": list(NOT_IMPLEMENTED),
        "code": current.code,
        "worktree_sha256": current.worktree_sha256,
        "lockfile_sha256": current.lockfile_sha256,
        "status": status,
        "a2_01_verified": status == "passed",
        "stage_a_verified": False,
        "reasons": reasons,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{run_id}.a2.json"
    temporary = output_dir / f".{run_id}.{uuid.uuid4().hex}.tmp"
    payload = (
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode()
    try:
        with temporary.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path, result
