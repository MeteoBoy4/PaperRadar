"""同次 论文事实底座验收;不继承前置组的通过资格。"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from pathlib import Path
from typing import Any

from scripts import a2_full_scope, a3_scope, a5_scope
from scripts.a6_scope import (
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
    environment_versions,
    file_records,
    files_unchanged,
    identity_matches,
    migrated_revision,
    read_json,
    receipt_completed,
    receipt_records,
    same_run_document,
)
from scripts.verification_identity import RunIdentity, capture_identity
from scripts.verification_publication import publish_conclusion
from scripts.verification_run import VerificationRun


class A6ReasonCode(StrEnum):
    EVIDENCE_UNAVAILABLE = "evidence_unavailable"
    BINDING_MISMATCH = "binding_mismatch"
    FORMAT_MISMATCH = "format_mismatch"
    PREREQUISITE_NOT_PASSED = "prerequisite_not_passed"
    CHECK_NOT_PASSED = "check_not_passed"
    SCOPE_DRIFT = "scope_drift"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    MIGRATION_UNAVAILABLE = "migration_unavailable"
    PAPER_FACT_FORMAT_DRIFT = "paper_fact_format_drift"
    IDENTITY_CHANGED = "identity_changed"
    RUN_INCOMPLETE = "run_incomplete"
    TEST_EXECUTION_NOT_PASSED = "test_execution_not_passed"


_HELP = {
    A6ReasonCode.EVIDENCE_UNAVAILABLE: ("本次证据无法读取；请重跑完整离线入口。"),
    A6ReasonCode.BINDING_MISMATCH: (
        "同次证据、前置结论或回执绑定不一致；请重跑完整离线入口。"
    ),
    A6ReasonCode.FORMAT_MISMATCH: (
        "证据、前置结论或回执格式不受支持；请核对版本后重跑。"
    ),
    A6ReasonCode.PREREQUISITE_NOT_PASSED: (
        "本次必需前置结论未通过；请先处理 A1、完整 A2、A3 或 A5。"
    ),
    A6ReasonCode.CHECK_NOT_PASSED: ("固定离线检查缺失、失败或未执行；请查看本次证据。"),
    A6ReasonCode.SCOPE_DRIFT: ("A6 固定范围缺失或字节漂移；请逐项审查并显式登记。"),
    A6ReasonCode.DEPENDENCY_UNAVAILABLE: ("A6 实际依赖版本不可得；请修复锁定环境。"),
    A6ReasonCode.MIGRATION_UNAVAILABLE: (
        "真实临时库迁移失败或 head 未登记；请审查迁移范围。"
    ),
    A6ReasonCode.PAPER_FACT_FORMAT_DRIFT: (
        "论文事实或输入格式漂移；请审查并显式版本化范围。"
    ),
    A6ReasonCode.IDENTITY_CHANGED: (
        "运行期间代码、工作树或 lockfile 变化；请重跑完整入口。"
    ),
    A6ReasonCode.RUN_INCOMPLETE: ("本次运行中断或未完成；请重新执行完整入口。"),
    A6ReasonCode.TEST_EXECUTION_NOT_PASSED: (
        "本次 A6 固定用例未全部实际通过；请检查执行回执后重跑。"
    ),
}


def _reason(code: A6ReasonCode, item: str | None = None) -> dict[str, str]:
    return {
        "code": code.value,
        "message_zh": _HELP[code],
        **({"item": item} if item else {}),
    }


def _environment(reasons: list[dict[str, str]]) -> dict[str, Any]:
    environment = environment_versions(REQUIRED_DEPENDENCIES)
    for name, version in environment["dependencies"].items():
        if version is None:
            reasons.append(_reason(A6ReasonCode.DEPENDENCY_UNAVAILABLE, name))
    return environment


def _formats() -> dict[str, Any]:
    from paper_radar.backup.manifest import BACKUP_FORMAT_VERSION
    from paper_radar.config import StageName
    from paper_radar.papers.doi import DOI_RULES_VERSION
    from paper_radar.papers.errors import REASON_CATALOG_VERSION
    from paper_radar.papers.feed import FEED_ITEM_FINGERPRINT_VERSION
    from paper_radar.papers.models import PAPER_FACTS_VERSION, TEXT_NORM_VERSION
    from paper_radar.stage_inputs import STAGE_INPUT_FORMAT_VERSIONS

    return {
        "paper_facts": PAPER_FACTS_VERSION,
        "doi_rules": DOI_RULES_VERSION,
        "text_norm": TEXT_NORM_VERSION,
        "feed_item_fingerprint": FEED_ITEM_FINGERPRINT_VERSION,
        "reason_catalog": REASON_CATALOG_VERSION,
        "stage_inputs": {
            stage.value: STAGE_INPUT_FORMAT_VERSIONS[stage]
            for stage in (StageName.BOUNDARY, StageName.VALUE)
        },
        "backup": BACKUP_FORMAT_VERSION,
    }


def _capability_materials(root: Path) -> dict[str, Any] | None:
    # 只解析本组已冻结的精确字节; 漂移材料不能进入失败结论。
    relative = "tests/fixtures/a6_capabilities.json"
    expected = dict(REQUIRED_FIXTURE_FILES).get(relative)
    try:
        raw = (root / relative).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            return None
        value = json.loads(raw)
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _same_formats(actual: object, expected: object) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return (
            isinstance(actual, dict)
            and actual.keys() == expected.keys()
            and all(
                _same_formats(actual[key], value) for key, value in expected.items()
            )
        )
    return actual == expected


def _code_well_typed(code: object) -> bool:
    return (
        isinstance(code, dict)
        and set(code) == {"commit", "dirty"}
        and isinstance(code.get("commit"), str)
        and bool(code["commit"])
        and type(code.get("dirty")) is bool
    )


def write_a6_conclusion(
    root: Path,
    evidence_path: Path,
    a1_path: Path,
    a1: dict[str, Any],
    full_a2_path: Path,
    full_a2: dict[str, Any],
    a3_path: Path,
    a3: dict[str, Any],
    a5_path: Path,
    a5: dict[str, Any],
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
        "a6_verified": False,
        "stage_a_verified": False,
        "live_verified": False,
        "rpc_verified": False,
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
        "a3_conclusion": a3_path,
        "a5_conclusion": a5_path,
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
            reasons.append(_reason(A6ReasonCode.EVIDENCE_UNAVAILABLE))
            evidence = {}
        if (
            not same_run_document(evidence_path, run_id, ".json", evidence)
            or not same_run_document(a1_path, run_id, ".a1.json", a1)
            or not same_run_document(full_a2_path, run_id, ".a2-full.json", full_a2)
            or not same_run_document(a3_path, run_id, ".a3.json", a3)
            or not same_run_document(a5_path, run_id, ".a5.json", a5)
            or a5.get("scope") != a5_scope.SCOPE
            or type(a5.get("issue")) is not int
            or a5.get("issue") != a5_scope.ISSUE
            or type(a5.get("parent_issue")) is not int
            or a5.get("parent_issue") != a5_scope.PARENT_ISSUE
            or any(
                a5.get(label + "_file") != paths[label].name
                or a5.get(label + "_sha256") != result[label + "_sha256"]
                for label in (
                    "evidence",
                    "a1_conclusion",
                    "a2_full_conclusion",
                    "a3_conclusion",
                    "pytest_receipt",
                )
            )
            or a3.get("scope") != a3_scope.SCOPE
            or a3.get("issue") != a3_scope.ISSUE
            or a3.get("parent_issue") != a3_scope.PARENT_ISSUE
            or a1.get("scope") != "a1_screening_authoritative_contracts"
            or a1.get("issue") != 13
            or full_a2.get("scope") != a2_full_scope.SCOPE
            or full_a2.get("issue") != a2_full_scope.ISSUE
            or a1.get("evidence_file") != evidence_path.name
            or full_a2.get("evidence_file") != evidence_path.name
            or a1.get("evidence_sha256") != result["evidence_sha256"]
            or full_a2.get("evidence_sha256") != result["evidence_sha256"]
            or full_a2.get("a1_conclusion_file") != a1_path.name
            or full_a2.get("a1_conclusion_sha256") != result["a1_conclusion_sha256"]
            or full_a2.get("pytest_receipt_file") != receipt_path.name
            or full_a2.get("pytest_receipt_sha256") != result["pytest_receipt_sha256"]
            or any(
                a3.get(label + "_file") != paths[label].name
                or a3.get(label + "_sha256") != result[label + "_sha256"]
                for label in (
                    "evidence",
                    "a1_conclusion",
                    "a2_full_conclusion",
                    "pytest_receipt",
                )
            )
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
            or any(
                evidence["scope"].get(key) is not False
                for key in ("full_a1_verified", "stage_a_verified")
            )
        ):
            reasons.append(_reason(A6ReasonCode.BINDING_MISMATCH))
        if any(
            type(value.get("format_version")) is not int
            or value.get("format_version") != expected
            for value, expected in (
                (evidence, 1),
                (a1, 1),
                (full_a2, 2),
                (a3, 1),
                (a5, 1),
            )
        ):
            reasons.append(_reason(A6ReasonCode.FORMAT_MISMATCH))
        for label, value, verified in (
            ("A1", a1, "a1_verified"),
            ("完整 A2", full_a2, "a2_verified"),
            ("A3", a3, "a3_verified"),
            ("A5", a5, "a5_verified"),
        ):
            if value.get("status") != "passed" or value.get(verified) is not True:
                reasons.append(_reason(A6ReasonCode.PREREQUISITE_NOT_PASSED, label))
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
            reasons.append(_reason(A6ReasonCode.CHECK_NOT_PASSED))
        if (
            evidence.get("completed") is False
            or evidence.get("overall") == "incomplete"
            or any(
                value.get("status") == "incomplete" for value in (a1, full_a2, a3, a5)
            )
        ):
            reasons.append(_reason(A6ReasonCode.RUN_INCOMPLETE))
        for key, required in (
            ("test_modules", REQUIRED_TEST_MODULES),
            ("source_modules", REQUIRED_SOURCE_MODULES),
            ("fixture_files", REQUIRED_FIXTURE_FILES),
        ):
            result[key] = file_records(root, required)
            if not required:
                reasons.append(_reason(A6ReasonCode.SCOPE_DRIFT))
            for record in result[key]:
                if record["result"] != CheckStatus.PASSED:
                    reasons.append(_reason(A6ReasonCode.SCOPE_DRIFT, record["path"]))
        receipt = read_json(receipt_path)
        if receipt is None or not receipt_completed(receipt, run_id):
            reasons.append(_reason(A6ReasonCode.TEST_EXECUTION_NOT_PASSED))
        if receipt is not None and (
            type(receipt.get("format_version")) is not int
            or receipt.get("format_version") != 1
        ):
            reasons.append(_reason(A6ReasonCode.FORMAT_MISMATCH))
        if receipt is not None and receipt.get("completed") is False:
            reasons.append(_reason(A6ReasonCode.RUN_INCOMPLETE))
        if set(REQUIRED_TEST_CASE_COUNTS) != {
            name for name, _ in REQUIRED_TEST_MODULES
        }:
            reasons.append(_reason(A6ReasonCode.SCOPE_DRIFT))
        modules = receipt.get("modules") if receipt is not None else None
        if receipt is not None:
            result["test_execution"] = receipt_records(
                modules if isinstance(modules, dict) else {}, REQUIRED_TEST_CASE_COUNTS
            )
            for record in result["test_execution"]:
                if record["result"] != CheckStatus.PASSED:
                    reasons.append(
                        _reason(A6ReasonCode.TEST_EXECUTION_NOT_PASSED, record["path"])
                    )
        capability_evidence = _capability_materials(root)
        result["capability_evidence"] = capability_evidence
        fixed_paths = {
            name
            for name, _ in (
                *REQUIRED_TEST_MODULES,
                *REQUIRED_SOURCE_MODULES,
                *REQUIRED_FIXTURE_FILES,
            )
        }
        if (
            not isinstance(capability_evidence, dict)
            or set(capability_evidence) != set(CAPABILITIES)
            or any(
                not isinstance(material, dict)
                or not material.get("cases")
                or not material.get("materials")
                or any(
                    not isinstance(case, str)
                    or case.split("::", 1)[0] not in REQUIRED_TEST_CASE_COUNTS
                    for case in material["cases"]
                )
                or any(path not in fixed_paths for path in material["materials"])
                for material in capability_evidence.values()
            )
        ):
            reasons.append(_reason(A6ReasonCode.SCOPE_DRIFT))
        result["environment"] = _environment(reasons)
        try:
            result["migration_revision"] = migrated_revision(
                temp_prefix="paper-radar-a6-"
            )
        except Exception:
            reasons.append(_reason(A6ReasonCode.MIGRATION_UNAVAILABLE))
        else:
            if result["migration_revision"] != MIGRATION_REVISION:
                reasons.append(_reason(A6ReasonCode.MIGRATION_UNAVAILABLE))
        try:
            formats = _formats()
        except Exception:
            formats = {}
        result["format_versions"] = formats
        if not _same_formats(formats, FORMAT_VERSIONS):
            reasons.append(_reason(A6ReasonCode.PAPER_FACT_FORMAT_DRIFT))
        current = capture_identity(root)
        result.update(
            code=current.code,
            worktree_sha256=current.worktree_sha256,
            lockfile_sha256=current.lockfile_sha256,
        )
        if (
            current != baseline
            or not identity_matches(current, evidence, a1, full_a2, a3, a5)
            or any(
                not _code_well_typed(code)
                for code in (
                    current.code,
                    baseline.code,
                    evidence.get("code"),
                    a1.get("code"),
                    full_a2.get("code"),
                    a3.get("code"),
                    a5.get("code"),
                )
            )
        ):
            reasons.append(_reason(A6ReasonCode.IDENTITY_CHANGED))
        if (
            not files_unchanged(
                tuple(
                    (path, result[label + "_sha256"]) for label, path in paths.items()
                )
            )
            or read_json(a1_path) != a1
            or read_json(full_a2_path) != full_a2
            or read_json(a3_path) != a3
            or read_json(a5_path) != a5
        ):
            reasons.append(_reason(A6ReasonCode.BINDING_MISMATCH))
    except KeyboardInterrupt:
        interrupted = True
    if interrupted and not any(
        reason["code"] == A6ReasonCode.RUN_INCOMPLETE for reason in reasons
    ):
        reasons.append(_reason(A6ReasonCode.RUN_INCOMPLETE))
    status = OverallStatus.PASSED if not reasons else OverallStatus.FAILED
    if any(reason["code"] == A6ReasonCode.RUN_INCOMPLETE for reason in reasons):
        status = OverallStatus.INCOMPLETE
    result.update(
        status=status.value,
        a6_verified=status is OverallStatus.PASSED,
        capabilities=dict.fromkeys(CAPABILITIES, status.value),
    )
    return publish_conclusion(output_dir, run_id, SUFFIX, result), result


def write_group(run: VerificationRun, interrupted: bool) -> tuple[Path, dict[str, Any]]:
    a1_path, a1 = run.conclusions["A1"]
    full_path, full = run.conclusions["完整 A2"]
    a3_path, a3 = run.conclusions["A3"]
    a5_path, a5 = run.conclusions["A5"]
    return write_a6_conclusion(
        run.root,
        run.evidence_path,
        a1_path,
        a1,
        full_path,
        full,
        a3_path,
        a3,
        a5_path,
        a5,
        run.output_dir,
        run.baseline,
        expected_run_id=run.run_id,
        interrupted=interrupted,
    )
