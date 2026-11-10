"""受保护例行观察发布;候选验证后替换,不形成能力或采集消耗。"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime
from typing import Literal

from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerError
from paper_radar.live_evidence.observation import (
    OBSERVATION_FILENAME,
    REFRESH_FILENAME,
    CurrentObservation,
    RefreshStatus,
    read_observation_snapshot,
)
from paper_radar.live_evidence.receipt import canonical_bytes
from paper_radar.live_evidence.types import BindingComponent


def record_refresh(
    ledger: EvidenceLedger,
    *,
    candidate: CurrentObservation | None,
    failure: Literal["observation_unavailable", "observation_drift", "source_untrusted"]
    | None = None,
    now: datetime,
    confirmed_components: frozenset[BindingComponent] = frozenset(),
    placement_mismatch: bool = False,
) -> RefreshStatus:
    """只供封印 root 入口使用;调用方须持有 collector.lock。"""
    from paper_radar.live_evidence.lifecycle import EvidenceLifecycle
    from paper_radar.live_evidence.sealed_runtime import _publish

    ledger._writer()
    try:
        previous = read_observation_snapshot(ledger, now=now)
    except LedgerError:
        if failure != "source_untrusted":
            raise
        previous = None
    if (candidate is None) == (failure is None):
        raise LedgerError("observation_invalid")
    changed = tuple(
        component
        for component in BindingComponent
        if component in confirmed_components
        or (
            candidate is not None
            and previous is not None
            and (
                candidate.binding[component] != previous.binding[component]
                or (
                    component in previous.checked_components
                    and component not in candidate.checked_components
                )
            )
        )
    )
    if candidate is not None:
        candidate.validate_time(now=now)
    result = failure or ("observation_drift" if changed else "available")
    snapshot = previous if candidate is None else candidate
    status = RefreshStatus(
        recorded_at=now,
        result=result,
        snapshot_sha256=hashlib.sha256(canonical_bytes(snapshot)).hexdigest()
        if snapshot is not None
        else None,
        changed_components=changed,
        pending_revocation=result in {"observation_drift", "source_untrusted"},
        placement_mismatch=placement_mismatch,
    )
    status_path = ledger.root / "inbox" / REFRESH_FILENAME
    # 先封闭读取;两次原子发布之间中断只会拒绝,不会暴露半份候选。
    _publish(
        status_path,
        canonical_bytes(
            status
            if result != "available"
            else status.model_copy(update={"result": "observation_unavailable"})
        ),
        replace=True,
    )
    history = ledger.root / "observation-refresh-history.jsonl"
    if history.exists():
        ledger._protected(history)
    fd = os.open(history, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o644)
    with os.fdopen(fd, "ab") as stream:
        stream.write(canonical_bytes(status) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    if result in {"observation_drift", "source_untrusted"}:
        lifecycle = EvidenceLifecycle(ledger)
        if result == "source_untrusted":
            from paper_radar.live_evidence.lifecycle import use_id_for
            from paper_radar.live_evidence.registry import INITIAL_REGISTRY

            for entry in INITIAL_REGISTRY.uses:
                lifecycle.tighten_use(use_id_for(entry.use), now=now)
        for source in () if result == "source_untrusted" else ledger.list_received():
            for use_id in sorted({claim.use_id for claim in source.receipt.claims}):
                lifecycle.tighten(
                    source.receipt_id,
                    use_id,
                    now=now,
                    components=frozenset(changed) if changed else None,
                )
    status = status.model_copy(update={"pending_revocation": False})
    if candidate is not None:
        _publish(
            ledger.root / "inbox" / OBSERVATION_FILENAME,
            canonical_bytes(candidate),
            replace=True,
        )
    _publish(status_path, canonical_bytes(status), replace=True)
    return status
