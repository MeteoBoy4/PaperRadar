"""fixture 注册、HTTP审计、回放与恢复的独立同次离线验收。"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from pathlib import Path
from typing import Any

from scripts import a2_full_scope, a3_scope, a6_scope
from scripts.a10_coverage import validate_coverage
from scripts.a10_scope import (
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
from scripts.offline_evidence import CheckStatus, OverallStatus, file_sha256
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


class A10ReasonCode(StrEnum):
    EVIDENCE_UNAVAILABLE = "evidence_unavailable"
    BINDING_MISMATCH = "binding_mismatch"
    FORMAT_MISMATCH = "format_mismatch"
    PREREQUISITE_NOT_PASSED = "prerequisite_not_passed"
    CHECK_NOT_PASSED = "check_not_passed"
    SCOPE_DRIFT = "scope_drift"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    MIGRATION_UNAVAILABLE = "migration_unavailable"
    AUDIT_FORMAT_DRIFT = "audit_format_drift"
    IDENTITY_CHANGED = "identity_changed"
    RUN_INCOMPLETE = "run_incomplete"
    TEST_EXECUTION_NOT_PASSED = "test_execution_not_passed"


_HELP = {
    A10ReasonCode.EVIDENCE_UNAVAILABLE: "本次证据无法读取；请重跑完整离线入口。",
    A10ReasonCode.BINDING_MISMATCH: (
        "同次证据、前置结论或回执绑定不一致；请重跑完整入口。"
    ),
    A10ReasonCode.FORMAT_MISMATCH: "证据、前置结论或回执格式不受支持；请核对版本。",
    A10ReasonCode.PREREQUISITE_NOT_PASSED: (
        "本次 A1、完整 A2、A3 或 A6 未通过；请先处理直接前置。"
    ),
    A10ReasonCode.CHECK_NOT_PASSED: "固定六项检查缺失、失败或未执行；请查看本次证据。",
    A10ReasonCode.SCOPE_DRIFT: "A10 固定范围或覆盖台账漂移；请逐项审查并显式登记。",
    A10ReasonCode.DEPENDENCY_UNAVAILABLE: "A10 实际依赖版本不可得；请修复锁定环境。",
    A10ReasonCode.MIGRATION_UNAVAILABLE: (
        "真实临时库迁移失败或 head 未登记；请审查迁移范围。"
    ),
    A10ReasonCode.AUDIT_FORMAT_DRIFT: (
        "审计策略、通道、解析或备份格式漂移；请显式审查规则身份。"
    ),
    A10ReasonCode.IDENTITY_CHANGED: (
        "运行期间代码、工作树或 lockfile 变化；请重跑完整入口。"
    ),
    A10ReasonCode.RUN_INCOMPLETE: "本次运行中断或未完成；请重跑完整入口。",
    A10ReasonCode.TEST_EXECUTION_NOT_PASSED: (
        "本次 A10 固定用例未全部实际通过；请查看执行回执。"
    ),
}


def _reason(code: A10ReasonCode, item: str | None = None) -> dict[str, str]:
    return {
        "code": code.value,
        "message_zh": _HELP[code],
        **({"item": item} if item else {}),
    }


def _formats() -> dict[str, Any]:
    from typing import get_args

    from paper_radar.backup.manifest import BACKUP_FORMAT_VERSION
    from paper_radar.fixture_audit import abstract_models as abstract
    from paper_radar.fixture_audit import acquisition_models as acquisition
    from paper_radar.fixture_audit.models import DECLARATION_FORMAT_VERSION
    from paper_radar.papers.doi import DOI_RULES_VERSION
    from paper_radar.papers.models import TEXT_NORM_VERSION

    return {
        "registration": DECLARATION_FORMAT_VERSION,
        "acquisition_strategy": acquisition.ACQUISITION_STRATEGY_VERSION,
        "channels": acquisition.CHANNELS_VERSION,
        "channel_values": list(get_args(acquisition.Channel)),
        "http": acquisition.HTTP_RULES_VERSION,
        "parser": acquisition.PARSER_VERSION,
        "ua_template": acquisition.UA_TEMPLATE_VERSION,
        "sampling": acquisition.SAMPLING_RULES_VERSION,
        "category": acquisition.CATEGORY_RULES_VERSION,
        "abstract": abstract.ABSTRACT_RULES_VERSION,
        "truncation": abstract.TRUNCATION_RULES_VERSION,
        "matrix": abstract.MATRIX_RULES_VERSION,
        "doi_rules": DOI_RULES_VERSION,
        "text_norm": TEXT_NORM_VERSION,
        "backup": BACKUP_FORMAT_VERSION,
    }


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


def _fixed_json(root: Path, relative: str) -> dict[str, Any] | None:
    try:
        raw = (root / relative).read_bytes()
        if hashlib.sha256(raw).hexdigest() != dict(REQUIRED_FIXTURE_FILES).get(
            relative
        ):
            return None
        value = json.loads(raw)
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _coverage(root: Path) -> dict[str, Any] | None:
    # 台账先由规格独立审阅;运行只验证冻结材料及覆盖引用,不生成期望。
    value = _fixed_json(root, "tests/fixtures/a10_coverage.json")
    if value is None or not validate_coverage(
        root,
        value,
        fixed={
            path
            for path, _ in (
                *REQUIRED_TEST_MODULES,
                *REQUIRED_SOURCE_MODULES,
                *REQUIRED_FIXTURE_FILES,
            )
        },
        test_modules=set(REQUIRED_TEST_CASE_COUNTS),
        capabilities=set(CAPABILITIES),
    ):
        return None
    return value


def write_a10_conclusion(
    root: Path,
    evidence_path: Path,
    a1_path: Path,
    a1: dict[str, Any],
    full_a2_path: Path,
    full_a2: dict[str, Any],
    a3_path: Path,
    a3: dict[str, Any],
    a6_path: Path,
    a6: dict[str, Any],
    output_dir: Path,
    baseline: RunIdentity,
    *,
    expected_run_id: str,
    interrupted: bool = False,
) -> tuple[Path, dict[str, Any]]:
    """核对同次实际材料再不可覆盖发布;不继承任何历史通过。"""
    run_id = expected_run_id
    receipt_path = evidence_path.with_suffix(".pytest.json")
    reasons: list[dict[str, str]] = []
    result: dict[str, Any] = dict(
        format_version=FORMAT_VERSION,
        run_id=run_id,
        scope=SCOPE,
        issue=ISSUE,
        parent_issue=PARENT_ISSUE,
        status="incomplete",
        a10_verified=False,
        stage_a_verified=False,
        live_verified=False,
        rpc_verified=False,
        required_checks=list(REQUIRED_CHECKS),
        test_modules=[],
        source_modules=[],
        fixture_files=[],
        test_execution=[],
        environment=None,
        migration_revision=None,
        format_versions=None,
        code=None,
        worktree_sha256=None,
        lockfile_sha256=None,
        not_assessed=list(NOT_ASSESSED),
        reasons=reasons,
        direct_dependencies=["A1", "完整 A2", "A3", "A6"],
        dependency_rationale=(
            "直接消费契约、配置、恢复与A6纯规则；其他required组仍决定总门禁。"
        ),
    )
    paths = {
        "evidence": evidence_path,
        "a1_conclusion": a1_path,
        "a2_full_conclusion": full_a2_path,
        "a3_conclusion": a3_path,
        "a6_conclusion": a6_path,
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
            reasons.append(_reason(A10ReasonCode.EVIDENCE_UNAVAILABLE))
            evidence = {}
        predecessors = (
            (
                "A1",
                a1_path,
                a1,
                ".a1.json",
                "a1_screening_authoritative_contracts",
                13,
                1,
                "a1_verified",
            ),
            (
                "完整 A2",
                full_a2_path,
                full_a2,
                ".a2-full.json",
                a2_full_scope.SCOPE,
                a2_full_scope.ISSUE,
                a2_full_scope.FORMAT_VERSION,
                "a2_verified",
            ),
            (
                "A3",
                a3_path,
                a3,
                ".a3.json",
                a3_scope.SCOPE,
                a3_scope.ISSUE,
                1,
                "a3_verified",
            ),
            (
                "A6",
                a6_path,
                a6,
                ".a6.json",
                a6_scope.SCOPE,
                a6_scope.ISSUE,
                a6_scope.FORMAT_VERSION,
                "a6_verified",
            ),
        )
        if not same_run_document(evidence_path, run_id, ".json", evidence):
            reasons.append(_reason(A10ReasonCode.BINDING_MISMATCH))
        for label, path, value, suffix, scope, issue, version, verified in predecessors:
            if (
                not same_run_document(path, run_id, suffix, value)
                or value.get("scope") != scope
                or type(value.get("issue")) is not int
                or value.get("issue") != issue
            ):
                reasons.append(_reason(A10ReasonCode.BINDING_MISMATCH, label))
            if (
                type(value.get("format_version")) is not int
                or value.get("format_version") != version
            ):
                reasons.append(_reason(A10ReasonCode.FORMAT_MISMATCH, label))
            if value.get("status") != "passed" or value.get(verified) is not True:
                reasons.append(_reason(A10ReasonCode.PREREQUISITE_NOT_PASSED, label))
            bindings = ["evidence"]
            if label != "A1":
                bindings.extend(("a1_conclusion", "pytest_receipt"))
            if label in ("A3", "A6"):
                bindings.append("a2_full_conclusion")
                if type(value.get("parent_issue")) is not int or value.get(
                    "parent_issue"
                ) != (
                    a3_scope.PARENT_ISSUE if label == "A3" else a6_scope.PARENT_ISSUE
                ):
                    reasons.append(_reason(A10ReasonCode.BINDING_MISMATCH, label))
            if label == "A6":
                bindings.append("a3_conclusion")
            if any(
                value.get(binding + "_file") != paths[binding].name
                or value.get(binding + "_sha256") != result[binding + "_sha256"]
                for binding in bindings
            ):
                reasons.append(_reason(A10ReasonCode.BINDING_MISMATCH, label))
        evidence_scope = evidence.get("scope")
        if (
            not isinstance(evidence_scope, dict)
            or type(evidence_scope.get("issue")) is not int
            or evidence_scope.get("issue") != 12
            or evidence_scope.get("claim") != "implemented_offline_checks_only"
            or any(
                evidence_scope.get(key) is not False
                for key in ("full_a1_verified", "stage_a_verified")
            )
        ):
            reasons.append(_reason(A10ReasonCode.BINDING_MISMATCH))
        if (
            type(evidence.get("format_version")) is not int
            or evidence.get("format_version") != 1
        ):
            reasons.append(_reason(A10ReasonCode.FORMAT_MISMATCH))
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
                or item.get("reason") != "none"
                or type(item.get("exit_code")) is not int
                or item.get("exit_code") != 0
                for item in checks
            )
        ):
            reasons.append(_reason(A10ReasonCode.CHECK_NOT_PASSED))
        if (
            evidence.get("completed") is False
            or evidence.get("overall") == "incomplete"
            or any(
                value.get("status") == "incomplete" for _, _, value, *_ in predecessors
            )
        ):
            reasons.append(_reason(A10ReasonCode.RUN_INCOMPLETE))
        for key, required in (
            ("test_modules", REQUIRED_TEST_MODULES),
            ("source_modules", REQUIRED_SOURCE_MODULES),
            ("fixture_files", REQUIRED_FIXTURE_FILES),
        ):
            result[key] = file_records(root, required)
            if not required or any(
                record["result"] != CheckStatus.PASSED for record in result[key]
            ):
                reasons.append(_reason(A10ReasonCode.SCOPE_DRIFT, key))
        receipt = read_json(receipt_path)
        if receipt is None or not receipt_completed(receipt, run_id):
            reasons.append(_reason(A10ReasonCode.TEST_EXECUTION_NOT_PASSED))
        if receipt is not None:
            if (
                type(receipt.get("format_version")) is not int
                or receipt.get("format_version") != 1
            ):
                reasons.append(_reason(A10ReasonCode.FORMAT_MISMATCH))
            if receipt.get("completed") is False:
                reasons.append(_reason(A10ReasonCode.RUN_INCOMPLETE))
            modules = receipt.get("modules")
            result["test_execution"] = receipt_records(
                modules if isinstance(modules, dict) else {}, REQUIRED_TEST_CASE_COUNTS
            )
            if any(
                record["result"] != CheckStatus.PASSED
                for record in result["test_execution"]
            ):
                reasons.append(_reason(A10ReasonCode.TEST_EXECUTION_NOT_PASSED))
        if set(REQUIRED_TEST_CASE_COUNTS) != {
            name for name, _ in REQUIRED_TEST_MODULES
        }:
            reasons.append(_reason(A10ReasonCode.SCOPE_DRIFT))
        coverage = _coverage(root)
        if coverage is None:
            reasons.append(_reason(A10ReasonCode.SCOPE_DRIFT, "coverage"))
        else:
            result["requirements_coverage"] = {
                "file": "tests/fixtures/a10_coverage.json",
                "review_state": coverage["review_state"],
                "original_inventory_count": coverage["original_inventory_count"],
                "source_document_count": coverage["source_document_count"],
                "dispositions": {
                    status: sum(
                        row["status"] == status for row in coverage["requirements"]
                    )
                    for status in (
                        "covered",
                        "superseded",
                        "not_assessed",
                        "operational",
                    )
                },
            }
            result["capability_evidence"] = coverage["capabilities"]
        result["environment"] = environment_versions(REQUIRED_DEPENDENCIES)
        for name, version in result["environment"]["dependencies"].items():
            if version is None:
                reasons.append(_reason(A10ReasonCode.DEPENDENCY_UNAVAILABLE, name))
        try:
            result["migration_revision"] = migrated_revision(
                temp_prefix="paper-radar-a10-"
            )
        except Exception:
            reasons.append(_reason(A10ReasonCode.MIGRATION_UNAVAILABLE))
        else:
            if result["migration_revision"] != MIGRATION_REVISION:
                reasons.append(_reason(A10ReasonCode.MIGRATION_UNAVAILABLE))
        try:
            result["format_versions"] = _formats()
        except Exception:
            result["format_versions"] = None
        if not _same_formats(result["format_versions"], FORMAT_VERSIONS):
            reasons.append(_reason(A10ReasonCode.AUDIT_FORMAT_DRIFT))
        current = capture_identity(root)
        result.update(
            code=current.code,
            worktree_sha256=current.worktree_sha256,
            lockfile_sha256=current.lockfile_sha256,
        )
        if (
            current != baseline
            or not identity_matches(current, evidence, a1, full_a2, a3, a6)
            or any(
                not _code_well_typed(code)
                for code in (
                    current.code,
                    baseline.code,
                    evidence.get("code"),
                    a1.get("code"),
                    full_a2.get("code"),
                    a3.get("code"),
                    a6.get("code"),
                )
            )
        ):
            reasons.append(_reason(A10ReasonCode.IDENTITY_CHANGED))
        if not files_unchanged(
            tuple((path, result[label + "_sha256"]) for label, path in paths.items())
        ) or any(read_json(path) != value for _, path, value, *_ in predecessors):
            reasons.append(_reason(A10ReasonCode.BINDING_MISMATCH))
    except KeyboardInterrupt:
        interrupted = True
    if interrupted and not any(
        reason["code"] == A10ReasonCode.RUN_INCOMPLETE for reason in reasons
    ):
        reasons.append(_reason(A10ReasonCode.RUN_INCOMPLETE))
    status = OverallStatus.PASSED if not reasons else OverallStatus.FAILED
    if any(reason["code"] == A10ReasonCode.RUN_INCOMPLETE for reason in reasons):
        status = OverallStatus.INCOMPLETE
    result.update(
        status=status.value,
        a10_verified=status is OverallStatus.PASSED,
        capabilities=dict.fromkeys(CAPABILITIES, status.value),
    )
    return publish_conclusion(output_dir, run_id, SUFFIX, result), result


def write_group(run: VerificationRun, interrupted: bool) -> tuple[Path, dict[str, Any]]:
    a1_path, a1 = run.conclusions["A1"]
    full_path, full = run.conclusions["完整 A2"]
    a3_path, a3 = run.conclusions["A3"]
    a6_path, a6 = run.conclusions["A6"]
    return write_a10_conclusion(
        run.root,
        run.evidence_path,
        a1_path,
        a1,
        full_path,
        full,
        a3_path,
        a3,
        a6_path,
        a6,
        run.output_dir,
        run.baseline,
        expected_run_id=run.run_id,
        interrupted=interrupted,
    )
