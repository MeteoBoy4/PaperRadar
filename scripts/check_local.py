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
    uv_prefix = ("uv", "run", "--offline", "--locked")
    for check in default_checks():
        if check.id not in {"format", "lint"}:
            continue
        if check.command[: len(uv_prefix)] != uv_prefix:
            print(
                "invalid_check_plan：Ruff 检查计划缺少锁定离线 uv 前缀；"
                "请检查 default_checks() 的 format/lint 定义。",
                file=sys.stderr,
            )
            return 1
        module_command = check.command[len(uv_prefix) :]
        started = time.monotonic()
        print(f"执行 {check.id}：{' '.join(module_command)}", flush=True)
        result = subprocess.call(
            [sys.executable, "-B", "-m", *module_command],
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
        f"docs：{'失败' if problems else '通过'}；"
        f"耗时 {time.monotonic() - started:.3f}s",
        flush=True,
    )
    return int(failed or bool(problems))


def _export_index(root: Path, snapshot: Path) -> None:
    additions = []
    for visibility in ("--ita-visible-in-index", "--ita-invisible-in-index"):
        result = subprocess.run(
            [
                "git",
                "diff",
                "--cached",
                "--name-only",
                "--diff-filter=A",
                "-z",
                visibility,
            ],
            cwd=root,
            capture_output=True,
            check=True,
        )
        additions.append(set(result.stdout.split(b"\0")))
    if additions[0] != additions[1]:
        raise ValueError(
            "intent_to_add：存在仅登记意图、尚未暂存内容的路径；请先完整暂存或撤销意图。"
        )
    listing = subprocess.run(
        ["git", "ls-files", "--stage", "-z"],
        cwd=root,
        capture_output=True,
        check=True,
    ).stdout
    entries: list[tuple[Path, bytes, int]] = []
    for entry in listing.split(b"\0"):
        if not entry:
            continue
        fields, _, raw_path = entry.partition(b"\t")
        mode, object_id, stage = fields.split()
        if stage != b"0" or mode not in {b"100644", b"100755", b"120000"}:
            raise ValueError(
                "unsupported_index_entry：不支持未合并条目或 submodule；"
                "请先解决冲突或移除暂存的 submodule。"
            )
        try:
            relative = raw_path.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError(
                "non_utf8_path：暂存路径必须为 UTF-8；请重命名后重新暂存。"
            ) from error
        path = snapshot / relative
        if not relative or not path.resolve().is_relative_to(snapshot):
            raise ValueError(
                "invalid_index_path：暂存路径不在快照内；请移除异常条目后重新暂存。"
            )
        entries.append((path, object_id, int(mode, 8)))
    # 直接读取对象字节:不执行 attributes 的 smudge/编码/EOL 转换或 replace refs。
    objects = subprocess.run(
        ["git", "--no-replace-objects", "cat-file", "--batch"],
        input=b"".join(object_id + b"\n" for _, object_id, _ in entries),
        cwd=root,
        capture_output=True,
        check=True,
    ).stdout
    cursor = 0
    symlinks: list[tuple[Path, str]] = []
    for path, object_id, mode_bits in entries:
        header_end = objects.index(b"\n", cursor)
        actual_id, kind, raw_size = objects[cursor:header_end].split()
        if actual_id != object_id or kind != b"blob":
            raise ValueError(
                "invalid_index_object：暂存对象不是原始 blob；"
                "请检查 Git 对象完整性并重新暂存。"
            )
        start = header_end + 1
        end = start + int(raw_size)
        if end >= len(objects) or objects[end : end + 1] != b"\n":
            raise ValueError(
                "invalid_index_object：暂存 blob 不完整；"
                "请检查 Git 对象完整性并重新暂存。"
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        if mode_bits == 0o120000:
            try:
                symlinks.append((path, objects[start:end].decode("utf-8")))
            except UnicodeDecodeError as error:
                raise ValueError(
                    "invalid_index_symlink：符号链接目标必须为 UTF-8；"
                    "请修正目标后重新暂存。"
                ) from error
        else:
            path.write_bytes(objects[start:end])
            path.chmod(mode_bits & 0o777)
        cursor = end + 1
    if cursor != len(objects):
        raise ValueError(
            "invalid_index_object：暂存 blob 输出不完整；"
            "请检查 Git 对象完整性并重新暂存。"
        )
    # 全部普通文件写完后才创建链接,避免父目录链接引导写入快照外。
    for path, target in symlinks:
        path.symlink_to(target)
    for path, _ in symlinks:
        try:
            try:
                resolved = path.resolve(strict=True)
            except FileNotFoundError:
                # 仓库可能保留悬空的内部 skills 链接;其目标仍须位于快照内。
                resolved = path.resolve()
        except (OSError, RuntimeError) as error:
            raise ValueError(
                "invalid_index_symlink：符号链接成环或无法解析；"
                "请修正链接目标后重新暂存。"
            ) from error
        if not resolved.is_relative_to(snapshot):
            raise ValueError(
                "outside_repository：暂存符号链接指向快照外；"
                "请改为仓库内相对目标或移除该暂存链接。"
            )


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
        _export_index(root, snapshot)
        if not (snapshot / "pyproject.toml").is_file():
            raise ValueError(
                "missing_ruff_config：暂存快照缺少 pyproject.toml；"
                "请暂存项目配置后重试，不能沿用工作树配置或默认规则。"
            )
        yield snapshot


class _Parser(argparse.ArgumentParser):
    def format_help(self) -> str:
        return super().format_help().replace("usage: ", "用法：", 1)

    def error(self, message: str) -> NoReturn:
        if message.startswith("unrecognized arguments:"):
            reason = "未知选项或多余参数"
        elif message.startswith("argument action: invalid choice:"):
            reason = "action 不受支持（可用 check、install、uninstall）"
        elif message == "--staged only applies to check":
            reason = "--staged 只适用于 check；请移除该选项或使用 check --staged"
        else:
            reason = "参数格式不正确"
        self.exit(2, f"参数错误：{reason}；请运行 ./scripts/check-local --help。\n")


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
    arguments = parser.add_argument_group("参数与选项")
    arguments.add_argument("-h", "--help", action="help", help="显示中文帮助并退出")
    arguments.add_argument(
        "action",
        nargs="?",
        choices=("check", "install", "uninstall"),
        default="check",
        help="检查（默认）、显式安装或安全卸载 hook",
    )
    arguments.add_argument(
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
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1
    except (OSError, ImportError, subprocess.CalledProcessError) as error:
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
