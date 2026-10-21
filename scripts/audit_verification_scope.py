"""开发命令: 固定范围只读审计, 不属于正式验收计划。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import NoReturn

from scripts.verification_scope_audit import (
    AuditReason,
    AuditReport,
    CollectionResult,
    Scope,
    audit_scopes,
    collection_targets,
    merge_collection,
)
from scripts.verification_scope_collection import collect_counts
from scripts.verification_scope_registry import load_scopes


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        if message.startswith("unrecognized arguments:"):
            reason = AuditReason.UNKNOWN_ARGUMENT
            explanation = "存在不支持的参数"
        elif message.startswith("argument "):
            reason = AuditReason.INVALID_OPTION_VALUE
            explanation = "选项值或组合无效"
        else:
            reason = AuditReason.INVALID_ARGUMENTS
            explanation = "参数格式无效"
        self.exit(
            2,
            f"{explanation}（{reason}）；"
            "请运行 ./scripts/audit-verification-scope --help。\n",
        )


def _print_report(report: AuditReport) -> None:
    print(
        "固定 scope 只读审计：" + ("匹配" if report["exit_code"] == 0 else "发现问题")
    )
    print("仅供维护审阅；收集不代表实际执行或验收通过。")
    print("建议处理顺序：" + " → ".join(report["order"]))
    for path, downstream in report["downstream"].items():
        print(f"修改 {path} 后需重算下游登记：" + ("、".join(downstream) or "无"))
    for record in report["files"]:
        if record["reason"] != AuditReason.OK:
            print(
                f"{record['group']} {record['role']} {record['path']}: "
                f"{record['reason']}"
            )
            print(
                f"  登记：{record['expected_sha256']} 当前：{record['actual_sha256']}"
            )
    for issue in report["issues"]:
        print(f"{issue['group']} {issue['path']}: {issue['reason']}")
    for count in report["counts"]:
        print(f"{count['group']} {count['path']}: 固定用例 {count['expected_cases']}")
    print("受影响组：" + ("、".join(report["affected_groups"]) or "无"))
    collection = report["collection"]
    print("收集结果：" + collection["reason"] + "；真实执行：not_run")
    if collection["reason"] != AuditReason.NOT_REQUESTED:
        for path, actual in collection["modules"].items():
            print(f"收集 {path}: {actual}")
    if report["exit_code"]:
        print(
            "请逐项审查原因与候选哈希，按顺序人工修改 scope 后重跑；本工具不写回登记。"
        )


def main() -> int:
    parser = _Parser(
        description=(
            "只读审计固定 scope 的哈希、计数与引用链；不修改文件、Git 索引或正式回执。"
            "仅作开发审阅，不表示验收通过。"
            "退出码：0 匹配，1 漂移/无法核验，2 参数错误。"
        ),
        epilog="示例：./scripts/audit-verification-scope --collect --json",
    )
    parser.add_argument("--json", action="store_true", help="输出脱敏 JSON 报告")
    parser.add_argument(
        "--collect",
        action="store_true",
        help="独立进程核对固定模块收集数量，不执行测试",
    )
    arguments = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    scopes: tuple[Scope, ...] = ()
    try:
        scopes = load_scopes(root)
        report = audit_scopes(root, scopes)
    except Exception:
        # registry 导入失败也不得回显源码、参数或异常文本。
        report = audit_scopes(root, ())
        report["issues"] = [
            dict(
                group="registry",
                path="scripts",
                reason=AuditReason.REGISTRY_UNAVAILABLE,
            )
        ]
    if arguments.collect:
        expected = collection_targets(report)
        collection: CollectionResult
        if expected is None:
            collection = dict(
                reason=AuditReason.AUDIT_FAILED, execution="not_run", modules={}
            )
        else:
            collection = collect_counts(root, expected)
        report = merge_collection(report, scopes, collection)
    if arguments.json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    else:
        _print_report(report)
    return int(report["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
