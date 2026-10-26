"""同一次完整离线运行的 A2 全量结论。不继承历史 A2-01 的通过状态。"""

from __future__ import annotations

import importlib.metadata
import signal
import sys
import tempfile
from enum import StrEnum
from pathlib import Path
from typing import Any

from scripts import a1_acceptance
from scripts.a1_acceptance import capture_identity
from scripts.a1_scope import REQUIRED_TEST_MODULES as A1_TEST_MODULES
from scripts.a2_acceptance import A2_01_GROUP
from scripts.a2_full_scope import (
    FORMAT_VERSION,
    FORMAT_VERSIONS,
    ISSUE,
    MIGRATION_REVISION,
    NOT_ASSESSED,
    REQUIRED_CHECKS,
    REQUIRED_DEPENDENCIES,
    REQUIRED_FIXTURE_FILES,
    REQUIRED_SOURCE_MODULES,
    REQUIRED_TEST_CASE_COUNTS,
    REQUIRED_TEST_MODULES,
    SCOPE,
)
from scripts.a3_acceptance import write_group as write_a3_group
from scripts.a4_acceptance import write_group as write_a4_group
from scripts.a5_acceptance import write_group as write_a5_group
from scripts.a6_acceptance import write_group as write_a6_group
from scripts.a7_acceptance import write_group as write_a7_group
from scripts.a8_acceptance import write_group as write_a8_group
from scripts.a9_acceptance import write_group as write_a9_group
from scripts.a10_acceptance import write_group as write_a10_group
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
from scripts.verification_publication import publish_conclusion
from scripts.verification_run import AcceptanceGroup, VerificationRun, run_verification


class A2FullReasonCode(StrEnum):
    EVIDENCE_UNAVAILABLE = "evidence_unavailable"
    BINDING_MISMATCH = "binding_mismatch"
    FORMAT_MISMATCH = "format_mismatch"
    A1_NOT_PASSED = "a1_not_passed"
    CHECK_NOT_PASSED = "check_not_passed"
    SCOPE_DRIFT = "scope_drift"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    MIGRATION_UNAVAILABLE = "migration_unavailable"
    CONFIG_FORMAT_DRIFT = "config_format_drift"
    IDENTITY_CHANGED = "identity_changed"
    RUN_INCOMPLETE = "run_incomplete"
    TEST_EXECUTION_NOT_PASSED = "test_execution_not_passed"


_HELP: dict[A2FullReasonCode, str] = {
    A2FullReasonCode.EVIDENCE_UNAVAILABLE: "本次证据无法读取；请重跑完整离线入口。",
    A2FullReasonCode.BINDING_MISMATCH: (
        "证据、A1 结论或运行身份不一致；请重跑完整离线入口。"
    ),
    A2FullReasonCode.FORMAT_MISMATCH: (
        "证据或结论格式不受支持；请核对格式版本后重跑。"
    ),
    A2FullReasonCode.A1_NOT_PASSED: "本次 A1 未通过；请先处理 A1 结论中的原因。",
    A2FullReasonCode.CHECK_NOT_PASSED: (
        "完整固定检查缺失、失败或未执行；请查看本次离线证据。"
    ),
    A2FullReasonCode.SCOPE_DRIFT: (
        "固定范围文件缺失或字节变化；请逐项审查后显式更新范围。"
    ),
    A2FullReasonCode.DEPENDENCY_UNAVAILABLE: "A2 依赖实际版本不可得；请修复锁定环境。",
    A2FullReasonCode.MIGRATION_UNAVAILABLE: (
        "临时验收库迁移失败或 head 未登记；请审查迁移范围。"
    ),
    A2FullReasonCode.CONFIG_FORMAT_DRIFT: (
        "配置格式身份变化；请审查并显式版本化验收范围。"
    ),
    A2FullReasonCode.IDENTITY_CHANGED: (
        "运行期间代码、工作树或 lockfile 变化；请重跑完整入口。"
    ),
    A2FullReasonCode.RUN_INCOMPLETE: "本次运行中断或未完成；请重新执行完整入口。",
    A2FullReasonCode.TEST_EXECUTION_NOT_PASSED: (
        "本次测试回执缺失、不一致或固定用例未全部执行通过；请重跑完整入口。"
    ),
}


