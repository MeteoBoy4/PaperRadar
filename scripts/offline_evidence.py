"""执行离线检查, 并为每次运行保存不含原始输出的验收证据。"""

from __future__ import annotations

import hashlib
import json
import os
import select
import shlex
import signal
import subprocess
import sys
import time
import uuid
from contextlib import ExitStack, suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, TypedDict


class CodeIdentity(TypedDict):
    commit: str | None
    dirty: bool | None


class CheckStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    NOT_RUN = "not_run"


class CheckReason(StrEnum):
    NONE = "none"
    NOT_STARTED = "not_started"
    SKIPPED = "skipped"
    PRIOR_FAILURE = "prior_failure"
    INTERRUPTED = "interrupted"
    EXIT_NONZERO = "exit_nonzero"
    LAUNCH_ERROR = "launch_error"


class OverallStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    INCOMPLETE = "incomplete"


@dataclass(frozen=True, slots=True)
class Check:
    id: str
    command: tuple[str, ...]
    enabled: bool = True
    help_zh: str = "请在本地单独运行该检查，查看具体失败项。"


CONTRACT_NAMES = (
    "boundary",
    "value-prediction",
    "reuse-assessment",
    "decision-reasons",
)
CONTRACT_VERSION = "v1"


def default_checks() -> tuple[Check, ...]:
    """唯一的生产离线检查计划; 证据和实际执行共用此计划。"""
    uv = ("uv", "run", "--offline", "--locked")

    def planned_check(check_id: str, command: tuple[str, ...], note: str = "") -> Check:
        return Check(
            check_id,
            command,
            help_zh=f"请单独运行：{shlex.join(command)}。{note}",
        )

    return (
        planned_check(
            "lockfile",
            ("uv", "lock", "--check", "--offline"),
            "若无法启动，请检查 uv 是否可用。",
        ),
        planned_check(
            "format",
            (*uv, "ruff", "format", "--check", "src", "tests", "scripts"),
        ),
        planned_check(
            "lint",
            (*uv, "ruff", "check", "src", "tests", "scripts"),
        ),
        planned_check(
            "types",
            (*uv, "mypy"),
        ),
        planned_check(
            "tests",
            (*uv, "python", "-m", "pytest", "-p", "scripts.a2_test_receipt"),
            "定位失败用例。",
        ),
        planned_check(
            "contracts",
            (
                *uv,
                "paper-radar",
                "contracts",
                "check",
                *(item for name in CONTRACT_NAMES for item in ("--contract", name)),
                "--version",
                CONTRACT_VERSION,
                "--target",
                "contracts",
            ),
            "查看逐项安全错误类别。",
        ),
    )


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def file_sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _child_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("PAPER_RADAR_TEST_RECEIPT", None)
    environment.pop("PAPER_RADAR_TEST_RUN_ID", None)
    return environment


def git_metadata(root: Path) -> CodeIdentity:
    try:
        commit = subprocess.run(
            ("git", "rev-parse", "HEAD"),
            cwd=root,
            env=_child_environment(),
            capture_output=True,
            check=True,
            text=True,
        ).stdout.strip()
        status = subprocess.run(
            ("git", "status", "--porcelain", "--untracked-files=normal"),
            cwd=root,
            env=_child_environment(),
            capture_output=True,
            check=True,
            text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "dirty": None}
    return {"commit": commit or None, "dirty": bool(status)}


_DEPENDENCY_NAMES = ("pydantic", "typer", "pytest", "ruff", "mypy")
_ENVIRONMENT_CODE = """import importlib.metadata, json, platform, sys
names = sys.argv[1:]
versions = {}
for name in names:
    try:
        versions[name] = importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        versions[name] = None
print(json.dumps({'python': platform.python_version(), 'dependencies': versions}))
"""


def _environment_metadata(root: Path) -> dict[str, Any]:
    missing = dict.fromkeys(_DEPENDENCY_NAMES)
    if not (root / "pyproject.toml").is_file() or not (root / "uv.lock").is_file():
        return {
            "python": None,
            "dependencies": missing,
            "missing_reason": "environment_unavailable",
        }
    try:
        result = subprocess.run(
            (
                "uv",
                "run",
                "--offline",
                "--locked",
                "python",
                "-c",
                _ENVIRONMENT_CODE,
                *_DEPENDENCY_NAMES,
            ),
            cwd=root,
            env=_child_environment(),
            capture_output=True,
            check=True,
            text=True,
        )
        loaded = json.loads(result.stdout)
        python = loaded["python"]
        dependencies = loaded["dependencies"]
        if not isinstance(python, str) or not isinstance(dependencies, dict):
            raise ValueError("invalid environment metadata")
        return {
            "python": python,
            "dependencies": {name: dependencies.get(name) for name in missing},
            "missing_reason": None,
        }
    except (OSError, subprocess.CalledProcessError, ValueError, KeyError):
        return {
            "python": None,
            "dependencies": missing,
            "missing_reason": "environment_unavailable",
        }


