"""根据一次完整离线运行的证据生成独立的 A1 验收结论。"""

from __future__ import annotations

import hashlib
import json
import os
import signal
import stat
import subprocess
import sys
import uuid
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from paper_radar.contracts import (
    ContractCheckError,
    ContractCheckErrorCategory,
    ContractCheckOutcome,
    check_frozen_contracts,
)
from scripts.a1_scope import REQUIRED_TEST_MODULES
from scripts.offline_evidence import (
    CONTRACT_NAMES,
    CONTRACT_VERSION,
    CheckReason,
    CheckStatus,
    CodeIdentity,
    OverallStatus,
    default_checks,
    file_sha256,
    git_metadata,
    run_offline_verification,
)

_NOT_ASSESSED = (
    "runtime_plan",
    "persistence",
    "stage_fingerprints",
    "tasks_and_shared_interfaces",
    "doctor",
    "structured_logs",
    "backup_and_recovery",
    "live_source_audit",
    "stage_b",
    "automatic_fulltext_reading",
)


class A1ReasonCode(StrEnum):
    EVIDENCE_UNAVAILABLE = "evidence_unavailable"
    EVIDENCE_IDENTITY_MISMATCH = "evidence_identity_mismatch"
    EVIDENCE_SCOPE_MISMATCH = "evidence_scope_mismatch"
    RUN_INCOMPLETE = "run_incomplete"
    OFFLINE_CHECKS_NOT_PASSED = "offline_checks_not_passed"
    CHECK_SCOPE_MISMATCH = "check_scope_mismatch"
    CHECK_NOT_PASSED = "check_not_passed"
    TEST_SCOPE_MISMATCH = "test_scope_mismatch"
    CONTRACT_SCOPE_MISMATCH = "contract_scope_mismatch"
    SNAPSHOT_INVALID = "snapshot_invalid"
    SNAPSHOT_HASH_MISMATCH = "snapshot_hash_mismatch"
    IDENTITY_CHANGED = "identity_changed"
    ENVIRONMENT_UNAVAILABLE = "environment_unavailable"


_REASON_HELP: dict[A1ReasonCode, str] = {
    A1ReasonCode.EVIDENCE_UNAVAILABLE: "本次离线证据无法读取；重新运行完整离线入口。",
    A1ReasonCode.EVIDENCE_IDENTITY_MISMATCH: (
        "证据格式或 run_id 不属于本次运行；重新运行完整离线入口。"
    ),
    A1ReasonCode.EVIDENCE_SCOPE_MISMATCH: (
        "本次证据不是 #12 固定离线范围；使用完整入口重跑。"
    ),
    A1ReasonCode.RUN_INCOMPLETE: "本次检查被中断或尚未收尾；修复后重新运行。",
    A1ReasonCode.OFFLINE_CHECKS_NOT_PASSED: (
        "本次离线检查未全部通过；查看证据中的失败项。"
    ),
    A1ReasonCode.CHECK_SCOPE_MISMATCH: (
        "本次证据缺少固定 A1 检查项；使用仓库的 check-offline 入口重跑。"
    ),
    A1ReasonCode.CHECK_NOT_PASSED: "必需检查未通过或未执行；修复后重新运行完整入口。",
    A1ReasonCode.TEST_SCOPE_MISMATCH: (
        "固定 A1 测试模块缺失或内容漂移；核对测试并更新范围清单。"
    ),
    A1ReasonCode.CONTRACT_SCOPE_MISMATCH: (
        "证据未覆盖四份 v1 契约；使用固定完整入口重跑。"
    ),
    A1ReasonCode.SNAPSHOT_INVALID: (
        "冻结快照缺失或不一致；逐项运行 contracts check 定位并修复。"
    ),
    A1ReasonCode.SNAPSHOT_HASH_MISMATCH: (
        "证据中的快照哈希与当前文件不同；重新运行完整入口。"
    ),
    A1ReasonCode.IDENTITY_CHANGED: (
        "HEAD、工作树或 lockfile 与本次检查身份不一致；重新运行完整入口。"
    ),
    A1ReasonCode.ENVIRONMENT_UNAVAILABLE: (
        "锁定环境版本信息不完整；修复环境后重新运行。"
    ),
}


