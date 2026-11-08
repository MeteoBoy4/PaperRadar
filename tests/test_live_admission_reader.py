"""新纯判定层不变成产品授予接缝,安全冷导入无外部行为。"""

import json
import subprocess
import sys

from paper_radar.pi_execution.admission import load_admission_evidence
from tests.test_pi_execution_admission import binding


def test_renamed_product_loader_has_no_fact_source() -> None:
    assert load_admission_evidence(binding()) is None


def test_pure_registry_and_evaluator_import_without_execution_or_storage() -> None:
    script = """
import json, sys
import paper_radar.live_evidence.evaluator
import paper_radar.live_evidence.registry
forbidden = (
    "sqlite3", "httpx", "paper_radar.pi_execution.auth",
    "paper_radar.pi_execution.launcher", "paper_radar.pi_supply.protection",
    "paper_radar.storage", "paper_radar.read_execution.service",
)
print(json.dumps([name for name in forbidden if name in sys.modules]))
"""
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True
    )
    assert json.loads(result.stdout) == []
