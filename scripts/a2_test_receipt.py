"""pytest 固定范围执行回执。不记录测试名、参数、输出、异常或 skip 原因。"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import pytest

from scripts.a1_scope import REQUIRED_TEST_MODULES as A1_TEST_MODULES
from scripts.a2_full_scope import (
    RECEIPT_COUNTERS,
    REQUIRED_TEST_MODULES,
    ReceiptCounter,
)
from scripts.a3_scope import REQUIRED_TEST_MODULES as A3_TEST_MODULES
from scripts.a4_scope import REQUIRED_TEST_MODULES as A4_TEST_MODULES
from scripts.a5_scope import REQUIRED_TEST_MODULES as A5_TEST_MODULES
from scripts.a6_scope import REQUIRED_TEST_MODULES as A6_TEST_MODULES
from scripts.a7_scope import REQUIRED_TEST_MODULES as A7_TEST_MODULES


class TestReceipt:
    def __init__(self, path: Path, run_id: str) -> None:
        self.path = path
        self.run_id = run_id
        self.nodes: dict[str, dict[str, str]] = {}
        self.modules = {
            name: dict.fromkeys(RECEIPT_COUNTERS, 0)
            for name, _ in (
                *A1_TEST_MODULES,
                *REQUIRED_TEST_MODULES,
                *A3_TEST_MODULES,
                *A4_TEST_MODULES,
                *A5_TEST_MODULES,
                *A6_TEST_MODULES,
                *A7_TEST_MODULES,
            )
        }

    def _write(self, *, completed: bool = False, exit_code: int | None = None) -> None:
        payload = {
            "format_version": 1,
            "run_id": self.run_id,
            "completed": completed,
            "exit_code": exit_code,
            "modules": self.modules,
        }
        temporary = self.path.with_name(f".{self.path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with temporary.open("xb") as stream:
                stream.write((json.dumps(payload, sort_keys=True) + "\n").encode())
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def pytest_sessionstart(self) -> None:
        self._write()

    def pytest_collection_finish(self, session: pytest.Session) -> None:
        for item in session.items:
            module = item.nodeid.split("::", 1)[0]
            if module in self.modules:
                self.nodes[item.nodeid] = {}
                self.modules[module][ReceiptCounter.COLLECTED] += 1
        self._write()

    def pytest_deselected(self, items: list[pytest.Item]) -> None:
        for item in items:
            module = item.nodeid.split("::", 1)[0]
            if module in self.modules:
                self.modules[module][ReceiptCounter.DESELECTED] += 1

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        if report.nodeid in self.nodes:
            self.nodes[report.nodeid][report.when] = report.outcome

    def pytest_sessionfinish(self, exitstatus: int) -> None:
        for node, phases in self.nodes.items():
            if ReceiptCounter.FAILED in phases.values():
                outcome = ReceiptCounter.FAILED
            elif ReceiptCounter.SKIPPED in phases.values():
                outcome = ReceiptCounter.SKIPPED
            elif phases == {"setup": "passed", "call": "passed", "teardown": "passed"}:
                outcome = ReceiptCounter.PASSED
            else:
                outcome = ReceiptCounter.INCOMPLETE
            self.modules[node.split("::", 1)[0]][outcome] += 1
        self._write(completed=exitstatus not in (2, 3), exit_code=int(exitstatus))


def pytest_configure(config: pytest.Config) -> None:
    path = os.environ.get("PAPER_RADAR_TEST_RECEIPT")
    run_id = os.environ.get("PAPER_RADAR_TEST_RUN_ID")
    if path and run_id:
        config.pluginmanager.register(
            TestReceipt(Path(path), run_id), "a2-test-receipt"
        )