def _reason(code: A2FullReasonCode, item: str | None = None) -> dict[str, str]:
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
        available = isinstance(version, str) and bool(version.strip())
        versions[name] = version if available else None
        if not available:
            reasons.append(_reason(A2FullReasonCode.DEPENDENCY_UNAVAILABLE, name))
    return {"python": sys.version.split()[0], "dependencies": versions}


def _formats() -> dict[str, Any]:
    from paper_radar.config.adapters import ADAPTER_SEMANTICS_FORMAT_VERSION
    from paper_radar.config.compile import FORMAT_VERSION as snapshot_version
    from paper_radar.config.projections import (
        BASELINE_FORMAT_VERSION,
        PROJECTION_FORMAT_VERSIONS,
    )

    return {
        "snapshot": snapshot_version,
        "stage_projections": {
            stage.value: version
            for stage, version in PROJECTION_FORMAT_VERSIONS.items()
        },
        "calibration_baseline": BASELINE_FORMAT_VERSION,
        "adapter_semantics": ADAPTER_SEMANTICS_FORMAT_VERSION,
    }


def _migrated_revision() -> str | None:
    """实际创建并升级独立临时库, 读取库内 revision。不接受用户库路径。"""
    from paper_radar.storage.database import (
        DatabaseMode,
        current_revision,
        open_database,
        upgrade_database,
    )

    with tempfile.TemporaryDirectory(prefix="paper-radar-a2-") as directory:
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


def _test_execution(
    path: Path,
    run_id: str,
    reasons: list[dict[str, str]],
) -> list[dict[str, Any]]:
    receipt = read_json(path)
    if receipt is None:
        reasons.append(_reason(A2FullReasonCode.TEST_EXECUTION_NOT_PASSED))
        return []
    if not receipt_completed(receipt, run_id):
        reasons.append(_reason(A2FullReasonCode.TEST_EXECUTION_NOT_PASSED))
    if receipt.get("completed") is False:
        reasons.append(_reason(A2FullReasonCode.RUN_INCOMPLETE))
    required = {name for name, _ in (*A1_TEST_MODULES, *REQUIRED_TEST_MODULES)}
    if set(REQUIRED_TEST_CASE_COUNTS) != required:
        reasons.append(_reason(A2FullReasonCode.SCOPE_DRIFT))
    modules = receipt.get("modules")
    if not isinstance(modules, dict):
        reasons.append(_reason(A2FullReasonCode.TEST_EXECUTION_NOT_PASSED))
        modules = {}
    records = receipt_records(
        modules,
        {name: REQUIRED_TEST_CASE_COUNTS.get(name) for name in required},
    )
    for record in records:
        if record["result"] != CheckStatus.PASSED:
            reasons.append(
                _reason(A2FullReasonCode.TEST_EXECUTION_NOT_PASSED, record["path"])
            )
    return records


