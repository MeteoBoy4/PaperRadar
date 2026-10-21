"""固定解释器及临时根的独立开发检查, 不属于验收 scope。"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import shlex
import stat
import subprocess
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import NoReturn

from scripts.dev_environment_probes import Probes, read_temporary_root

MIN_AVAILABLE_GIB = 5
MIN_AVAILABLE_BYTES = MIN_AVAILABLE_GIB * 1024**3


class Reason(StrEnum):
    OK = "ok"
    TEMPORARY_UNKNOWN = "temporary_unknown"
    NOT_WRITABLE = "not_writable"
    GIT_NOT_ISOLATED = "git_not_isolated"
    GIT_UNKNOWN = "git_unknown"
    QUOTA_UNKNOWN = "quota_unknown"
    CAPACITY_UNKNOWN = "capacity_unknown"
    SPACE_INSUFFICIENT = "space_insufficient"
    INODES_INSUFFICIENT = "inodes_insufficient"
    RESIDUE_PRESENT = "residue_present"
    RESIDUE_UNKNOWN = "residue_unknown"
    PYTHON_UNKNOWN = "python_unknown"
    PYTHON_MISMATCH = "python_mismatch"


GUIDANCE = {
    Reason.OK: "检查通过。",
    Reason.TEMPORARY_UNKNOWN: "临时根不可读取；请选择可访问且位于 Git 工作树外的目录。",
    Reason.NOT_WRITABLE: "临时根不可写；请检查目录权限或选择其他临时根。",
    Reason.GIT_NOT_ISOLATED: "临时根未与 Git 工作树隔离；请选择仓库外的临时根。",
    Reason.GIT_UNKNOWN: "无法核实 Git 隔离；请确认 git 可用并在该目录手动核对。",
    Reason.QUOTA_UNKNOWN: (
        "配额未知；只能报告 statvfs 的文件系统余量，"
        f"不能确认满足 {MIN_AVAILABLE_GIB} GiB 阈值。"
        "请核实用户配额或选择可读取配额的临时根。"
    ),
    Reason.CAPACITY_UNKNOWN: "无法读取容量或 inode；请检查临时根的可访问性。",
    Reason.SPACE_INSUFFICIENT: (
        f"有效可用空间未大于 {MIN_AVAILABLE_GIB} GiB；请释放空间或选择其他临时根。"
    ),
    Reason.INODES_INSUFFICIENT: (
        "可用 inode 已耗尽；请释放残留或选择其他临时根。此项仅提示，不导致失败。"
    ),
    Reason.RESIDUE_PRESENT: (
        "存在 pytest 残留（含正常保留的会话）；仅提示，不导致失败。"
        "如需清理，请确认没有 pytest 运行后手动执行 cleanup_command。"
    ),
    Reason.RESIDUE_UNKNOWN: (
        "无法完整统计 pytest 残留；体积未知或仅为部分下界，请手动核对权限及符号链接。"
        "此项仅提示，不导致失败；清理须在没有 pytest 运行时手动执行。"
    ),
    Reason.PYTHON_UNKNOWN: (
        "项目解释器版本未知；请检查 .python-version 和环境中的 bin/python，"
        "再使用 uv run --offline --locked 同步环境。"
    ),
    Reason.PYTHON_MISMATCH: (
        "项目解释器版本与 .python-version 不一致；"
        "请使用 uv run --offline --locked 同步环境。"
    ),
}


@dataclass(frozen=True)
class CheckResult:
    reason: Reason
    facts: dict[str, object]


@dataclass(frozen=True)
class Report:
    checks: dict[str, CheckResult]

    @property
    def exit_code(self) -> int:
        return int(
            any(
                check.reason
                not in {
                    Reason.OK,
                    Reason.RESIDUE_PRESENT,
                    Reason.RESIDUE_UNKNOWN,
                    Reason.INODES_INSUFFICIENT,
                }
                for check in self.checks.values()
            )
        )


def _interpreter(project: Path) -> CheckResult:
    environment = Path(os.environ.get("UV_PROJECT_ENVIRONMENT", ".venv"))
    if not environment.is_absolute():
        environment = project / environment
    facts: dict[str, object] = {
        "path": str(environment),
        "expected": None,
        "actual": None,
    }
    try:
        expected = (project / ".python-version").read_text(encoding="utf-8").strip()
        result = subprocess.run(
            [
                str(environment / "bin/python"),
                "-I",
                "-S",
                "-B",
                "-c",
                "import sys; print('.'.join(map(str, sys.version_info[:3])))",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        actual = result.stdout.strip()
        if not re.fullmatch(r"\d+\.\d+", expected) or not re.fullmatch(
            r"\d+\.\d+\.\d+", actual
        ):
            return CheckResult(Reason.PYTHON_UNKNOWN, facts)
        facts.update(expected=expected, actual=actual)
        reason = (
            Reason.OK
            if actual.rsplit(".", 1)[0] == expected
            else Reason.PYTHON_MISMATCH
        )
        return CheckResult(reason, facts)
    except (OSError, UnicodeError, subprocess.SubprocessError):
        return CheckResult(Reason.PYTHON_UNKNOWN, facts)


def _residue(temporary: Path) -> CheckResult:
    try:
        username = getpass.getuser()
        if not username or Path(username).name != username or "\0" in username:
            return CheckResult(Reason.RESIDUE_UNKNOWN, {"allocated_bytes": None})
        path = temporary / f"pytest-of-{username}"
        if not path.exists() and not path.is_symlink():
            return CheckResult(Reason.OK, {"path": str(path), "allocated_bytes": 0})
        facts: dict[str, object] = {"path": str(path), "allocated_bytes": None}
        if path.is_symlink() or not path.is_dir():
            return CheckResult(Reason.RESIDUE_UNKNOWN, facts)
        pending = [path]
        seen: set[tuple[int, int]] = set()
        size = 0
        unreadable = 0
        while pending:
            current = pending.pop()
            try:
                info = current.lstat()
            except OSError:
                unreadable += 1
                continue
            identity = (info.st_dev, info.st_ino)
            if identity in seen:
                continue
            seen.add(identity)
            size += info.st_blocks * 512
            if stat.S_ISDIR(info.st_mode):
                try:
                    pending.extend(current.iterdir())
                except OSError:
                    unreadable += 1
        facts.update(
            allocated_bytes=size,
            unreadable_entries=unreadable,
            size_complete=unreadable == 0,
            cleanup_command=(
                f"chmod -R u+w {shlex.quote(str(path))}"
                f" && rm -rf -- {shlex.quote(str(path))}"
            ),
        )
        return CheckResult(
            Reason.RESIDUE_UNKNOWN if unreadable else Reason.RESIDUE_PRESENT,
            facts,
        )
    except (OSError, KeyError):
        return CheckResult(Reason.RESIDUE_UNKNOWN, {"allocated_bytes": None})


def _capacity(temporary: Path, probes: Probes) -> dict[str, CheckResult]:
    try:
        capacity = probes.capacity(temporary)
    except OSError:
        return {
            name: CheckResult(Reason.CAPACITY_UNKNOWN, {})
            for name in ("capacity", "inodes")
        }
    try:
        quota = probes.quota(temporary)
    except OSError:
        quota = None
    available = (
        min(capacity.available_bytes, max(0, quota.limit_bytes - quota.used_bytes))
        if quota is not None
        else None
    )
    return {
        "capacity": CheckResult(
            Reason.QUOTA_UNKNOWN
            if available is None
            else (
                Reason.OK
                if available > MIN_AVAILABLE_BYTES
                else Reason.SPACE_INSUFFICIENT
            ),
            {
                "statvfs_available_bytes": capacity.available_bytes,
                "quota_limit_bytes": quota.limit_bytes if quota else None,
                "quota_used_bytes": quota.used_bytes if quota else None,
                "effective_available_bytes": available,
                "required_more_than_bytes": MIN_AVAILABLE_BYTES,
            },
        ),
        "inodes": CheckResult(
            Reason.OK if capacity.available_inodes > 0 else Reason.INODES_INSUFFICIENT,
            {
                "available_inodes": capacity.available_inodes,
            },
        ),
    }


def check_environment(
    project: Path, temporary: Path | None = None, *, probes: Probes | None = None
) -> Report:
    """只读检查; 临时根与系统探测可注入, 不接触用户数据库。"""
    probes = probes or Probes()
    checks = {"interpreter": _interpreter(project)}
    try:
        temporary = (
            temporary if temporary is not None else read_temporary_root()
        ).resolve(strict=True)
        if not temporary.is_dir():
            raise OSError("not_directory")
        checks["temporary"] = CheckResult(
            Reason.OK if probes.writable(temporary) else Reason.NOT_WRITABLE,
            {"path": str(temporary), "temporary_probe": "access_only"},
        )
    except (OSError, RuntimeError):
        checks["temporary"] = CheckResult(
            Reason.TEMPORARY_UNKNOWN,
            {"temporary_probe": "access_only"},
        )
        return Report(checks)
    try:
        checks["git"] = CheckResult(
            Reason.OK if probes.git_isolated(temporary) else Reason.GIT_NOT_ISOLATED,
            {},
        )
    except (OSError, subprocess.SubprocessError):
        checks["git"] = CheckResult(Reason.GIT_UNKNOWN, {})
    checks.update(_capacity(temporary, probes))
    checks["residue"] = _residue(temporary)
    return Report(checks)


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        if message.startswith("the following arguments are required:"):
            cause = "缺少 check 子命令"
        elif message.startswith("argument command: invalid choice:"):
            cause = "仅支持 check 子命令"
        elif message.startswith("unrecognized arguments:"):
            cause = "未知选项或多余参数"
        else:
            cause = "参数格式不正确"
        self.exit(2, f"参数错误：{cause}；请运行 ./scripts/dev-environment --help。\n")


def main(
    argv: list[str] | None = None,
    *,
    project: Path | None = None,
    probes: Probes | None = None,
) -> int:
    parser = _Parser(
        prog="./scripts/dev-environment",
        description=(
            "只读检查项目解释器、临时根、Git 隔离、容量、inode 和 pytest 残留。"
        ),
        epilog=(
            "不联网、不安装、不删除、不修改文件，不操作用户数据库，不消耗模型配额。"
            f"容量要求：有效可用空间大于 {MIN_AVAILABLE_GIB} GiB；"
            "配额未知不能通过。"
            "inode 与残留仅报告和提示；清理须在没有 pytest 运行时手动执行。"
            "临时根为 access_only 权限探测，无法保证实际写入成功。"
            "输出到终端；全部满足返回 0，不满足返回 1，参数错误返回 2。"
            "常见失败：配额未知、空间不足、Git 未隔离或解释器不一致；请按输出处理。"
            "示例：./scripts/dev-environment check --json"
        ),
        add_help=False,
    )
    parser.add_argument("-h", "--help", action="help", help="显示本地中文帮助并退出")
    parser.add_argument("command", choices=["check"], help="执行只读环境检查")
    parser.add_argument("--json", action="store_true", help="输出同样事实的 JSON")
    arguments = parser.parse_args(argv)
    project = project or Path(__file__).resolve().parent.parent
    report = check_environment(project, probes=probes)
    checks = {
        name: {
            "reason": item.reason.value,
            "facts": item.facts,
            "help_zh": GUIDANCE[item.reason],
        }
        for name, item in report.checks.items()
    }
    if arguments.json:
        print(
            json.dumps(
                {"exit_code": report.exit_code, "checks": checks},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    else:
        labels = {
            "interpreter": "项目解释器（实际执行 bin/python）",
            "temporary": "临时根",
            "git": "Git 隔离",
            "capacity": "有效容量",
            "inodes": "可用 inode",
            "residue": "pytest 残留",
        }
        for name, item in checks.items():
            print(f"{labels[name]}：{item['reason']}；{item['help_zh']}")
            print(json.dumps(item["facts"], ensure_ascii=False, sort_keys=True))
        print(f"检查退出码：{report.exit_code}")
    return report.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
