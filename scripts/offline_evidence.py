"""执行离线检查, 并为每次运行保存不含原始输出的验收证据。"""

from __future__ import annotations

import hashlib
import json
import os
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
    return (
        Check(
            "lockfile",
            ("uv", "lock", "--check", "--offline"),
            help_zh="请检查 uv 是否可用，并单独运行 uv lock --check --offline。",
        ),
        Check(
            "format",
            (*uv, "ruff", "format", "--check", "src", "tests", "scripts"),
            help_zh=(
                "请单独运行 uv run --offline --locked ruff format --check "
                "src tests scripts。"
            ),
        ),
        Check(
            "lint",
            (*uv, "ruff", "check", "src", "tests", "scripts"),
            help_zh=(
                "请单独运行 uv run --offline --locked ruff check src tests scripts。"
            ),
        ),
        Check(
            "types",
            (*uv, "mypy"),
            help_zh="请单独运行 uv run --offline --locked mypy。",
        ),
        Check(
            "tests",
            (*uv, "pytest"),
            help_zh="请单独运行 uv run --offline --locked pytest，定位失败用例。",
        ),
        Check(
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
            help_zh="请单独运行已选契约的 contracts check，查看逐项安全错误类别。",
        ),
    )


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _git_metadata(root: Path) -> dict[str, str | bool | None]:
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
            "schema_sha256": _sha256(
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


def run_offline_verification(
    root: Path,
    checks: tuple[Check, ...],
    output_dir: Path,
    *,
    contract_names: tuple[str, ...] = CONTRACT_NAMES,
    contract_version: str = CONTRACT_VERSION,
) -> tuple[Path, dict[str, Any]]:
    """逐项运行检查; 失败停止后续执行, 证据始终区分未运行。"""
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
        "code": _git_metadata(root),
        "lockfile_sha256": _sha256(root / "uv.lock"),
        "environment": _environment_metadata(root),
        "contracts": _contract_metadata(root, contract_names, contract_version),
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
    _write_evidence(path, evidence)
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