@dataclass(frozen=True, slots=True)
class RunIdentity:
    code: CodeIdentity
    lockfile_sha256: str | None
    worktree_sha256: str | None


def _worktree_sha256(root: Path) -> str | None:
    """哈希 Git 管理及非忽略文件的路径、类型和字节; 不保存内容。"""
    try:
        result = subprocess.run(
            ("git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"),
            cwd=root,
            capture_output=True,
            check=True,
        )
        digest = hashlib.sha256()
        for relative in sorted(set(result.stdout.split(b"\0")) - {b""}):
            path = root / os.fsdecode(relative)
            digest.update(len(relative).to_bytes(8, "big"))
            digest.update(relative)
            if not os.path.lexists(path):
                digest.update(b"missing\0")
                continue
            digest.update(stat.S_IMODE(path.lstat().st_mode).to_bytes(2, "big"))
            if path.is_symlink():
                digest.update(b"link\0")
                digest.update(os.fsencode(os.readlink(path)))
            elif path.is_file():
                digest.update(b"file\0")
                digest.update(hashlib.sha256(path.read_bytes()).digest())
            else:
                digest.update(b"other\0")
        return digest.hexdigest()
    except (OSError, subprocess.CalledProcessError):
        return None


def capture_identity(root: Path) -> RunIdentity:
    """采集一次运行的 HEAD、工作树与锁文件身份。"""
    return RunIdentity(
        code=git_metadata(root),
        lockfile_sha256=file_sha256(root / "uv.lock"),
        worktree_sha256=_worktree_sha256(root),
    )


def _reason(code: A1ReasonCode, item: str | None = None) -> dict[str, str]:
    return {
        "code": code,
        "message_zh": _REASON_HELP[code],
        **({"item": item} if item is not None else {}),
    }


