"""开发期入口兼容组合; 精选清单是唯一权威, 不产生验收结论。"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CheckGroup:
    description: str
    selections: tuple[tuple[str, str], ...]


CHECK_GROUPS = {
    "acceptance": CheckGroup(
        "验收入口/回执接线",
        (
            (
                "tests/test_a2_full_entry.py",
                "一次计划、正常/失败/中断产物与完整入口帮助",
            ),
            ("tests/test_a3_entry.py", "A3 发布中断及发布前字节复核"),
            ("tests/test_a4_entry.py", "A4 必需组失败、发布中断与字节绑定"),
            ("tests/test_a5_entry.py", "A5 必需组失败、发布中断与字节绑定"),
            ("tests/test_a6_entry.py", "A6 依赖、嵌套回执隔离及发布失败"),
            ("tests/test_a7_entry.py", "A7 依赖、嵌套回执隔离及发布失败"),
            ("tests/test_a8_entry.py", "A8 依赖、嵌套回执隔离及发布失败"),
            ("tests/test_a9_entry.py", "A9 Read 独立契约、回执隔离及发布失败"),
            ("tests/test_a10_entry.py", "A10 接线、可选/必需组独立性及最终发布失败"),
            ("tests/test_verification_run.py", "登记扩展与非法登记拒绝"),
            (
                "tests/test_verification_compatibility.py",
                "独立历史终端字节、退出码和产物数量",
            ),
            ("tests/test_verification_status.py", "可信终态、历史兼容与失败/中断查询"),
        ),
    ),
    "cli": CheckGroup(
        "CLI 注册/导入链",
        (
            ("tests/test_cli_help.py", "已安装根命令/契约帮助及禁网络/SQLite 守卫"),
            (
                "tests/test_cli_import_compatibility.py",
                "新旧命令冷进程帮助与禁 I/O 导入链",
            ),
            ("tests/test_fixture_cli.py", "fixture 注册、查询、帮助与缺失数据库"),
            ("tests/test_fixture_pdf_cli.py", "PDF/backend 登记、查询及原字节行为"),
            ("tests/test_audit_cli.py", "audit 查询、帮助与无写入边界"),
            ("tests/test_audit_matrix_cli.py", "摘要矩阵命令及安全输出"),
            ("tests/test_audit_resume_cli.py", "resume/replay 帮助、继续和只读回放"),
            (
                "tests/test_fixture_audit_references.py",
                "fixture 与 audit 的完整历史引用",
            ),
        ),
    ),
}


def select_tests(group: str) -> tuple[str, ...]:
    """有序并集; 不扫描仓库或隐式扩大到全量 pytest。"""
    groups = tuple(CHECK_GROUPS) if group == "all" else (group,)
    return tuple(
        dict.fromkeys(
            selection
            for name in groups
            for selection, _ in CHECK_GROUPS[name].selections
        )
    )


def selection_documentation() -> str:
    """帮助与开发文档共用的选择说明。"""
    lines = ["| 组合 | 测试选择 | 选择理由 |", "| --- | --- | --- |"]
    for name, group in CHECK_GROUPS.items():
        lines.extend(
            f"| {name}（{group.description}） | `{selection}` | {reason} |"
            for selection, reason in group.selections
        )
    lines.append("\n`all` 是上面所有组合的有序并集，同一节点只执行一次。")
    return "\n".join(lines)


def run_checks(root: Path, selections: tuple[str, ...]) -> int:
    """在独立命令进程运行显式选择; 不接入正式 run_id/回执协议。"""
    started = time.monotonic()
    code = 1
    selections = tuple(dict.fromkeys(selections))
    print(f"选择项：{len(selections)}", flush=True)
    for selection in selections:
        print(f"  {selection}", flush=True)
    try:
        if not selections:
            print("empty_selection：测试选择为空；请修正组合定义。", file=sys.stderr)
            return code
        for selection in selections:
            if not (root / selection.split("::", 1)[0]).is_file():
                print(f"missing_module：{selection}；请修正组合定义。", file=sys.stderr)
                return code

        # 不继承外层正式回执或任意 pytest 参数/插件, 防止少跑与证据污染。
        for key in (
            "PAPER_RADAR_TEST_RECEIPT",
            "PAPER_RADAR_TEST_RUN_ID",
            "PYTEST_ADDOPTS",
            "PYTEST_PLUGINS",
        ):
            os.environ.pop(key, None)
        os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
        sys.dont_write_bytecode = True

        import pytest

        class SelectionReport:
            @pytest.hookimpl(trylast=True)
            def pytest_collection_modifyitems(self, items: list[pytest.Item]) -> None:
                # 模块与节点选择可以重叠, 参数化用例按完整 nodeid 去重。
                items[:] = list({item.nodeid: item for item in items}.values())

            def pytest_collection_finish(self, session: pytest.Session) -> None:
                nodes = [item.nodeid for item in session.items]
                for selection in selections:
                    count = sum(
                        node == selection
                        or node.startswith(selection + "::")
                        or node.startswith(selection + "[")
                        for node in nodes
                    )
                    print(f"实际选择：{selection}；节点数：{count}", flush=True)
                    if not count and not session.testsfailed:
                        reason = (
                            "missing_node (not found)"
                            if "::" in selection
                            else "empty_module"
                        )
                        raise pytest.UsageError(
                            f"{reason}：{selection} 没有测试节点；请修正组合定义。"
                        )
                print(f"实际节点总数：{len(nodes)}（已去重）", flush=True)

        previous = Path.cwd()
        try:
            os.chdir(root)
            code = int(
                pytest.main(
                    [
                        "-q",
                        "--tb=short",
                        "-p",
                        "no:cacheprovider",
                        "-p",
                        "no:scripts.a2_test_receipt",
                        "-o",
                        "addopts=--strict-config --strict-markers",
                        *selections,
                    ],
                    plugins=[SelectionReport()],
                )
            )
        finally:
            os.chdir(previous)
        return code
    finally:
        result = "passed" if code == 0 else "failed"
        print(
            f"结果：{result}；退出码：{code}；耗时：{time.monotonic() - started:.2f}s",
            flush=True,
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="./scripts/check-compatibility",
        description=(
            "开发期离线入口兼容检查。副作用：测试使用临时目录/数据库，"
            "不访问实时网络或用户数据库；不发布验收结论，不写 verification-runs/。"
            "实际检查通过 uv run --offline --locked 执行，可能同步项目环境。"
        ),
        epilog=(
            "输出：先打印有序选择，再打印实际模块/节点数、pytest 结果、退出码与耗时。\n"
            "退出码：0=所选测试通过；1=空选择/缺失模块/测试失败/启动失败；"
            "2=参数错误或中断；其他非零沿用 uv/pytest。\n"
            "未知参数返回 2；请使用 --help。"
            "帮助仅打印中文，不启动 uv 或检查，不写文件。\n"
            "本入口只运行显式选择，不运行完整门禁；"
            "最终仍须 ./scripts/check-offline。\n\n" + selection_documentation()
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "group",
        choices=(*CHECK_GROUPS, "all"),
        help="组合名；all 为全部组合的有序并集",
    )
    options = parser.parse_args()
    started = time.monotonic()
    code = 1
    try:
        code = subprocess.call(
            [
                "uv",
                "run",
                "--offline",
                "--locked",
                "python",
                "-B",
                "-c",
                "import sys; from pathlib import Path; "
                "from scripts.check_compatibility import run_checks, select_tests; "
                "raise SystemExit(run_checks(Path.cwd(), select_tests(sys.argv[1])))",
                options.group,
            ],
            cwd=Path(__file__).resolve().parents[1],
        )
        return code
    except KeyboardInterrupt:
        code = 2
        return code
    except OSError:
        print(
            "launch_error：无法启动 uv；请检查离线环境。",
            file=sys.stderr,
        )
        return code
    finally:
        result = "passed" if code == 0 else "failed"
        print(
            f"入口结果：{result}；退出码：{code}；"
            f"总耗时（含 uv）：{time.monotonic() - started:.2f}s",
            flush=True,
        )


if __name__ == "__main__":
    raise SystemExit(main())
