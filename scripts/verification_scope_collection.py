"""独立 pytest 收集进程; 只传递模块计数, 永不写正式回执。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path

from scripts.verification_scope_audit import (
    AuditReason,
    CollectionResult,
    valid_case_count,
    valid_path,
)


def collect_counts(
    root: Path,
    expected: Mapping[str, int | None],
    *,
    timeout: float = 120,
) -> CollectionResult:
    """只收集显式模块; skip/deselect/失败与实际执行通过严格分离。"""
    result: CollectionResult = dict(
        reason=AuditReason.COLLECTION_UNAVAILABLE,
        execution="not_run",
        modules={},
    )
    if not expected or any(
        not valid_path(p) or (n is not None and not valid_case_count(n))
        for p, n in expected.items()
    ):
        result["reason"] = AuditReason.INVALID_COUNTS
        return result
    environment = dict(os.environ)
    for key in (
        "PAPER_RADAR_TEST_RECEIPT",
        "PAPER_RADAR_TEST_RUN_ID",
        "PYTEST_ADDOPTS",
        "PYTEST_PLUGINS",
    ):
        environment.pop(key, None)
    environment.update(PYTHONDONTWRITEBYTECODE="1", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    module_root = Path(__file__).resolve().parents[1]
    worker = (
        "import sys; "
        "sys.path.insert(0, sys.argv.pop(1)); "
        "from scripts.verification_scope_collection import collection_worker; "
        "raise SystemExit(collection_worker())"
    )
    # 只有受控计数临时文件, 不保留原始 stdout/stderr 或正式运行身份。
    with tempfile.TemporaryDirectory(
        prefix="scope-collection-", dir="/tmp"
    ) as directory:
        output = Path(directory) / "counts.json"
        try:
            process = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-c",
                    worker,
                    str(module_root),
                    str(output),
                    *sorted(expected),
                ],
                cwd=root,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=timeout,
                check=False,
            )
            raw = json.loads(output.read_bytes())
            modules = raw["modules"]
            if (
                not isinstance(modules, dict)
                or set(modules) != set(expected)
                or any(type(n) is not int or n < 0 for n in modules.values())
                or type(raw["skipped"]) is not int
                or raw["skipped"] < 0
                or type(raw["deselected"]) is not int
                or raw["deselected"] < 0
            ):
                return result
        except subprocess.TimeoutExpired:
            result["reason"] = AuditReason.COLLECTION_TIMEOUT
            return result
        except (OSError, ValueError, KeyError, TypeError):
            return result
    result["modules"] = modules
    result["collection_skipped"] = raw["skipped"]
    result["deselected"] = raw["deselected"]
    if process.returncode not in (0, 5):
        result["reason"] = AuditReason.COLLECTION_FAILED
    elif raw["skipped"]:
        result["reason"] = AuditReason.COLLECTION_SKIPPED
    elif raw["deselected"]:
        result["reason"] = AuditReason.COLLECTION_DESELECTED
    elif process.returncode != 0:
        result["reason"] = AuditReason.COLLECTION_FAILED
    else:
        result["reason"] = (
            AuditReason.COUNT_MISMATCH if modules != expected else AuditReason.OK
        )
    return result


def collection_worker() -> int:
    """子进程专用入口, pytest 的输出只流向父进程的 DEVNULL。"""
    import pytest

    output = Path(sys.argv[1])
    modules = dict.fromkeys(sys.argv[2:], 0)

    class Counts:
        skipped = 0
        deselected = 0

        @pytest.hookimpl(tryfirst=True)
        def pytest_collection_modifyitems(self, items: list[pytest.Item]) -> None:
            for item in items:
                path = item.path.relative_to(Path.cwd()).as_posix()
                if path in modules:
                    modules[path] += 1

        def pytest_collectreport(self, report: pytest.CollectReport) -> None:
            if report.skipped:
                self.skipped += 1

        def pytest_deselected(self, items: list[pytest.Item]) -> None:
            self.deselected += len(items)

    counts = Counts()
    code = pytest.main(
        [
            "--collect-only",
            "-q",
            "-p",
            "no:cacheprovider",
            "-p",
            "no:scripts.a2_test_receipt",
            "-o",
            "addopts=",
            *modules,
        ],
        plugins=[counts],
    )
    output.write_text(
        json.dumps(
            dict(modules=modules, skipped=counts.skipped, deselected=counts.deselected)
        )
    )
    return int(code)
