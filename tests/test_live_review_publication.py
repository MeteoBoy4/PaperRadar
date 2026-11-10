"""D1: collector 公共入口发布恢复;合成 OS/RPC 不取得现场资格。"""

from datetime import timedelta
from pathlib import Path

import pytest

from paper_radar.live_evidence import model_collector
from paper_radar.live_evidence.collection import ProtectedCollection
from paper_radar.live_evidence.ledger import LedgerError
from paper_radar.live_evidence.receipt import canonical_bytes, content_sha256
from tests.live_evidence_ledger_support import NOW
from tests.model_collection_support import setup_collection


def test_negative_publication_reopens_without_repeating_or_refreshing_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime, ledger, collection, manifest, active = setup_collection(
        tmp_path, monkeypatch
    )
    from paper_radar.live_evidence.sealed_runtime import _publish

    publish = _publish
    interrupted = False

    def fail_once(
        path: Path, data: bytes, *, replace: bool = False, mode: int = 0o644
    ) -> None:
        nonlocal interrupted
        if path.name.startswith("negative-") and not interrupted:
            interrupted = True
            raise OSError("synthetic_negative_publication_interruption")
        publish(path, data, replace=replace, mode=mode)

    monkeypatch.setattr(model_collector, "_publish", fail_once)
    with pytest.raises(OSError, match="synthetic_negative_publication_interruption"):
        model_collector.collect_models_once(runtime, ledger, clock=lambda: NOW)
    completed = collection.completed_receipts()
    assert len(completed) == 1 and len(active) == 4
    original = completed[0]
    source = ledger.root / "inbox" / f"negative-{content_sha256(original)}.json"
    assert not source.exists()
    status = collection.status(manifest.negative_plan.plan_id, now=NOW)
    assert status.independent_network_used == 4 and not status.stopped
    later = NOW + timedelta(seconds=1)
    assert (
        len(model_collector.collect_models_once(runtime, ledger, clock=lambda: later))
        == 6
    )
    reopened = ProtectedCollection(ledger)
    assert reopened.completed_receipts()[0] == original
    assert source.read_bytes() == canonical_bytes(original)
    assert original.started_at == original.completed_at == NOW
    assert len(active) == 10 and len(set(active)) == 10
    status = reopened.status(manifest.negative_plan.plan_id, now=later)
    assert (
        status.independent_network_used == 4
        and status.auth_used == status.model_used == 6
    )
    assert not list(ledger.root.glob("publish-*.pending"))
    assert not ledger.list_received()


def test_lost_logically_published_negative_source_stays_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime, ledger, collection, manifest, active = setup_collection(
        tmp_path, monkeypatch
    )
    assert (
        len(model_collector.collect_models_once(runtime, ledger, clock=lambda: NOW))
        == 6
    )
    receipt = collection.completed_receipts()[0]
    source = ledger.root / "inbox" / f"negative-{content_sha256(receipt)}.json"
    source.unlink()
    before = collection.status(manifest.negative_plan.plan_id, now=NOW)
    with pytest.raises(LedgerError, match=r"^source_untrusted$"):
        model_collector.collect_models_once(runtime, ledger, clock=lambda: NOW)
    assert not source.exists() and len(active) == 10
    assert (
        ProtectedCollection(ledger).status(manifest.negative_plan.plan_id, now=NOW)
        == before
    )
