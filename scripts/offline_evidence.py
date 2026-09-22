"""执行离线检查, 并为每次运行保存不含原始输出的验收证据。"""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import signal
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any


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
            (*uv, "pytest"),
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


def git_metadata(root: Path) -> dict[str, str | bool | None]:
    try:
        commit = subprocess.run(
            ("git", "rev-parse", "HEAD"),
            cwd=root,
            capture_output=True,
            check=True,
            text=True,
        ).stdout.strip()
        status = subprocess.run(
            ("git", "status", "--porcelain", "--untracked-files=normal"),
            cwd=root,
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
    return [
        {
            "name": name,
            "version": version,
            "schema_sha256": file_sha256(
                root / "contracts" / "screening" / name / version / "schema.json"
            ),
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
                result = subprocess.run(
                    check.command,
                    cwd=root,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            except KeyboardInterrupt:
                item.update(status=CheckStatus.FAILED, reason=CheckReason.INTERRUPTED)
                stopped = interrupted = True
            except OSError:
                item.update(status=CheckStatus.FAILED, reason=CheckReason.LAUNCH_ERROR)
                stopped = True
            else:
                item["exit_code"] = result.returncode
                if result.returncode == 0:
                    item.update(status=CheckStatus.PASSED, reason=CheckReason.NONE)
                elif result.returncode < 0:
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
