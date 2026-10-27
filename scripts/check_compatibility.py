"""开发期入口兼容组合; 精选清单是唯一权威, 不产生验收结论。"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import NoReturn


@dataclass(frozen=True)
class TestSelection:
    selector: str
    reason: str


@dataclass(frozen=True)
class CheckGroup:
    description: str
    selections: tuple[TestSelection, ...]


class FailureReason(StrEnum):
    EMPTY_SELECTION = "empty_selection"
    MISSING_MODULE = "missing_module"
    MISSING_NODE = "missing_node"
    EMPTY_MODULE = "empty_module"
    LAUNCH_ERROR = "launch_error"


class CheckStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


@dataclass(frozen=True)
class SelectionCount:
    selector: str
    node_count: int

    @property
    def problem(self) -> FailureReason | None:
        if self.node_count:
            return None
        return (
            FailureReason.MISSING_NODE
            if "::" in self.selector
            else FailureReason.EMPTY_MODULE
        )


ALL_GROUP = "all"


CHECK_GROUPS = {
    "acceptance": CheckGroup(
        "验收入口/回执接线",
        (
            TestSelection(
                "tests/test_a2_full_entry.py",
                "一次计划、正常/失败/中断产物与完整入口帮助",
            ),
            TestSelection("tests/test_a3_entry.py", "A3 发布中断及发布前字节复核"),
            TestSelection(
                "tests/test_a4_entry.py", "A4 必需组失败、发布中断与字节绑定"
            ),
            TestSelection(
                "tests/test_a5_entry.py", "A5 必需组失败、发布中断与字节绑定"
            ),
            TestSelection("tests/test_a6_entry.py", "A6 依赖、嵌套回执隔离及发布失败"),
            TestSelection("tests/test_a7_entry.py", "A7 依赖、嵌套回执隔离及发布失败"),
            TestSelection("tests/test_a8_entry.py", "A8 依赖、嵌套回执隔离及发布失败"),
            TestSelection(
                "tests/test_a9_entry.py", "A9 Read 独立契约、回执隔离及发布失败"
            ),
            TestSelection(
                "tests/test_a10_entry.py", "A10 接线、可选/必需组独立性及最终发布失败"
            ),
            TestSelection("tests/test_verification_run.py", "登记扩展与非法登记拒绝"),
            TestSelection(
                "tests/test_verification_compatibility.py",
                "独立历史终端字节、退出码和产物数量",
            ),
            TestSelection(
                "tests/test_verification_status.py", "可信终态、历史兼容与失败/中断查询"
            ),
        ),
    ),
    "cli": CheckGroup(
        "CLI 注册/导入链",
        (
            TestSelection(
                "tests/test_cli_help.py", "已安装根命令/契约帮助及禁网络/SQLite 守卫"
            ),
            TestSelection(
                "tests/test_cli_import_compatibility.py",
                "新旧命令冷进程帮助与禁 I/O 导入链",
            ),
            TestSelection(
                "tests/test_fixture_cli.py", "fixture 注册、查询、帮助与缺失数据库"
            ),
            TestSelection(
                "tests/test_fixture_pdf_cli.py", "PDF/backend 登记、查询及原字节行为"
            ),
            TestSelection("tests/test_audit_cli.py", "audit 查询、帮助与无写入边界"),
            TestSelection("tests/test_audit_matrix_cli.py", "摘要矩阵命令及安全输出"),
            TestSelection(
                "tests/test_audit_resume_cli.py", "resume/replay 帮助、继续和只读回放"
            ),
            TestSelection(
                "tests/test_fixture_audit_references.py",
                "fixture 与 audit 的完整历史引用",
            ),
        ),
    ),
}


def select_tests(group: str) -> tuple[str, ...]:
    """有序并集; 不扫描仓库或隐式扩大到全量 pytest。"""
    groups = tuple(CHECK_GROUPS) if group == ALL_GROUP else (group,)
    return _ordered_unique(
        selection.selector
        for name in groups
        for selection in CHECK_GROUPS[name].selections
    )


def selection_documentation() -> str:
    """帮助与开发文档共用的选择说明。"""
    lines = ["| 组合 | 测试选择 | 选择理由 |", "| --- | --- | --- |"]
    for name, group in CHECK_GROUPS.items():
        lines.extend(
            f"| {name}（{group.description}） | `{selection.selector}` | "
            f"{selection.reason} |"
            for selection in group.selections
        )
    lines.append(f"\n`{ALL_GROUP}` 是上面所有组合的有序并集，同一节点只执行一次。")
    return "\n".join(lines)


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _collection_counts(
    selections: tuple[str, ...], node_ids: Iterable[str]
) -> tuple[SelectionCount, ...]:
    nodes = _ordered_unique(node_ids)
    return tuple(
        SelectionCount(
            selection,
            sum(
                node == selection
                or node.startswith(selection + "::")
                or node.startswith(selection + "[")
                for node in nodes
            ),
        )
        for selection in selections
    )


def _pytest_environment(environment: Mapping[str, str]) -> dict[str, str]:
    isolated = dict(environment)
    for key in (
        "PAPER_RADAR_TEST_RECEIPT",
        "PAPER_RADAR_TEST_RUN_ID",
        "PYTEST_ADDOPTS",
        "PYTEST_PLUGINS",
    ):
        isolated.pop(key, None)
    isolated.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", PYTHONDONTWRITEBYTECODE="1")
    return isolated


def _print_result(exit_code: int, started: float, *, include_uv: bool = False) -> None:
    result = CheckStatus.PASSED if exit_code == 0 else CheckStatus.FAILED
    title, duration = (
        ("入口结果", "总耗时（含 uv）") if include_uv else ("结果", "耗时")
    )
    print(
        f"{title}：{result}；退出码：{exit_code}；"
        f"{duration}：{time.monotonic() - started:.2f}s",
        flush=True,
    )


def run_checks(root: Path, selections: tuple[str, ...]) -> int:
    """在独立命令进程运行显式选择; 不接入正式 run_id/回执协议。"""
    started = time.monotonic()
    exit_code = 1
    selections = _ordered_unique(selections)
    print(f"选择项：{len(selections)}", flush=True)
    for selection in selections:
        print(f"  {selection}", flush=True)
    try:
        if not selections:
            print(
                f"{FailureReason.EMPTY_SELECTION}：测试选择为空；请修正组合定义。",
                file=sys.stderr,
            )
            return exit_code
        for selection in selections:
            if not (root / selection.split("::", 1)[0]).is_file():
                print(
                    f"{FailureReason.MISSING_MODULE}：{selection}；请修正组合定义。",
                    file=sys.stderr,
                )
                return exit_code
        exit_code = _run_pytest(root, selections)
        return exit_code
    finally:
        _print_result(exit_code, started)


def _run_pytest(root: Path, selections: tuple[str, ...]) -> int:
    # 仅在专用命令进程中应用已计算的环境; 不继承正式回执或外部 pytest 选项。
    environment = _pytest_environment(os.environ)
    os.environ.clear()
    os.environ.update(environment)
    sys.dont_write_bytecode = True

    import pytest

    class SelectionReport:
        @pytest.hookimpl(trylast=True)
        def pytest_collection_modifyitems(self, items: list[pytest.Item]) -> None:
            # pytest 对象按完整 nodeid 去重; 与字符串选择的并集分开处理。
            items[:] = list({item.nodeid: item for item in items}.values())

        def pytest_collection_finish(self, session: pytest.Session) -> None:
            counts = _collection_counts(selections, (i.nodeid for i in session.items))
            for count in counts:
                print(
                    f"实际选择：{count.selector}；节点数：{count.node_count}",
                    flush=True,
                )
                if count.problem is not None and not session.testsfailed:
                    raise pytest.UsageError(
                        f"{count.problem}：{count.selector} 没有测试节点；"
                        "请修正组合定义。"
                    )
            print(f"实际节点总数：{len(session.items)}（已去重）", flush=True)

    previous = Path.cwd()
    try:
        os.chdir(root)
        return int(
            pytest.main(
                [
                    "-q",
                    "--tb=short",
                    "-p",
                    "no:cacheprovider",
                    "-p",
                    "no:scripts.a2_test_receipt",
                    *selections,
                ],
                plugins=[SelectionReport()],
            )
        )
    finally:
        os.chdir(previous)


class _Parser(argparse.ArgumentParser):
    def format_help(self) -> str:
        return super().format_help().replace("usage: ", "用法：", 1)

    def error(self, message: str) -> NoReturn:
        if message.startswith("the following arguments are required:"):
            cause = "缺少组合名"
        elif message.startswith("argument group: invalid choice:"):
            cause = "组合名不受支持"
        elif message.startswith("unrecognized arguments:"):
            cause = "未知选项或多余参数"
        else:
            cause = "参数格式不正确"
        self.exit(
            2,
            f"参数错误：{cause}；请运行 ./scripts/check-compatibility --help。\n",
        )


def main() -> int:
    parser = _Parser(
        prog="./scripts/check-compatibility",
        add_help=False,
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
            "引导需要 Python >=3.12；项目环境缺失时使用宿主 python3，"
            "两者均不可用时请先准备解释器。\n"
            "本入口只运行显式选择，不运行完整门禁；"
            "最终仍须 ./scripts/check-offline。\n\n" + selection_documentation()
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    arguments = parser.add_argument_group("参数与选项")
    arguments.add_argument("-h", "--help", action="help", help="显示中文帮助并退出")
    arguments.add_argument(
        "group",
        choices=(*CHECK_GROUPS, ALL_GROUP),
        help="组合名；all 为全部组合的有序并集",
    )
    options = parser.parse_args()
    started = time.monotonic()
    exit_code = 1
    try:
        exit_code = subprocess.call(
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
        return exit_code
    except KeyboardInterrupt:
        exit_code = 2
        return exit_code
    except OSError:
        print(
            f"{FailureReason.LAUNCH_ERROR}：无法启动 uv；请检查离线环境。",
            file=sys.stderr,
        )
        return exit_code
    finally:
        _print_result(exit_code, started, include_uv=True)


if __name__ == "__main__":
    raise SystemExit(main())