def _validate_run(
    evidence_path: Path,
    a1_path: Path,
    a1: dict[str, Any],
    reasons: list[dict[str, str]],
) -> dict[str, Any]:
    evidence = read_json(evidence_path)
    if evidence is None:
        reasons.append(_reason(A2FullReasonCode.EVIDENCE_UNAVAILABLE))
        evidence = {}
    run_id = a1["run_id"]
    if (
        not same_run_document(a1_path, run_id, ".a1.json", a1)
        or evidence_path.name != f"{run_id}.json"
        or evidence.get("run_id") != run_id
        or a1.get("evidence_sha256") != file_sha256(evidence_path)
        or a1.get("scope") != "a1_screening_authoritative_contracts"
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
        reasons.append(_reason(A2FullReasonCode.BINDING_MISMATCH))
    if evidence.get("format_version") != 1 or a1.get("format_version") != 1:
        reasons.append(_reason(A2FullReasonCode.FORMAT_MISMATCH))
    if a1.get("status") != OverallStatus.PASSED or a1.get("a1_verified") is not True:
        reasons.append(_reason(A2FullReasonCode.A1_NOT_PASSED))
    checks = evidence.get("checks")
    if (
        evidence.get("completed") is not True
        or evidence.get("overall") != OverallStatus.PASSED
        or not isinstance(checks, list)
        or [c.get("id") if isinstance(c, dict) else None for c in checks]
        != list(REQUIRED_CHECKS)
        or any(
            not isinstance(c, dict)
            or c.get("status") != CheckStatus.PASSED
            or c.get("reason") != CheckReason.NONE
            or type(c.get("exit_code")) is not int
            or c.get("exit_code") != 0
            for c in checks
        )
    ):
        reasons.append(_reason(A2FullReasonCode.CHECK_NOT_PASSED))
    if (
        evidence.get("completed") is False
        or evidence.get("overall") == OverallStatus.INCOMPLETE
        or a1.get("status") == OverallStatus.INCOMPLETE
    ):
        reasons.append(_reason(A2FullReasonCode.RUN_INCOMPLETE))
    return evidence


def write_full_a2_conclusion(
    root: Path,
    evidence_path: Path,
    a1_path: Path,
    a1_conclusion: dict[str, Any],
    output_dir: Path,
    *,
    interrupted: bool = False,
) -> tuple[Path, dict[str, Any]]:
    """只追加完整 A2 结论。不执行完整测试或读取旧运行结论与配置正文。"""
    reasons: list[dict[str, str]] = []
    run_id = a1_conclusion["run_id"]
    result: dict[str, Any] = {
        "format_version": FORMAT_VERSION,
        "run_id": run_id,
        "scope": SCOPE,
        "issue": ISSUE,
        "status": OverallStatus.INCOMPLETE.value,
        "a2_verified": False,
        "stage_a_verified": False,
        "live_verified": False,
        "evidence_file": evidence_path.name,
        "evidence_sha256": None,
        "a1_conclusion_file": a1_path.name,
        "a1_conclusion_sha256": None,
        "required_checks": list(REQUIRED_CHECKS),
        "test_modules": [],
        "source_modules": [],
        "fixture_files": [],
        "pytest_receipt_file": evidence_path.with_suffix(".pytest.json").name,
        "pytest_receipt_sha256": None,
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
    try:
        evidence = _validate_run(evidence_path, a1_path, a1_conclusion, reasons)
        result["evidence_sha256"] = file_sha256(evidence_path)
        result["a1_conclusion_sha256"] = file_sha256(a1_path)
        for key, required in (
            ("test_modules", REQUIRED_TEST_MODULES),
            ("source_modules", REQUIRED_SOURCE_MODULES),
            ("fixture_files", REQUIRED_FIXTURE_FILES),
        ):
            result[key] = file_records(root, required)
            if not required:
                reasons.append(_reason(A2FullReasonCode.SCOPE_DRIFT))
            for record in result[key]:
                if record["result"] != CheckStatus.PASSED:
                    reasons.append(
                        _reason(A2FullReasonCode.SCOPE_DRIFT, record["path"])
                    )
        receipt_path = evidence_path.with_suffix(".pytest.json")
        result["pytest_receipt_sha256"] = file_sha256(receipt_path)
        result["test_execution"] = _test_execution(receipt_path, run_id, reasons)
        result["environment"] = _environment(reasons)
        try:
            result["migration_revision"] = _migrated_revision()
        except Exception:
            reasons.append(_reason(A2FullReasonCode.MIGRATION_UNAVAILABLE))
        else:
            if result["migration_revision"] != MIGRATION_REVISION:
                reasons.append(_reason(A2FullReasonCode.MIGRATION_UNAVAILABLE))
        result["format_versions"] = _formats()
        if result["format_versions"] != FORMAT_VERSIONS:
            reasons.append(_reason(A2FullReasonCode.CONFIG_FORMAT_DRIFT))
        current = capture_identity(root)
        result.update(
            code=current.code,
            worktree_sha256=current.worktree_sha256,
            lockfile_sha256=current.lockfile_sha256,
        )
        if not identity_matches(current, evidence, a1_conclusion):
            reasons.append(_reason(A2FullReasonCode.IDENTITY_CHANGED))
        # 结论发布前再次核对绑定文件, 不能接受检查期间替换的证据。
        if (
            not files_unchanged(
                (
                    (evidence_path, result["evidence_sha256"]),
                    (a1_path, result["a1_conclusion_sha256"]),
                    (receipt_path, result["pytest_receipt_sha256"]),
                )
            )
            or result["evidence_sha256"] != a1_conclusion.get("evidence_sha256")
            or read_json(a1_path) != a1_conclusion
        ):
            reasons.append(_reason(A2FullReasonCode.BINDING_MISMATCH))
    except KeyboardInterrupt:
        interrupted = True
    if interrupted:
        reasons.append(_reason(A2FullReasonCode.RUN_INCOMPLETE))
    status = OverallStatus.PASSED if not reasons else OverallStatus.FAILED
    if any(
        reason["code"] == A2FullReasonCode.RUN_INCOMPLETE.value for reason in reasons
    ):
        status = OverallStatus.INCOMPLETE
    result.update(status=status.value, a2_verified=status is OverallStatus.PASSED)
    path = publish_conclusion(output_dir, run_id, ".a2-full.json", result)
    return path, result


def _write_group(
    run: VerificationRun, interrupted: bool
) -> tuple[Path, dict[str, Any]]:
    a1_path, a1 = run.conclusions["A1"]
    return write_full_a2_conclusion(
        run.root,
        run.evidence_path,
        a1_path,
        a1,
        run.output_dir,
        interrupted=interrupted,
    )


def acceptance_groups() -> tuple[AcceptanceGroup, ...]:
    """生产登记处: 发布顺序与是否决定整体通过分别声明。"""
    return (
        a1_acceptance.A1_GROUP,
        A2_01_GROUP,
        AcceptanceGroup(
            name="完整 A2",
            suffix=".a2-full.json",
            write=_write_group,
            required=True,
            dependencies=("A1",),
            show_reasons=True,
        ),
        AcceptanceGroup(
            name="A3",
            suffix=".a3.json",
            write=write_a3_group,
            required=True,
            dependencies=("A1", "完整 A2"),
            show_reasons=True,
        ),
        AcceptanceGroup(
            name="A4",
            suffix=".a4.json",
            write=write_a4_group,
            required=True,
            dependencies=("A1", "完整 A2", "A3"),
            show_reasons=True,
        ),
        AcceptanceGroup(
            name="A5",
            suffix=".a5.json",
            write=write_a5_group,
            required=True,
            dependencies=("A1", "完整 A2", "A3"),
            show_reasons=True,
        ),
        AcceptanceGroup(
            name="A6",
            suffix=".a6.json",
            write=write_a6_group,
            required=True,
            dependencies=("A1", "完整 A2", "A3", "A5"),
            show_reasons=True,
        ),
        AcceptanceGroup(
            name="A7",
            suffix=".a7.json",
            write=write_a7_group,
            required=True,
            dependencies=("A1", "完整 A2", "A3", "A5", "A6"),
            show_reasons=True,
        ),
        AcceptanceGroup(
            name="A8",
            suffix=".a8.json",
            write=write_a8_group,
            required=True,
            dependencies=("A1", "完整 A2", "A3", "A5", "A6", "A7"),
            show_reasons=True,
        ),
        AcceptanceGroup(
            name="A9",
            suffix=".a9.json",
            write=write_a9_group,
            required=True,
            dependencies=("A1", "完整 A2", "A3"),
            show_reasons=True,
        ),
        AcceptanceGroup(
            name="A10",
            suffix=".a10.json",
            write=write_a10_group,
            required=True,
            dependencies=("A1", "完整 A2", "A3", "A6"),
            show_reasons=True,
        ),
    )


def _run_verification(root: Path, output_dir: Path) -> VerificationRun:
    return run_verification(
        root,
        output_dir,
        acceptance_groups(),
        capture=a1_acceptance.capture_identity,
        execute=a1_acceptance.execute_checks,
    )


def run_full_verification(root: Path, output_dir: Path) -> tuple[Path, dict[str, Any]]:
    """兼容完整入口; 组织模块执行一次固定计划及全部已登记验收组。"""
    return _run_verification(root, output_dir).conclusions["完整 A2"]


def _interrupt(_signum: int, _frame: object) -> None:
    raise KeyboardInterrupt


def main() -> int:
    signal.signal(signal.SIGTERM, _interrupt)
    root = Path(__file__).resolve().parents[1]
    run = _run_verification(root, root / "verification-runs")
    return 0 if run.passed else 1


if __name__ == "__main__":
    sys.exit(main())
