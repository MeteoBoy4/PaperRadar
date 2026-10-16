"""同次制品、备份与隔离恢复验收;不继承依赖组的通过资格。"""

from __future__ import annotations

import importlib.metadata
import sqlite3
import sys
import tempfile
from enum import StrEnum
from pathlib import Path
from typing import Any

from scripts.a3_scope import (
    CAPABILITIES,
    FORMAT_VERSION,
    FORMAT_VERSIONS,
    ISSUE,
    MIGRATION_REVISION,
    NOT_ASSESSED,
    PARENT_ISSUE,
    REQUIRED_CHECKS,
    REQUIRED_DEPENDENCIES,
    REQUIRED_FIXTURE_FILES,
    REQUIRED_SOURCE_MODULES,
    REQUIRED_TEST_CASE_COUNTS,
    REQUIRED_TEST_MODULES,
    SCOPE,
    SUFFIX,
)
from scripts.offline_evidence import (
    CheckReason,
    CheckStatus,
    OverallStatus,
    file_sha256,
)
from scripts.verification_checks import (
    file_records,
    files_unchanged,
    identity_matches,
    read_json,
    receipt_completed,
    receipt_records,
    same_run_document,
)
from scripts.verification_identity import RunIdentity, capture_identity
from scripts.verification_publication import publish_conclusion
from scripts.verification_run import VerificationRun


class A3ReasonCode(StrEnum):
    EVIDENCE_UNAVAILABLE = "evidence_unavailable"
    BINDING_MISMATCH = "binding_mismatch"
    FORMAT_MISMATCH = "format_mismatch"
    PREREQUISITE_NOT_PASSED = "prerequisite_not_passed"
    CHECK_NOT_PASSED = "check_not_passed"
    SCOPE_DRIFT = "scope_drift"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    MIGRATION_UNAVAILABLE = "migration_unavailable"
    STORAGE_FORMAT_DRIFT = "storage_format_drift"
    IDENTITY_CHANGED = "identity_changed"
    RUN_INCOMPLETE = "run_incomplete"
    TEST_EXECUTION_NOT_PASSED = "test_execution_not_passed"


_HELP = {
    A3ReasonCode.EVIDENCE_UNAVAILABLE: ("本次证据无法读取；请重跑完整离线入口。"),
    A3ReasonCode.BINDING_MISMATCH: (
        "同次证据、前置结论或回执绑定不一致；请重跑完整离线入口。"
    ),
    A3ReasonCode.FORMAT_MISMATCH: (
        "证据、前置结论或回执格式不受支持；请核对版本后重跑。"
    ),
    A3ReasonCode.PREREQUISITE_NOT_PASSED: (
        "本次必需前置结论未通过；请先处理 A1 或完整 A2。"
    ),
    A3ReasonCode.CHECK_NOT_PASSED: ("固定离线检查缺失、失败或未执行；请查看本次证据。"),
    A3ReasonCode.SCOPE_DRIFT: ("A3 固定范围缺失或字节漂移；请逐项审查并显式登记。"),
    A3ReasonCode.DEPENDENCY_UNAVAILABLE: ("A3 实际依赖版本不可得；请修复锁定环境。"),
    A3ReasonCode.MIGRATION_UNAVAILABLE: (
        "真实临时库迁移失败或 head 未登记；请审查迁移范围。"
    ),
    A3ReasonCode.STORAGE_FORMAT_DRIFT: ("存储或备份格式漂移；请审查并显式版本化范围。"),
    A3ReasonCode.IDENTITY_CHANGED: (
        "运行期间代码、工作树或 lockfile 变化；请重跑完整入口。"
    ),
    A3ReasonCode.RUN_INCOMPLETE: ("本次运行中断或未完成；请重新执行完整入口。"),
    A3ReasonCode.TEST_EXECUTION_NOT_PASSED: (
        "本次 A3 固定用例未全部实际通过；请检查执行回执后重跑。"
    ),
}


def _reason(code: A3ReasonCode, item: str | None = None) -> dict[str, str]:
    return {
        "code": code.value,
        "message_zh": _HELP[code],
        **({"item": item} if item else {}),
    }


def _environment(reasons: list[dict[str, str]]) -> dict[str, Any]:
    versions: dict[str, str | None] = {}
    for name in REQUIRED_DEPENDENCIES:
        try:
            version = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            version = None
        versions[name] = (
            version if isinstance(version, str) and version.strip() else None
        )
        if versions[name] is None:
            reasons.append(_reason(A3ReasonCode.DEPENDENCY_UNAVAILABLE, name))
    return {
        "python": sys.version.split()[0],
        "sqlite": sqlite3.sqlite_version,
        "dependencies": versions,
    }


