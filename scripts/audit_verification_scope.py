"""开发命令: 固定范围只读审计, 不属于正式验收计划。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, NoReturn

from scripts.verification_scope_audit import audit_scopes
from scripts.verification_scope_collection import collect_counts
from scripts.verification_scope_registry import load_scopes


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        self.exit(2, "参数无效；请运行 ./scripts/audit-verification-scope --help。\n")


def _print_report(report: dict[str, Any]) -> None:
    print(
        "固定 scope 只读审计：" + ("匹配" if report["exit_code"] == 0 else "发现问题")
    )
    print("仅供维护审阅；收集不代表实际执行或验收通过。")
    print("建议处理顺序：" + " → ".join(report["order"]))
    for path, downstream in report["downstream"].items():
        print(f"修改 {path} 后需重算下游登记：" + ("、".join(downstream) or "无"))
    for record in report["files"]:
        if record["reason"] != "ok":
            print(
                f"{record['group']} {record['role']} {record['path']}: "
                f"{record['reason']}"
            )
            print(
                f"  登记：{record['expected_sha256']} 当前：{record['actual_sha256']}"
            )
    for issue in report["issues"]:
        print(f"{issue['group']} {issue['path']}: {issue['reason']}")
    for record in report["counts"]:
        print(
            f"{record['group']} {record['path']}: 固定用例 {record['expected_cases']}"
        )
    print("受影响组：" + ("、".join(report["affected_groups"]) or "无"))
    collection = report["collection"]
    print("收集结果：" + collection["reason"] + "；真实执行：not_run")
    if collection["reason"] != "not_requested":
        for path, actual in collection.get("modules", {}).items():
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
    try:
        report = audit_scopes(root, load_scopes(root))
    except Exception:
        # registry 导入失败也不得回显源码、参数或异常文本。
        report = audit_scopes(root, ())
        report["issues"] = [
            dict(group="registry", path="scripts", reason="registry_unavailable")
        ]
    report["collection"] = dict(reason="not_requested", execution="not_run")
    if arguments.collect:
        if report["exit_code"]:
            report["collection"]["reason"] = "audit_failed"
        else:
            expected = {r["path"]: r["expected_cases"] for r in report["counts"]}
            report["collection"] = collect_counts(root, expected)
            if report["collection"]["reason"] != "ok":
                report["exit_code"] = 1
                mismatched = {
                    p
                    for p, n in expected.items()
                    if report["collection"]["modules"].get(p) != n
                }
                report["affected_groups"] = sorted(
                    {r["group"] for r in report["counts"] if r["path"] in mismatched}
                )
    if arguments.json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    else:
        _print_report(report)
    return int(report["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
