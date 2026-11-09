"""#171 的受保护离线 OS fixture;不生成产品可导入的授予材料。"""

from datetime import datetime, timedelta
from pathlib import Path

from paper_radar.live_evidence.evidence import ExecutionBinding
from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerTrust
from paper_radar.live_evidence.lifecycle import EvidenceLifecycle
from paper_radar.live_evidence.receipt import (
    ApprovedPlan,
    EvidenceReceipt,
    canonical_bytes,
    content_sha256,
)
from paper_radar.live_evidence.types import BindingComponent, Capability
from tests.live_evidence_ledger_support import (
    NOW,
    owner_uid,
    plan,
    protected_root,
    receipt,
)


def installed(
    tmp_path: Path,
    *,
    capabilities: tuple[Capability, ...] = (Capability.CWD_ANCESTORS,),
    verified_at: datetime = NOW,
    provider: bool = False,
) -> tuple[EvidenceLedger, EvidenceReceipt, ExecutionBinding]:
    root = protected_root(tmp_path)
    ledger = EvidenceLedger(root, trust=LedgerTrust(owner_uid(), owner_uid() + 1, root))
    ledger.initialize()
    approved = ApprovedPlan.model_validate(
        plan().model_dump()
        | {
            "kind": "model_six_cell" if provider else "site_beta",
            "starts_at": verified_at - timedelta(days=1),
            "ends_at": NOW + timedelta(days=1),
        }
    )
    ledger.approve_plan(approved, now=NOW)
    data = receipt().model_dump(mode="json")
    data.update(
        plan_sha256=content_sha256(approved),
        started_at=verified_at.isoformat(),
        completed_at=verified_at.isoformat(),
    )
    claim = data["claims"][0]
    data["claims"] = [
        claim
        | {
            "capability": cap.value,
            "verified_at": verified_at.isoformat(),
            "evidence_at": verified_at.isoformat(),
            "basis": "rpc_probe" if provider else "site_probe",
            "scope": "single_case" if provider else "current_site",
        }
        for cap in capabilities
    ]
    original = EvidenceReceipt.model_validate(data)
    source = root / "inbox" / "site.json"
    source.write_bytes(canonical_bytes(original))
    source.chmod(0o644)
    ledger.receive(source, now=NOW)
    return ledger, original, ExecutionBinding(tuple(original.binding.items()))


def activated(
    tmp_path: Path,
    *,
    capabilities: tuple[Capability, ...] = (Capability.CWD_ANCESTORS,),
    verified_at: datetime = NOW,
    provider: bool = False,
) -> tuple[EvidenceLedger, EvidenceReceipt, ExecutionBinding]:
    ledger, original, binding = installed(
        tmp_path, capabilities=capabilities, verified_at=verified_at, provider=provider
    )
    lifecycle = EvidenceLifecycle(ledger)
    review = lifecycle.review(
        original.receipt_id,
        "boundary-low",
        binding=binding,
        checked_components=frozenset(BindingComponent),
        now=NOW,
    )
    lifecycle.activate(review, confirmation=original.receipt_id, now=NOW)
    return ledger, original, binding