def _migrated_revision() -> str | None:
    from paper_radar.storage.database import (
        DatabaseMode,
        current_revision,
        open_database,
        upgrade_database,
    )

    with tempfile.TemporaryDirectory(prefix="paper-radar-a3-") as directory:
        database = Path(directory) / "acceptance.sqlite3"
        upgrade_database(database)
        engine = open_database(database, mode=DatabaseMode.READ_ONLY)
        try:
            with engine.connect() as connection:
                revisions = (
                    connection.exec_driver_sql(
                        "SELECT version_num FROM alembic_version"
                    )
                    .scalars()
                    .all()
                )
        finally:
            engine.dispose()
        if len(revisions) != 1 or revisions[0] != current_revision():
            return None
        return str(revisions[0])


def _formats() -> dict[str, Any]:
    from paper_radar.backup.manifest import (
        BACKUP_DATABASE_REVISION,
        BACKUP_FORMAT_VERSION,
    )
    from paper_radar.storage.artifact_contract import (
        ARTIFACT_FORMAT_VERSION,
        BLOB_LAYOUT_VERSION,
    )

    return {
        "artifact": ARTIFACT_FORMAT_VERSION,
        "blob_layout": BLOB_LAYOUT_VERSION,
        "backup": BACKUP_FORMAT_VERSION,
        "backup_database_revision": BACKUP_DATABASE_REVISION,
    }