def _load_evidence(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        raw = path.read_bytes()
        loaded = json.loads(raw)
    except (OSError, ValueError):
        return None, None
    if not isinstance(loaded, dict):
        return None, None
    return loaded, hashlib.sha256(raw).hexdigest()


def _check_scope(evidence: dict[str, Any], reasons: list[dict[str, str]]) -> None:
    expected = [check.id for check in default_checks()]
    checks = evidence.get("checks")
    if (
        not isinstance(checks, list)
        or [item.get("id") if isinstance(item, dict) else None for item in checks]
        != expected
    ):
        reasons.append(_reason(A1ReasonCode.CHECK_SCOPE_MISMATCH))
        return
    for item in checks:
        if (
            item.get("status") != CheckStatus.PASSED
            or item.get("reason") != CheckReason.NONE
            or item.get("exit_code") != 0
        ):
            reasons.append(_reason(A1ReasonCode.CHECK_NOT_PASSED, item["id"]))


def _check_test_modules(
    root: Path, reasons: list[dict[str, str]]
) -> list[dict[str, Any]]:
    modules: list[dict[str, Any]] = []
    for relative, expected_hash in REQUIRED_TEST_MODULES:
        actual_hash = file_sha256(root / relative)
        matched = actual_hash == expected_hash
        modules.append(
            {
                "path": relative,
                "expected_sha256": expected_hash,
                "actual_sha256": actual_hash,
                "result": "passed" if matched else "failed",
            }
        )
        if not matched:
            reasons.append(_reason(A1ReasonCode.TEST_SCOPE_MISMATCH, relative))
    return modules


def _check_contracts(
    evidence: dict[str, Any], target: Path, reasons: list[dict[str, str]]
) -> list[dict[str, str | None]]:
    recorded = evidence.get("contracts")
    if not isinstance(recorded, list) or [
        (item.get("name"), item.get("version")) if isinstance(item, dict) else None
        for item in recorded
    ] != [(name, CONTRACT_VERSION) for name in CONTRACT_NAMES]:
        reasons.append(_reason(A1ReasonCode.CONTRACT_SCOPE_MISMATCH))
        recorded = None
    try:
        checked = check_frozen_contracts(CONTRACT_NAMES, CONTRACT_VERSION, target)
    except ContractCheckError as error:
        reason = (
            A1ReasonCode.CONTRACT_SCOPE_MISMATCH
            if error.category is ContractCheckErrorCategory.INVALID_SELECTION
            else A1ReasonCode.SNAPSHOT_INVALID
        )
        reasons.append(_reason(reason))
        return []
    snapshots: list[dict[str, str | None]] = []
    for index, current in enumerate(checked.items):
        snapshots.append(
            {
                "name": current.name.value,
                "version": current.version.value,
                "result": current.outcome.value,
                "error_category": (
                    current.error_category.value
                    if current.error_category is not None
                    else None
                ),
                "schema_sha256": current.schema_sha256,
            }
        )
        if current.outcome is not ContractCheckOutcome.PASSED:
            reasons.append(_reason(A1ReasonCode.SNAPSHOT_INVALID, current.name.value))
        elif (
            recorded is not None
            and recorded[index].get("schema_sha256") != current.schema_sha256
        ):
            reasons.append(
                _reason(A1ReasonCode.SNAPSHOT_HASH_MISMATCH, current.name.value)
            )
    return snapshots


def _check_results(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    raw = evidence.get("checks")
    if not isinstance(raw, list):
        return []
    result: list[dict[str, Any]] = []
    check_ids = {check.id for check in default_checks()}
    statuses = set(CheckStatus)
    reasons = set(CheckReason)
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            continue
        if item["id"] not in check_ids:
            continue
        status = item.get("status")
        reason = item.get("reason")
        result.append(
            {
                "id": item["id"],
                "status": status
                if isinstance(status, str) and status in statuses
                else "invalid",
                "reason": reason
                if isinstance(reason, str) and reason in reasons
                else "invalid",
                "exit_code": item.get("exit_code")
                if type(item.get("exit_code")) is int
                else None,
            }
        )
    return result


def write_a1_conclusion(
    root: Path,
    evidence_path: Path,
    output_dir: Path,
    baseline: RunIdentity,
    *,
    contract_target: Path | None = None,
    expected_run_id: str,
    interrupted: bool = False,
) -> tuple[Path, dict[str, Any]]:
    """核对本次证据与固定 A1 范围; 再发布独立结论。"""
    evidence, evidence_sha256 = _load_evidence(evidence_path)
    current = capture_identity(root)
    reasons: list[dict[str, str]] = []
    snapshots: list[dict[str, str | None]] = []
    test_modules: list[dict[str, Any]] = []
    if evidence is None:
        reasons.append(_reason(A1ReasonCode.EVIDENCE_UNAVAILABLE))
        evidence = {}
    else:
        if (
            evidence.get("run_id") != expected_run_id
            or evidence_path.stem != expected_run_id
            or evidence.get("format_version") != 1
        ):
            reasons.append(_reason(A1ReasonCode.EVIDENCE_IDENTITY_MISMATCH))
        scope = evidence.get("scope")
        if not isinstance(scope, dict) or any(
            scope.get(key) != value
            for key, value in {
                "issue": 12,
                "claim": "implemented_offline_checks_only",
                "full_a1_verified": False,
                "stage_a_verified": False,
            }.items()
        ):
            reasons.append(_reason(A1ReasonCode.EVIDENCE_SCOPE_MISMATCH))
        if evidence.get("completed") is not True:
            reasons.append(_reason(A1ReasonCode.RUN_INCOMPLETE))
        if evidence.get("overall") != OverallStatus.PASSED:
            reasons.append(_reason(A1ReasonCode.OFFLINE_CHECKS_NOT_PASSED))
        _check_scope(evidence, reasons)
        test_modules = _check_test_modules(root, reasons)
        snapshots = _check_contracts(
            evidence, contract_target or root / "contracts", reasons
        )

        if (
            baseline.code["commit"] is None
            or baseline.code["dirty"] is None
            or baseline.lockfile_sha256 is None
            or baseline.worktree_sha256 is None
            or evidence.get("code") != baseline.code
            or evidence.get("lockfile_sha256") != baseline.lockfile_sha256
            or current != baseline
        ):
            reasons.append(_reason(A1ReasonCode.IDENTITY_CHANGED))

        environment = evidence.get("environment")
        if (
            not isinstance(environment, dict)
            or not isinstance(environment.get("python"), str)
            or environment.get("missing_reason") is not None
            or not isinstance(environment.get("dependencies"), dict)
            or any(
                not isinstance(environment["dependencies"].get(name), str)
                for name in ("pydantic", "typer", "pytest", "ruff", "mypy")
            )
        ):
            reasons.append(_reason(A1ReasonCode.ENVIRONMENT_UNAVAILABLE))

    environment = evidence.get("environment")
    if interrupted:
        reasons.append(_reason(A1ReasonCode.RUN_INCOMPLETE))

    status = "passed" if not reasons else "failed"
    if A1ReasonCode.RUN_INCOMPLETE in {reason["code"] for reason in reasons}:
        status = "incomplete"
    conclusion: dict[str, Any] = {
        "format_version": 1,
        "run_id": expected_run_id,
        "evidence_file": evidence_path.name,
        "evidence_sha256": evidence_sha256,
        "scope": "a1_screening_authoritative_contracts",
        "issue": 13,
        "required_checks": [check.id for check in default_checks()],
        "required_test_modules": [
            {"path": path, "sha256": sha256} for path, sha256 in REQUIRED_TEST_MODULES
        ],
        "required_contracts": list(CONTRACT_NAMES),
        "contract_version": CONTRACT_VERSION,
        "checks": _check_results(evidence),
        "test_modules": test_modules,
        "contracts": snapshots,
        "environment": evidence.get("environment")
        if isinstance(environment, dict)
        else None,
        "status": status,
        "a1_verified": status == "passed",
        "stage_a_verified": False,
        "not_assessed": list(_NOT_ASSESSED),
        "code": current.code,
        "worktree_sha256": current.worktree_sha256,
        "lockfile_sha256": current.lockfile_sha256,
        "reasons": reasons,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{expected_run_id}.a1.json"
    temporary = output_dir / f".{expected_run_id}.{uuid.uuid4().hex}.tmp"
    payload = (
        json.dumps(conclusion, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode()
    try:
        with temporary.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path, conclusion


def run_a1_verification(root: Path, output_dir: Path) -> tuple[Path, dict[str, Any]]:
    """运行固定计划, 并以同一次运行身份写出 A1 结论。"""
    baseline = capture_identity(root)
    evidence_path, evidence = run_offline_verification(
        root, default_checks(), output_dir
    )
    run_id = evidence["run_id"]
    try:
        path, conclusion = write_a1_conclusion(
            root, evidence_path, output_dir, baseline, expected_run_id=run_id
        )
    except KeyboardInterrupt:
        published = output_dir / f"{run_id}.a1.json"
        if published.exists():
            path = published
            conclusion = json.loads(path.read_text())
        else:
            path, conclusion = write_a1_conclusion(
                root,
                evidence_path,
                output_dir,
                baseline,
                expected_run_id=run_id,
                interrupted=True,
            )
    print(f"[A1 验收] 离线证据：{evidence_path}")
    print(f"[A1 验收] 结论：{path}")
    print(f"[A1 验收] 结果：{conclusion['status']}")
    for reason in conclusion["reasons"]:
        print(f"[A1 验收] 原因：{reason['code']}：{reason['message_zh']}")
    return path, conclusion


def main() -> int:
    """执行一次固定离线计划并给出独立 A1、A2-01 结论。"""
    signal.signal(signal.SIGTERM, _interrupt)
    root = Path(__file__).resolve().parent.parent
    output_dir = root / "verification-runs"
    a1_path, a1 = run_a1_verification(root, output_dir)
    from scripts.a2_acceptance import write_a2_conclusion

    evidence_path = output_dir / f"{a1['run_id']}.json"
    a2_path, a2 = write_a2_conclusion(root, evidence_path, a1_path, a1, output_dir)
    print(f"[A2-01 验收] 结论：{a2_path}")
    print(f"[A2-01 验收] 结果：{a2['status']}")
    for reason in a2["reasons"]:
        print(f"[A2-01 验收] 原因：{reason['code']}：{reason['message_zh']}")
    return 0 if a1["a1_verified"] and a2["a2_01_verified"] else 1


def _interrupt(_signum: int, _frame: object) -> None:
    raise KeyboardInterrupt


if __name__ == "__main__":
    sys.exit(main())
