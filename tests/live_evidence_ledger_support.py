from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

from paper_radar.live_evidence.receipt import (
    ApprovedPlan,
    EvidenceReceipt,
    content_sha256,
)
from paper_radar.live_evidence.types import BindingComponent

NOW = datetime(2026, 11, 9, 12, tzinfo=UTC)


def plan() -> ApprovedPlan:
    return ApprovedPlan.model_validate(
        {
            "format_version": "v1",
            "plan_id": "beta-1",
            "kind": "site_beta",
            "collector_sha256": "a" * 64,
            "cases": ["cwd"],
            "starts_at": "2026-11-09T00:00:00Z",
            "ends_at": "2026-11-10T00:00:00Z",
            "max_auth_calls": 0,
            "max_model_calls": 0,
            "max_network_requests": 0,
            "max_rounds": 1,
            "stop_on_first_failure": True,
        }
    )


def receipt() -> EvidenceReceipt:
    return EvidenceReceipt.model_validate(
        {
            "format_version": "v1",
            "registry_version": "live-admission-v1",
            "plan_id": "beta-1",
            "plan_sha256": content_sha256(plan()),
            "collector_sha256": "a" * 64,
            "round_number": 1,
            "started_at": "2026-11-09T01:00:00Z",
            "completed_at": "2026-11-09T01:01:00Z",
            "binding": {component: "b" * 64 for component in BindingComponent},
            "cases": [
                {
                    "case_id": "cwd",
                    "outcome": "passed",
                    "auth_calls": 0,
                    "model_calls": 0,
                    "network_requests": 0,
                }
            ],
            "failure_history": [],
            "claims": [
                {
                    "capability": "cwd_ancestors",
                    "use_id": "boundary-low",
                    "case_id": "cwd",
                    "status": "verified",
                    "basis": "site_probe",
                    "scope": "current_site",
                    "verified_at": "2026-11-09T01:01:00Z",
                    "evidence_at": "2026-11-09T01:01:00Z",
                }
            ],
        }
    )


def protected_root(tmp_path: Path) -> Path:
    root = tmp_path / "sealed"
    root.mkdir(mode=0o755)
    (root / "inbox").mkdir(mode=0o755)
    return root


def owner_uid() -> int:
    return os.getuid()