def _contract_metadata(
    root: Path, names: tuple[str, ...], version: str
) -> list[dict[str, str | None]]:
    from paper_radar.contracts.schema import (
        ContractSelectionError,
        build_selected_contract,
    )

    def schema_sha256(name: str) -> str | None:
        try:
            contract = build_selected_contract(name, version)
        except ContractSelectionError:
            return None
        return file_sha256(
            (root / "contracts").joinpath(
                *contract.snapshot_parts, contract.schema_filename
            )
        )

    return [
        {
            "name": name,
            "version": version,
            "schema_sha256": schema_sha256(name),
        }
        for name in names
    ]


def _write_evidence(path: Path, evidence: dict[str, Any]) -> None:
    payload = (
        json.dumps(evidence, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode()
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _kill_and_wait_for_group(group: int) -> None:
    """用 Linux pidfd 等待成员退出, 不把发送 SIGKILL 当成退出确认。"""
    empty_scan = False
    while True:
        with ExitStack() as descriptors:
            poller = select.poll()
            pending: set[int] = set()
            for entry in Path("/proc").iterdir():
                if not entry.name.isdecimal():
                    continue
                try:
                    pid = int(entry.name)
                    if os.getpgid(pid) != group:
                        continue
                    fd = os.pidfd_open(pid)
                    descriptors.callback(os.close, fd)
                    # 打开 fd 期间 PID 可能退出或被复用, 再确认归属。
                    if os.getpgid(pid) != group:
                        continue
                except ProcessLookupError:
                    continue
                poller.register(fd, select.POLLIN)
                pending.add(fd)
            for fd, _ in poller.poll(0):
                poller.unregister(fd)
                pending.remove(fd)
            if not pending:
                # 再扫一次, 覆盖上次枚举期间组内 fork 后父进程退出的情况。
                if empty_scan:
                    return
                empty_scan = True
                continue
            empty_scan = False
            with suppress(ProcessLookupError):
                os.killpg(group, signal.SIGKILL)
            while pending:
                for fd, _ in poller.poll():
                    poller.unregister(fd)
                    pending.remove(fd)


def _stop_process_group(process: subprocess.Popen[bytes], process_group: int) -> None:
    """给整组退出宽限, 即使组长先退出也继续清理后代。"""
    previous = {
        signum: signal.signal(signum, signal.SIG_IGN)
        for signum in (signal.SIGINT, signal.SIGTERM)
    }
    try:
        with suppress(ProcessLookupError):
            os.killpg(process_group, signal.SIGTERM)
        deadline = time.monotonic() + 2
        while True:
            process.poll()
            try:
                os.killpg(process_group, 0)
            except ProcessLookupError:
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(0.05, remaining))
        with suppress(ProcessLookupError):
            os.killpg(process_group, signal.SIGKILL)
        _kill_and_wait_for_group(process_group)
        process.wait()
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def _run_check(check: Check, root: Path, environment: dict[str, str]) -> int:
    process = subprocess.Popen(
        check.command,
        cwd=root,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    # start_new_session 令检查进程成为会话和进程组组长; 在启动边界固定清理目标。
    process_group = process.pid
    try:
        exit_code = process.wait()
    except KeyboardInterrupt:
        _stop_process_group(process, process_group)
        raise
    if exit_code < 0:
        _stop_process_group(process, process_group)
    return exit_code


def _run_checks(
    root: Path,
    checks: tuple[Check, ...],
    path: Path,
    evidence: dict[str, Any],
) -> bool:
    stopped = False
    interrupted = False
    for index, check in enumerate(checks):
        item = evidence["checks"][index]
        if stopped:
            item["reason"] = (
                CheckReason.INTERRUPTED if interrupted else CheckReason.PRIOR_FAILURE
            )
        elif not check.enabled:
            item["reason"] = CheckReason.SKIPPED
        else:
            print(f"[离线检查] {check.id}", flush=True)
            try:
                environment = _child_environment()
                if check.id == "tests":
                    environment.pop("PYTEST_ADDOPTS", None)
                    environment["PAPER_RADAR_TEST_RUN_ID"] = evidence["run_id"]
                    environment["PAPER_RADAR_TEST_RECEIPT"] = str(
                        path.with_suffix(".pytest.json").resolve()
                    )
                exit_code = _run_check(check, root, environment)
            except KeyboardInterrupt:
                item.update(status=CheckStatus.FAILED, reason=CheckReason.INTERRUPTED)
                stopped = interrupted = True
            except OSError:
                item.update(status=CheckStatus.FAILED, reason=CheckReason.LAUNCH_ERROR)
                stopped = True
            else:
                item["exit_code"] = exit_code
                if exit_code == 0:
                    item.update(status=CheckStatus.PASSED, reason=CheckReason.NONE)
                elif exit_code < 0:
                    item.update(
                        status=CheckStatus.FAILED, reason=CheckReason.INTERRUPTED
                    )
                    stopped = interrupted = True
                else:
                    item.update(
                        status=CheckStatus.FAILED, reason=CheckReason.EXIT_NONZERO
                    )
                    stopped = True
            if item["status"] == CheckStatus.FAILED:
                item["help_zh"] = check.help_zh
            print(
                f"[离线检查] {check.id}: {item['status']} ({item['reason']})",
                flush=True,
            )
            if item["status"] == CheckStatus.FAILED:
                print(f"[离线检查] 处理：{check.help_zh}", flush=True)
        _write_evidence(path, evidence)
    return interrupted


def run_offline_verification(
    root: Path,
    checks: tuple[Check, ...],
    output_dir: Path,
    *,
    contract_names: tuple[str, ...] = CONTRACT_NAMES,
    contract_version: str = CONTRACT_VERSION,
) -> tuple[Path, dict[str, Any]]:
    """逐项运行检查; 失败停止后续执行, 证据始终区分未运行。"""
    if not checks:
        raise ValueError("至少一项离线检查必须实际进入计划。")
    run_id = uuid.uuid4().hex
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{run_id}.json"
    evidence: dict[str, Any] = {
        "format_version": 1,
        "run_id": run_id,
        "started_at": _utc_now(),
        "finished_at": None,
        "completed": False,
        "overall": OverallStatus.INCOMPLETE,
        "scope": {
            "issue": 12,
            "claim": "implemented_offline_checks_only",
            "full_a1_verified": False,
            "stage_a_verified": False,
            "not_assessed": [
                "business_pipeline",
                "live_sources",
                "llm",
                "pdf",
                "calibration",
            ],
        },
        "code": {"commit": None, "dirty": None},
        "lockfile_sha256": None,
        "environment": {
            "python": None,
            "dependencies": dict.fromkeys(_DEPENDENCY_NAMES),
            "missing_reason": "not_collected",
        },
        "contracts": [
            {"name": name, "version": contract_version, "schema_sha256": None}
            for name in contract_names
        ],
        "checks": [
            {
                "id": check.id,
                "status": CheckStatus.NOT_RUN,
                "reason": CheckReason.NOT_STARTED,
                "exit_code": None,
            }
            for check in checks
        ],
    }
    interrupted = False
    try:
        _write_evidence(path, evidence)
        evidence["code"] = git_metadata(root)
        evidence["lockfile_sha256"] = file_sha256(root / "uv.lock")
        evidence["environment"] = _environment_metadata(root)
        evidence["contracts"] = _contract_metadata(
            root, contract_names, contract_version
        )
        _write_evidence(path, evidence)
        interrupted = _run_checks(root, checks, path, evidence)
    except KeyboardInterrupt:
        interrupted = True
        for item in evidence["checks"]:
            if (
                item["status"] == CheckStatus.NOT_RUN
                and item["reason"] == CheckReason.NOT_STARTED
            ):
                item["reason"] = CheckReason.INTERRUPTED
        print("[离线检查] 运行被中断；本次证据不视为通过。", flush=True)
    evidence["finished_at"] = _utc_now()
    evidence["completed"] = not interrupted
    if not interrupted:
        evidence["overall"] = (
            OverallStatus.PASSED
            if all(item["status"] == CheckStatus.PASSED for item in evidence["checks"])
            else OverallStatus.FAILED
        )
    _write_evidence(path, evidence)
    return path, evidence


def _interrupt(_signum: int, _frame: object) -> None:
    raise KeyboardInterrupt


def main() -> int:
    signal.signal(signal.SIGTERM, _interrupt)
    root = Path(__file__).resolve().parent.parent
    path, evidence = run_offline_verification(
        root, default_checks(), root / "verification-runs"
    )
    print(f"[离线检查] 证据：{path}")
    print(f"[离线检查] 结果：{evidence['overall']}")
    return 0 if evidence["overall"] == OverallStatus.PASSED else 1


if __name__ == "__main__":
    sys.exit(main())
