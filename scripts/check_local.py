"""轻量本地检查与显式 hook 生命周期;不产生正式验收回执。"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import NoReturn

from scripts.offline_evidence import default_checks


def run_checks(root: Path) -> int:
    """在已经锁定的环境中运行同源 Ruff 计划和活文档检查。"""
    from scripts.live_document_links import check_document_links

    environment = dict(os.environ)
    for key in ("PAPER_RADAR_TEST_RECEIPT", "PAPER_RADAR_TEST_RUN_ID"):
        environment.pop(key, None)
    environment.update(PYTHONDONTWRITEBYTECODE="1", RUFF_NO_CACHE="true")
    failed = False
    for check in default_checks():
        if check.id not in {"format", "lint"}:
            continue
        started = time.monotonic()
        print(f"执行 {check.id}：{' '.join(check.command[4:])}", flush=True)
        result = subprocess.call(
            [sys.executable, "-B", "-m", *check.command[4:]],
            cwd=root,
            env=environment,
        )
        failed |= result != 0
        print(
            f"{check.id}：退出码 {result}；耗时 {time.monotonic() - started:.3f}s",
            flush=True,
        )
    started = time.monotonic()
    problems = check_document_links(root)
    for problem in problems:
        print(problem, flush=True)
    print(
        f"docs：{'failed' if problems else 'passed'}；"
        f"耗时 {time.monotonic() - started:.3f}s",
        flush=True,
    )
    return int(failed or bool(problems))


@contextmanager
def checked_tree(root: Path, staged: bool) -> Iterator[Path]:
    if not staged:
        yield root
        return
    temporary_root = Path(tempfile.gettempdir()).resolve()
    if temporary_root.is_relative_to(root):
        raise ValueError(
            "temporary_root：TMPDIR 必须位于工作树外；请设置 TMPDIR=/tmp。"
        )
    with tempfile.TemporaryDirectory(
        prefix="paper-radar-index-", dir=temporary_root
    ) as name:
        snapshot = Path(name)
        subprocess.run(
            ["git", "checkout-index", "--all", f"--prefix={snapshot}/"],
            cwd=root,
            check=True,
        )
        # 不让 Ruff 或文档解析通过 index 中的符号链接读取工作树外材料。
        for path in snapshot.rglob("*"):
            if path.is_symlink() and not path.resolve().is_relative_to(snapshot):
                raise ValueError("outside_repository：暂存符号链接指向快照外。")
        yield snapshot


class _Parser(argparse.ArgumentParser):
    def format_help(self) -> str:
        return super().format_help().replace("usage: ", "用法：", 1)

    def error(self, message: str) -> NoReturn:
        self.exit(2, "参数错误：请运行 ./scripts/check-local --help。\n")


def main(root: Path | None = None) -> int:
    root = (root or Path.cwd()).resolve()
    parser = _Parser(
        prog="./scripts/check-local",
        add_help=False,
        description="轻量本地检查：Ruff format check、Ruff lint、活文档本地链接/锚点。",
        epilog=(
            "默认检查工作树；只读指不改源码、index 或提交；"
            "uv run --offline --locked 可能同步锁定环境。缓存禁用，临时材料清理。"
            "完整离线门禁仍须用户明确授权；"
            "本入口不运行 mypy/pytest/兼容检查或正式验收。"
        ),
    )
    parser.add_argument("-h", "--help", action="help", help="显示中文帮助并退出")
    parser.add_argument(
        "action",
        nargs="?",
        choices=("check", "install", "uninstall"),
        default="check",
        help="检查（默认）、显式安装或安全卸载 hook",
    )
    parser.add_argument(
        "--staged", action="store_true", help="检查 index 的树外临时快照；不使用 stash"
    )
    options = parser.parse_args()
    started = time.monotonic()
    try:
        if options.action != "check":
            from scripts.local_hooks import manage_hook

            if options.staged:
                parser.error("--staged only applies to check")
            print(manage_hook(root, install=options.action == "install"))
            return 0
        command = (
            "from pathlib import Path; import sys; "
            "from scripts.check_local import run_checks; "
            "raise SystemExit(run_checks(Path(sys.argv[1])))"
        )
        print(f"检查模式：{'staged' if options.staged else '工作树'}", flush=True)
        with checked_tree(root, options.staged) as selected:
            result = subprocess.call(
                [
                    "uv",
                    "run",
                    "--offline",
                    "--locked",
                    "python",
                    "-B",
                    "-c",
                    command,
                    str(selected),
                ],
                cwd=Path(__file__).resolve().parents[1],
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
        if result:
            print(
                "检查失败；环境缺失时请运行 "
                "uv run --offline --locked python --version 准备环境。"
            )
        return result
    except (OSError, ImportError, ValueError, subprocess.CalledProcessError) as error:
        print(
            f"launch_error：{error}；请检查 uv / Git 可用，"
            "运行 uv run --offline --locked python --version 准备环境。",
            file=sys.stderr,
        )
        return 1
    finally:
        print(f"入口总耗时（含 uv）：{time.monotonic() - started:.3f}s", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
