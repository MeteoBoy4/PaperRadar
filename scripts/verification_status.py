"""只读核对控制方终态与同次材料; 不重新执行任何验收判据。"""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Never

from scripts.offline_evidence import file_sha256
from scripts.verification_checks import (
    RECEIPT_COUNTERS,
    files_unchanged,
    identity_matches,
    receipt_completed,
)
from scripts.verification_identity import RunIdentity, capture_identity


class Status(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    INCOMPLETE = "incomplete"
    UNAVAILABLE = "unavailable"
    UNCONFIRMED = "unconfirmed"


class Reason(StrEnum):
    VERIFIED = "verified"
    TERMINAL_MISSING = "terminal_missing"
    MATERIAL_UNAVAILABLE = "material_unavailable"
    INVALID_DOCUMENT = "invalid_document"
    UNSUPPORTED_FORMAT = "unsupported_format"
    RUN_ID_MISMATCH = "run_id_mismatch"
    BINDING_MISMATCH = "binding_mismatch"
    CHECKS_NOT_PASSED = "checks_not_passed"
    GROUP_NOT_PASSED = "group_not_passed"
    RECEIPT_NOT_PASSED = "receipt_not_passed"
    EXIT_NONZERO = "exit_nonzero"
    INTERRUPTED = "interrupted"


class Phase(StrEnum):
    CHECKING = "checking"
    PUBLISHING = "publishing"
    FINISHED = "finished"
    UNKNOWN = "unknown"


class Applicability(StrEnum):
    SAME = "same"
    DIFFERENT = "different"
    UNKNOWN = "unknown"


STATUS_ZH = {
    Status.PASSED: "通过",
    Status.FAILED: "失败",
    Status.INCOMPLETE: "中断/不完整",
    Status.UNAVAILABLE: "材料不可得",
    Status.UNCONFIRMED: "历史结果/终态未证实",
}
PHASE_ZH = {
    Phase.CHECKING: "检查执行中（未证实存活）",
    Phase.PUBLISHING: "结论发布中（未证实存活）",
    Phase.FINISHED: "已收尾",
    Phase.UNKNOWN: "未知",
}
# 格式 1 的已发布计划, 不随生产 default_checks 的将来调整改变历史含义。
CHECK_IDS_V1 = ("lockfile", "format", "lint", "types", "tests", "contracts")
# 历史解析能力表, 独立于当前生产 registry; 升级时保留已支持的旧格式。
SUPPORTED_GROUP_FORMATS = {
    ".a7.json": (1,),
    ".a6.json": (1,),
    ".a1.json": (1,),
    ".a2.json": (1,),
    ".a2-full.json": (2,),
    ".a3.json": (1,),
    ".a4.json": (1,),
    ".a5.json": (1,),
}


class _Invalid(ValueError):
    def __init__(self, reason: Reason) -> None:
        self.reason = reason
        super().__init__(reason.value)


def _document(path: Path, run_id: str) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
    except OSError:
        raise _Invalid(Reason.MATERIAL_UNAVAILABLE) from None
    try:
        value = json.loads(raw)
    except (ValueError, RecursionError):
        raise _Invalid(Reason.INVALID_DOCUMENT) from None
    if not isinstance(value, dict):
        raise _Invalid(Reason.INVALID_DOCUMENT)
    if value.get("run_id") != run_id:
        raise _Invalid(Reason.RUN_ID_MISMATCH)
    return value


def _version(value: dict[str, Any]) -> None:
    if type(value.get("format_version")) is not int or value["format_version"] != 1:
        raise _Invalid(Reason.UNSUPPORTED_FORMAT)


def _checks(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    checks = evidence.get("checks")
    if (
        not isinstance(checks, list)
        or not all(isinstance(item, dict) for item in checks)
        or tuple(item.get("id") for item in checks) != CHECK_IDS_V1
        or any(
            item.get("status") not in ("passed", "failed", "not_run") for item in checks
        )
    ):
        raise _Invalid(Reason.INVALID_DOCUMENT)
    return checks


def _passed_checks(evidence: dict[str, Any]) -> bool:
    return (
        evidence.get("completed") is True
        and evidence.get("overall") == "passed"
        and all(
            item.get("status") == "passed"
            and item.get("reason") == "none"
            and type(item.get("exit_code")) is int
            and item["exit_code"] == 0
            for item in _checks(evidence)
        )
    )


def _test_summary(receipt: dict[str, Any] | None, run_id: str) -> dict[str, int] | None:
    if receipt is None or receipt.get("run_id") != run_id:
        return None
    modules = receipt.get("modules")
    if not isinstance(modules, dict) or not modules:
        return None
    counts = dict.fromkeys((key.value for key in RECEIPT_COUNTERS), 0)
    for module in modules.values():
        if not isinstance(module, dict):
            return None
        for key in counts:
            value = module.get(key)
            if type(value) is not int or value < 0:
                return None
            counts[key] += value
    return counts


def _terminal(
    directory: Path, run_id: str, terminal: dict[str, Any]
) -> tuple[Status, Reason]:
    _version(terminal)
    if (
        type(terminal.get("exit_code")) is not int
        or type(terminal.get("interrupted")) is not bool
        or type(terminal.get("materials_consistent")) is not bool
    ):
        raise _Invalid(Reason.INVALID_DOCUMENT)
    groups = terminal.get("groups")
    if not isinstance(groups, list) or not groups:
        raise _Invalid(Reason.INVALID_DOCUMENT)
    bindings: dict[str, str] = {}
    documents: dict[str, dict[str, Any]] = {}

    def bound(suffix: str, digest: object) -> dict[str, Any]:
        path = directory / f"{run_id}{suffix}"
        if not isinstance(digest, str) or not re.fullmatch("[0-9a-f]{64}", digest):
            raise _Invalid(Reason.BINDING_MISMATCH)
        actual = file_sha256(path)
        if actual is None:
            raise _Invalid(Reason.MATERIAL_UNAVAILABLE)
        if actual != digest:
            raise _Invalid(Reason.BINDING_MISMATCH)
        value = _document(path, run_id)
        bindings[path.name] = digest
        documents[path.name] = value
        return value

    evidence = bound(".json", terminal.get("evidence_sha256"))
    receipt = None
    if terminal.get("pytest_receipt_sha256") is not None:
        receipt = bound(".pytest.json", terminal["pytest_receipt_sha256"])
        _version(receipt)
    required = []
    suffixes = {".terminal.json", ".pytest.json"}
    for group in groups:
        if not isinstance(group, dict):
            raise _Invalid(Reason.INVALID_DOCUMENT)
        suffix = group.get("suffix")
        if (
            not isinstance(suffix, str)
            or not re.fullmatch(r"\.[a-z0-9-]+\.json", suffix)
            or suffix in suffixes
            or type(group.get("required")) is not bool
        ):
            raise _Invalid(Reason.INVALID_DOCUMENT)
        suffixes.add(suffix)
        value = bound(suffix, group.get("sha256"))
        if (
            type(group.get("format_version")) is not int
            or group["format_version"] not in SUPPORTED_GROUP_FORMATS.get(suffix, ())
            or type(value.get("format_version")) is not int
            or value["format_version"] != group["format_version"]
        ):
            raise _Invalid(Reason.UNSUPPORTED_FORMAT)
        if group["required"]:
            required.append(value)
    if not required:
        raise _Invalid(Reason.INVALID_DOCUMENT)
    # 所有已有文件链接都须指向本次已绑定材料; 不解释各组的业务判据。
    for value in documents.values():
        for key, name in value.items():
            if (
                key.endswith("_file")
                and name == f"{run_id}.pytest.json"
                and receipt is None
                and value.get(key.removesuffix("_file") + "_sha256") is None
            ):
                # 失败或中断可以没有回执; 成功仍在下方要求完整回执。
                continue
            if key.endswith("_file") and (
                not isinstance(name, str)
                or name not in bindings
                or value.get(key.removesuffix("_file") + "_sha256") != bindings[name]
            ):
                raise _Invalid(Reason.BINDING_MISMATCH)
    if not terminal["materials_consistent"]:
        raise _Invalid(Reason.BINDING_MISMATCH)
    if not files_unchanged(
        tuple((directory / name, digest) for name, digest in bindings.items())
    ):
        raise _Invalid(Reason.BINDING_MISMATCH)
    if (
        terminal["interrupted"]
        or evidence.get("overall") == "incomplete"
        or any(value.get("status") == "incomplete" for value in required)
    ):
        return Status.INCOMPLETE, Reason.INTERRUPTED
    if terminal["exit_code"] != 0:
        return Status.FAILED, Reason.EXIT_NONZERO
    if not _passed_checks(evidence):
        return Status.FAILED, Reason.CHECKS_NOT_PASSED
    if any(value.get("status") != "passed" for value in required):
        return Status.FAILED, Reason.GROUP_NOT_PASSED
    if receipt is None or not receipt_completed(receipt, run_id):
        return Status.FAILED, Reason.RECEIPT_NOT_PASSED
    if _test_summary(receipt, run_id) is None:
        return Status.FAILED, Reason.RECEIPT_NOT_PASSED
    code = terminal.get("code")
    if (
        not isinstance(code, dict)
        or not isinstance(code.get("commit"), str)
        or type(code.get("dirty")) is not bool
    ):
        raise _Invalid(Reason.BINDING_MISMATCH)
    identity = RunIdentity(
        {"commit": code["commit"], "dirty": code["dirty"]},
        terminal.get("lockfile_sha256"),
        terminal.get("worktree_sha256"),
    )
    if (
        not isinstance(identity.code, dict)
        or type(identity.code.get("dirty")) is not bool
        or not identity_matches(identity, evidence, *required)
    ):
        raise _Invalid(Reason.BINDING_MISMATCH)
    return Status.PASSED, Reason.VERIFIED


def query_status(root: Path, directory: Path, run_id: str) -> dict[str, Any]:
    """只返回封闭状态、固定计划进度及汇总; 失败不暴露载荷或异常文本。"""
    report: dict[str, Any] = {
        "format_version": 1,
        "status": Status.UNAVAILABLE,
        "reason": Reason.MATERIAL_UNAVAILABLE,
        "phase": Phase.UNKNOWN,
        "current_check": None,
        "checks_passed": 0,
        "checks_total": len(CHECK_IDS_V1),
        "elapsed_seconds": None,
        "tests": None,
        "exit_code": None,
        "applicability": Applicability.UNKNOWN,
    }
    if not re.fullmatch("[0-9a-f]{32}", run_id):
        report["reason"] = Reason.RUN_ID_MISMATCH
        return report
    try:
        evidence = _document(directory / f"{run_id}.json", run_id)
        _version(evidence)
        checks = _checks(evidence)
        try:
            receipt = _document(directory / f"{run_id}.pytest.json", run_id)
        except _Invalid:
            receipt = None
        report["tests"] = _test_summary(receipt, run_id)
        report["checks_passed"] = sum(item["status"] == "passed" for item in checks)
        report["current_check"] = next(
            (
                item["id"]
                for item in checks
                if item["status"] == "not_run"
                and item.get("reason") == "not_started"
                and not evidence.get("finished_at")
            ),
            None,
        )
        report["phase"] = (
            Phase.PUBLISHING if evidence.get("finished_at") else Phase.CHECKING
        )
        try:
            start = datetime.fromisoformat(evidence["started_at"])
            end = (
                datetime.fromisoformat(evidence["finished_at"])
                if evidence.get("finished_at")
                else datetime.now(UTC)
            )
            report["elapsed_seconds"] = max(0, int((end - start).total_seconds()))
        except (KeyError, TypeError, ValueError, OverflowError):
            pass
        terminal_path = directory / f"{run_id}.terminal.json"
        if not terminal_path.exists():
            report.update(status=Status.UNCONFIRMED, reason=Reason.TERMINAL_MISSING)
            if evidence.get("overall") == "incomplete" and evidence.get("finished_at"):
                report.update(status=Status.INCOMPLETE, reason=Reason.INTERRUPTED)
            return report
        terminal_digest = file_sha256(terminal_path)
        terminal = _document(terminal_path, run_id)
        status, reason = _terminal(directory, run_id, terminal)
        if file_sha256(terminal_path) != terminal_digest:
            raise _Invalid(Reason.BINDING_MISMATCH)
        report.update(
            status=status,
            reason=reason,
            phase=Phase.FINISHED,
            exit_code=terminal["exit_code"],
        )
        current = capture_identity(root)
        if (
            current.worktree_sha256 is not None
            and terminal.get("worktree_sha256") is not None
        ):
            report["applicability"] = (
                Applicability.SAME
                if identity_matches(current, evidence, terminal)
                else Applicability.DIFFERENT
            )
    except _Invalid as error:
        report.update(
            status=Status.UNAVAILABLE
            if error.reason == Reason.MATERIAL_UNAVAILABLE
            else Status.FAILED,
            reason=error.reason,
        )
    return report


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        self.exit(2, "参数无效；请运行 ./scripts/verification-status --help。\n")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = _Parser(
        prog="./scripts/verification-status",
        add_help=False,
        description=(
            "只读查询离线验证，不写文件、不执行检查或迁移；缺少终态记录不证明完成。"
            "退出码：0 通过，1 未通过/未证实，2 参数错误。"
        ),
        epilog=(
            "示例：./scripts/verification-status <run_id> "
            "--runs-dir verification-runs --json"
        ),
    )
    parser.add_argument("-h", "--help", action="help", help="显示中文帮助并退出")
    parser.add_argument("run_id", help="32 位小写十六进制运行标识")
    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=root / "verification-runs",
        help="证据目录",
    )
    parser.add_argument("--json", action="store_true", help="输出脱敏 JSON")
    args = parser.parse_args()
    report = query_status(root, args.runs_dir, args.run_id)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    else:
        print(f"输出格式：{report['format_version']}")
        print(
            f"状态：{STATUS_ZH[report['status']]}（{report['status']}）；原因：{report['reason']}"
        )
        print(
            f"阶段：{PHASE_ZH[report['phase']]}；检查：{report['checks_passed']}/{report['checks_total']}；当前：{report['current_check']}；耗时秒：{report['elapsed_seconds']}"
        )
        print(
            f"控制方退出决定：{report['exit_code']}；当前工作树适用性：{report['applicability']}；测试汇总：{report['tests']}"
        )
        if report["status"] != Status.PASSED:
            print(
                "请等待入口退出或查看同次结论；终态未证实时，需重跑完整入口取得新记录。"
            )
    return 0 if report["status"] == Status.PASSED else 1


if __name__ == "__main__":
    raise SystemExit(main())
