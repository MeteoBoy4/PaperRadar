"""纯内存准入:所有执行身份均绑定,导入不连接启动/认证层。"""

import json
import subprocess
import sys
from dataclasses import replace
from typing import Any

import pytest

from paper_radar.pi_execution.admission import (
    AdmissionEvidence,
    EvidenceBinding,
    admit,
    load_admission_evidence,
)


def binding() -> EvidenceBinding:
    return EvidenceBinding(
        "a" * 64,
        "b" * 32,
        "launch-v1",
        "isolation-v1",
        "<cwd>\n/srv/pi-cwd\n</cwd>",
        "openai",
        "fixed-model",
        "low",
        "provider_default",
        None,
        None,
        "pi-rpc-1.4.0-v1",
        "chatgpt_subscription",
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("supply_id", "c" * 64),
        ("install_id", "d" * 32),
        ("launch_policy_version", "launch-v2"),
        ("isolation_policy_version", "isolation-v2"),
        ("cwd_section", "<cwd>\n/other\n</cwd>"),
        ("provider", "other"),
        ("model", "other"),
        ("thinking_level", "high"),
        ("sampling", "explicit"),
        ("temperature", 0.0),
        ("top_p", 1.0),
        ("protocol_profile", "other"),
        ("auth_mode", "other"),
    ],
)
def test_evidence_cannot_be_reused_for_another_binding(field: str, value: Any) -> None:
    expected = binding()
    evidence = AdmissionEvidence(replace(expected, **{field: value}), True, True, True)
    assert admit(expected, evidence) == "evidence_mismatch"


def test_product_has_no_evidence_source_and_explicit_mapping_is_unavailable() -> None:
    expected = binding()
    assert load_admission_evidence(expected) is None
    assert admit(expected, None) == "evidence_missing"
    explicit = replace(expected, sampling="explicit", temperature=0.0, top_p=1.0)
    assert (
        admit(explicit, AdmissionEvidence(explicit, True, True, True))
        == "sampling_mapping_unavailable"
    )


def test_doctor_safe_import_does_not_import_auth_or_install_protection() -> None:
    script = """
import json, sys
import paper_radar.pi_execution.admission
names = [
    "paper_radar.pi_execution.auth", "paper_radar.pi_execution.launcher",
    "paper_radar.pi_supply.protection",
]
print(json.dumps([name for name in names if name in sys.modules]))
"""
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True
    )
    assert json.loads(result.stdout) == []
