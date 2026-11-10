"""D1: collector 的严格封印上下文与临时 metadata 拒绝不消费额度。"""

from pathlib import Path

import pytest

from paper_radar.live_evidence import sealed_runtime
from paper_radar.live_evidence.collector import SiteObservation
from paper_radar.live_evidence.model_collector import collect_models_once
from paper_radar.live_evidence.sealed_runtime import SiteConfiguration
from paper_radar.llm.dispatch import DispatchDenied
from tests.live_evidence_ledger_support import NOW
from tests.model_collection_support import setup_collection


def test_collector_metadata_is_strict_and_temporary_failure_has_no_consumption(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime, ledger, collection, manifest, active = setup_collection(
        tmp_path, monkeypatch
    )
    actual = sealed_runtime.product_observation
    checked: list[bool] = []

    def unavailable(
        site: SiteConfiguration,
        *,
        metadata_only: bool = False,
        require_snapshot: bool = False,
    ) -> SiteObservation:
        checked.append(require_snapshot)
        assert metadata_only and require_snapshot
        return SiteObservation({}, (("metadata", False),), "observation_unavailable")

    before = collection.status(manifest.negative_plan.plan_id, now=NOW)
    monkeypatch.setattr(sealed_runtime, "product_observation", unavailable)
    with pytest.raises(DispatchDenied, match=r"^resource_unavailable$"):
        collect_models_once(runtime, ledger, clock=lambda: NOW)
    assert checked == [True]
    assert not active and not collection.completed_receipts()
    assert collection.status(manifest.negative_plan.plan_id, now=NOW) == before
    monkeypatch.setattr(sealed_runtime, "product_observation", actual)
    assert len(collect_models_once(runtime, ledger, clock=lambda: NOW)) == 6
    assert len(active) == 10
