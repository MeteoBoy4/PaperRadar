"""正式路径 OS fixture;只替换站点观察来源和 helper 进程,不替换判定。"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerTrust
from paper_radar.live_evidence.lifecycle import EvidenceLifecycle
from paper_radar.live_evidence.observation import CurrentObservation
from paper_radar.live_evidence.receipt import (
    ApprovedPlan,
    EvidenceReceipt,
    UseId,
    canonical_bytes,
    content_sha256,
)
from paper_radar.live_evidence.types import BindingComponent
from tests.live_evidence_ledger_support import NOW, owner_uid, plan, protected_root
from tests.live_evidence_ledger_support import receipt as receipt_template

if TYPE_CHECKING:
    from paper_radar.pi_execution.service import PiExecution
    from paper_radar.screening_tasks import RequestReceipt


# 从已接受 ADR0052 人工列举;不从生产登记反推正例必需集合。
REQUIRED = (
    "auth_cache_current",
    "auth_cache_baseline",
    "cwd_ancestors",
    "file_isolation",
    "ipv4_egress",
    "zero_core",
    "apport_identity",
    "rpc_completion",
    "rpc_eof",
    "rpc_terminate",
    "model_identity",
    "single_dispatch",
    "no_extra_turns",
    "supply_tree",
    "instance_tree",
    "pi_version",
    "launch_policy",
    "isolation_policy",
    "host_runtime",
)


def protected_admission(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    capabilities: tuple[str, ...] = REQUIRED,
    components: dict[BindingComponent, str] | None = None,
    uses: tuple[UseId, ...] = ("boundary-low",),
    activate: bool = True,
) -> tuple[EvidenceLedger, EvidenceReceipt, dict[BindingComponent, str]]:
    from paper_radar.live_evidence import service
    from paper_radar.live_evidence.evidence import ExecutionBinding

    root.mkdir(parents=True)
    sealed = protected_root(root)
    ledger = EvidenceLedger(
        sealed, trust=LedgerTrust(owner_uid(), owner_uid() + 1, sealed)
    )
    ledger.initialize()
    approved = ApprovedPlan.model_validate(
        plan().model_dump()
        | {
            "kind": "model_six_cell",
            "starts_at": NOW - timedelta(days=1),
            "ends_at": NOW + timedelta(days=1),
        }
    )
    ledger.approve_plan(approved, now=NOW)
    data = receipt_template().model_dump(mode="json")
    data.update(
        plan_sha256=content_sha256(approved),
        started_at=NOW.isoformat(),
        completed_at=NOW.isoformat(),
    )
    if components is not None:
        data["binding"] = components.copy()
    template = data["claims"][0]
    data["claims"] = [
        template
        | {
            "capability": cap,
            "use_id": use,
            "verified_at": NOW.isoformat(),
            "evidence_at": NOW.isoformat(),
            "basis": "rpc_probe",
            "scope": "single_case",
        }
        for use in uses
        for cap in capabilities
    ]
    receipt = EvidenceReceipt.model_validate(data)
    source = sealed / "inbox/site.json"
    source.write_bytes(canonical_bytes(receipt))
    source.chmod(0o644)
    ledger.receive(source, now=NOW)
    binding = ExecutionBinding(tuple(receipt.binding.items()))
    lifecycle = EvidenceLifecycle(ledger)
    if activate:
        for use in uses:
            review = lifecycle.review(
                receipt.receipt_id,
                use,
                binding=binding,
                checked_components=frozenset(BindingComponent),
                now=NOW,
            )
            lifecycle.activate(review, confirmation=receipt.receipt_id, now=NOW)
    components = dict(binding.components)
    observation = CurrentObservation(
        observed_at=NOW, binding=components, checked_components=tuple(BindingComponent)
    )
    (ledger.root / "inbox/current-observation.json").write_bytes(
        canonical_bytes(observation)
    )
    (ledger.root / "inbox/current-observation.json").chmod(0o644)
    monkeypatch.setattr(
        "paper_radar.pi_execution.current_binding.EvidenceLedger", lambda: ledger
    )
    monkeypatch.setattr(
        "paper_radar.pi_execution.current_binding.local_binding_components",
        lambda *a, **kw: components.copy(),
    )
    monkeypatch.setattr(service, "_ledger", lambda: ledger)
    monkeypatch.setattr(service, "_pending_path", lambda: root / "pending.jsonl")
    monkeypatch.setattr(service, "_run_helper", lambda arguments: True)
    return ledger, receipt, components


def product_inputs(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[PiExecution, RequestReceipt, Path]:
    from tests.pi_execution_service_support import service_inputs

    return service_inputs(root, monkeypatch, thinking_level="low")