def write_a3_conclusion(
    root: Path,
    evidence_path: Path,
    a1_path: Path,
    a1: dict[str, Any],
    full_a2_path: Path,
    full_a2: dict[str, Any],
    output_dir: Path,
    baseline: RunIdentity,
    *,
    expected_run_id: str,
    interrupted: bool = False,
) -> tuple[Path, dict[str, Any]]:
    """实际核对同次固定范围再只追加结论;不运行第二套完整检查。"""
    run_id = expected_run_id
    receipt_path = evidence_path.with_suffix(".pytest.json")
    reasons: list[dict[str, str]] = []
    result: dict[str, Any] = {
        "format_version": FORMAT_VERSION,
        "run_id": run_id,
        "scope": SCOPE,
        "parent_issue": PARENT_ISSUE,
        "issue": ISSUE,
        "status": "incomplete",
        "a3_verified": False,
        "stage_a_verified": False,
        "live_verified": False,
        "required_checks": list(REQUIRED_CHECKS),
        "test_modules": [],
        "source_modules": [],
        "fixture_files": [],
        "test_execution": [],
        "environment": None,
        "migration_revision": None,
        "format_versions": None,
        "code": None,
        "worktree_sha256": None,
        "lockfile_sha256": None,
        "not_assessed": list(NOT_ASSESSED),
        "reasons": reasons,
    }
    paths = {
        "evidence": evidence_path,
        "a1_conclusion": a1_path,
        "a2_full_conclusion": full_a2_path,
        "pytest_receipt": receipt_path,
    }
    for label, path in paths.items():
        result[label + "_file"] = path.name
        result[label + "_sha256"] = None
    try:
        for label, path in paths.items():
            result[label + "_sha256"] = file_sha256(path)
        evidence = read_json(evidence_path)
        if evidence is None:
            reasons.append(_reason(A3ReasonCode.EVIDENCE_UNAVAILABLE))
            evidence = {}
        if (
            not same_run_document(evidence_path, run_id, ".json", evidence)
            or not same_run_document(a1_path, run_id, ".a1.json", a1)
            or not same_run_document(full_a2_path, run_id, ".a2-full.json", full_a2)
            or a1.get("scope") != "a1_screening_authoritative_contracts"
            or a1.get("issue") != 13
            or full_a2.get("scope") != "a2_versioned_config_snapshots"
            or full_a2.get("issue") != 25
            or a1.get("evidence_file") != evidence_path.name
            or full_a2.get("evidence_file") != evidence_path.name
            or a1.get("evidence_sha256") != result["evidence_sha256"]
            or full_a2.get("evidence_sha256") != result["evidence_sha256"]
            or full_a2.get("a1_conclusion_file") != a1_path.name
            or full_a2.get("a1_conclusion_sha256") != result["a1_conclusion_sha256"]
            or full_a2.get("pytest_receipt_file") != receipt_path.name
            or full_a2.get("pytest_receipt_sha256") != result["pytest_receipt_sha256"]
            or not isinstance(evidence.get("scope"), dict)
            or any(
                evidence["scope"].get(key) != value
                for key, value in {
                    "issue": 12,
                    "claim": "implemented_offline_checks_only",
                    "full_a1_verified": False,
                    "stage_a_verified": False,
                }.items()
            )
        ):
            reasons.append(_reason(A3ReasonCode.BINDING_MISMATCH))
        if any(
            type(value.get("format_version")) is not int
            or value.get("format_version") != expected
            for value, expected in ((evidence, 1), (a1, 1), (full_a2, 2))
        ):
            reasons.append(_reason(A3ReasonCode.FORMAT_MISMATCH))
        for label, value, verified in (
            ("A1", a1, "a1_verified"),
            ("完整 A2", full_a2, "a2_verified"),
        ):
            if value.get("status") != "passed" or value.get(verified) is not True:
                reasons.append(_reason(A3ReasonCode.PREREQUISITE_NOT_PASSED, label))
        checks = evidence.get("checks")
        if (
            evidence.get("completed") is not True
            or evidence.get("overall") != "passed"
            or not isinstance(checks, list)
            or [item.get("id") if isinstance(item, dict) else None for item in checks]
            != list(REQUIRED_CHECKS)
            or any(
                not isinstance(item, dict)
                or item.get("status") != "passed"
                or item.get("reason") != CheckReason.NONE
                or type(item.get("exit_code")) is not int
                or item.get("exit_code") != 0
                for item in checks
            )
        ):
            reasons.append(_reason(A3ReasonCode.CHECK_NOT_PASSED))
        if (
            evidence.get("completed") is False
            or evidence.get("overall") == "incomplete"
            or any(value.get("status") == "incomplete" for value in (a1, full_a2))
        ):
            reasons.append(_reason(A3ReasonCode.RUN_INCOMPLETE))
        for key, required in (
            ("test_modules", REQUIRED_TEST_MODULES),
            ("source_modules", REQUIRED_SOURCE_MODULES),
            ("fixture_files", REQUIRED_FIXTURE_FILES),
        ):
            result[key] = file_records(root, required)
            if not required:
                reasons.append(_reason(A3ReasonCode.SCOPE_DRIFT))
            for record in result[key]:
                if record["result"] != CheckStatus.PASSED:
                    reasons.append(_reason(A3ReasonCode.SCOPE_DRIFT, record["path"]))
        receipt = read_json(receipt_path)
        if receipt is None or not receipt_completed(receipt, run_id):
            reasons.append(_reason(A3ReasonCode.TEST_EXECUTION_NOT_PASSED))
        if receipt is not None and (
            type(receipt.get("format_version")) is not int
            or receipt.get("format_version") != 1
        ):
            reasons.append(_reason(A3ReasonCode.FORMAT_MISMATCH))
        if receipt is not None and receipt.get("completed") is False:
            reasons.append(_reason(A3ReasonCode.RUN_INCOMPLETE))
        if set(REQUIRED_TEST_CASE_COUNTS) != {
            name for name, _ in REQUIRED_TEST_MODULES
        }:
            reasons.append(_reason(A3ReasonCode.SCOPE_DRIFT))
        modules = receipt.get("modules") if receipt is not None else None
        if receipt is not None:
            result["test_execution"] = receipt_records(
                modules if isinstance(modules, dict) else {}, REQUIRED_TEST_CASE_COUNTS
            )
            for record in result["test_execution"]:
                if record["result"] != CheckStatus.PASSED:
                    reasons.append(
                        _reason(A3ReasonCode.TEST_EXECUTION_NOT_PASSED, record["path"])
                    )
        result["environment"] = _environment(reasons)
        try:
            result["migration_revision"] = _migrated_revision()
        except Exception:
            reasons.append(_reason(A3ReasonCode.MIGRATION_UNAVAILABLE))
        else:
            if result["migration_revision"] != MIGRATION_REVISION:
                reasons.append(_reason(A3ReasonCode.MIGRATION_UNAVAILABLE))
        result["format_versions"] = _formats()
        if result["format_versions"] != FORMAT_VERSIONS:
            reasons.append(_reason(A3ReasonCode.STORAGE_FORMAT_DRIFT))
        current = capture_identity(root)
        result.update(
            code=current.code,
            worktree_sha256=current.worktree_sha256,
            lockfile_sha256=current.lockfile_sha256,
        )
        if current != baseline or not identity_matches(current, evidence, a1, full_a2):
            reasons.append(_reason(A3ReasonCode.IDENTITY_CHANGED))
        if (
            not files_unchanged(
                tuple(
                    (path, result[label + "_sha256"]) for label, path in paths.items()
                )
            )
            or read_json(a1_path) != a1
            or read_json(full_a2_path) != full_a2
        ):
            reasons.append(_reason(A3ReasonCode.BINDING_MISMATCH))
    except KeyboardInterrupt:
        interrupted = True
    if interrupted and not any(
        reason["code"] == A3ReasonCode.RUN_INCOMPLETE for reason in reasons
    ):
        reasons.append(_reason(A3ReasonCode.RUN_INCOMPLETE))
    status = OverallStatus.PASSED if not reasons else OverallStatus.FAILED
    if any(reason["code"] == A3ReasonCode.RUN_INCOMPLETE for reason in reasons):
        status = OverallStatus.INCOMPLETE
    result.update(
        status=status.value,
        a3_verified=status is OverallStatus.PASSED,
        capabilities=dict.fromkeys(CAPABILITIES, status.value),
    )
    return publish_conclusion(output_dir, run_id, SUFFIX, result), result


def write_group(run: VerificationRun, interrupted: bool) -> tuple[Path, dict[str, Any]]:
    a1_path, a1 = run.conclusions["A1"]
    full_path, full = run.conclusions["完整 A2"]
    return write_a3_conclusion(
        run.root,
        run.evidence_path,
        a1_path,
        a1,
        full_path,
        full,
        run.output_dir,
        run.baseline,
        expected_run_id=run.run_id,
        interrupted=interrupted,
    )
