"""D1: 公开采集批次/正常刷新评审,不执行现场认证。"""

import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from paper_radar.live_evidence.model_collector import collect_models_once
from paper_radar.live_evidence.model_manifest import ModelManifestV2
from paper_radar.live_evidence.normal_auth_refresh import (
    initialize_epoch,
    review_normal_refresh,
)
from paper_radar.live_evidence.receipt import canonical_bytes
from tests.live_evidence_ledger_support import NOW
from tests.model_collection_support import setup_collection


def test_batches_pause_and_missing_refresh_persists_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, ledger, collection, manifest, active = setup_collection(tmp_path, monkeypatch)
    sealed = ModelManifestV2.model_validate(
        json.loads((root / "model-manifest.json").read_bytes()) | {"format_version": 2}
    )
    (root / "model-manifest.json").write_bytes(canonical_bytes(sealed))
    manifest = sealed.model_copy(update={"cells": manifest.cells})
    initialize_epoch(ledger, manifest, now=NOW)
    assert collect_models_once(root, ledger, clock=lambda: NOW) == ("boundary-low",)
    assert active[-1] == "model-boundary-low"
    assert len(collection.completed_receipts()) == 2  # negative round + A
    assert collect_models_once(
        root, ledger, clock=lambda: NOW + timedelta(seconds=1)
    ) == (
        "boundary-low",
        "boundary-high",
    )
    report = review_normal_refresh(ledger, manifest)
    assert report.status == "unknown"
    assert report.stopped is True
    before = list(active)
    assert collect_models_once(
        root, ledger, clock=lambda: NOW + timedelta(seconds=2)
    ) == (
        "boundary-low",
        "boundary-high",
    )
    assert active == before
    assert report.provider_real_expiry == "unknown"


@pytest.mark.parametrize("missing_second", [False, True])
def test_normal_refresh_requires_two_distinct_committed_events_in_success_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing_second: bool
) -> None:
    from paper_radar.live_evidence import model_ipc
    from paper_radar.live_evidence.model_worker import (
        ModelObservation,
        ModelObservationV2,
    )
    from paper_radar.pi_execution.auth_metadata import AuthRefreshMetadata

    root, ledger, _collection, manifest, active = setup_collection(
        tmp_path, monkeypatch
    )
    sealed = ModelManifestV2.model_validate(
        json.loads((root / "model-manifest.json").read_bytes()) | {"format_version": 2}
    )
    (root / "model-manifest.json").write_bytes(canonical_bytes(sealed))
    manifest = sealed.model_copy(update={"cells": manifest.cells})
    initialize_epoch(ledger, manifest, now=NOW)
    original = model_ipc.product_worker
    current_time = NOW

    def worker(*args: Any, **kwargs: Any) -> Any:
        observed = original(*args, **kwargs)
        if not isinstance(observed, ModelObservation):
            return observed
        cell = args[2]
        refreshed = cell.use_id in {"boundary-high", "value-low"}
        if missing_second and cell.use_id == "value-low":
            refreshed = False
        return ModelObservationV2(
            **observed.model_dump(),
            format_version=2,
            auth_metadata=AuthRefreshMetadata(
                format_version=1,
                source_id="pi-auth-refresh-1.4.0-v1",
                pid=999999,
                started_at=current_time,
                completed_at=current_time,
                refresh_at=current_time if refreshed else None,
                refresh_called=refreshed,
                need_refresh=True if refreshed else "unknown",
                was_expired_by_pi=False if refreshed else "unknown",
                refresh_succeeded=True if refreshed else "unknown",
                store_committed=True if refreshed else "unknown",
            ),
        )

    monkeypatch.setattr(model_ipc, "product_worker", worker)
    assert review_normal_refresh(ledger, manifest).status == "not_assessed"
    assert collect_models_once(root, ledger, clock=lambda: current_time) == (
        "boundary-low",
    )
    current_time += timedelta(seconds=10)
    assert collect_models_once(root, ledger, clock=lambda: current_time) == (
        "boundary-low",
        "boundary-high",
    )
    assert review_normal_refresh(ledger, manifest).next_batch == "C"
    current_time += timedelta(seconds=10)
    passed = collect_models_once(root, ledger, clock=lambda: current_time)
    report = review_normal_refresh(ledger, manifest)
    assert report.status == ("unknown" if missing_second else "passed")
    assert report.stopped is missing_second
    assert len(passed) == (3 if missing_second else 6)
    assert report.provider_real_expiry == "unknown"
    before = list(active)
    assert collect_models_once(root, ledger, clock=lambda: current_time) == passed
    assert active == before
    assert len({source for source in report.sources}) == 3


def test_deployment_epoch_is_fixed_and_missing_epoch_cannot_be_recreated_after_use(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.live_evidence.ledger import LedgerError
    from paper_radar.live_evidence.normal_auth_refresh import epoch_path, read_epoch

    root, ledger, _collection, manifest, _active = setup_collection(
        tmp_path, monkeypatch
    )
    sealed = ModelManifestV2.model_validate(
        json.loads((root / "model-manifest.json").read_bytes()) | {"format_version": 2}
    )
    (root / "model-manifest.json").write_bytes(canonical_bytes(sealed))
    manifest = sealed.model_copy(update={"cells": manifest.cells})
    initialize_epoch(ledger, manifest, now=NOW)
    original = epoch_path(ledger, manifest).read_bytes()
    initialize_epoch(ledger, manifest, now=NOW + timedelta(hours=1))
    assert epoch_path(ledger, manifest).read_bytes() == original
    assert read_epoch(ledger, manifest).deployed_at == NOW
    assert collect_models_once(root, ledger, clock=lambda: NOW) == ("boundary-low",)
    epoch_path(ledger, manifest).unlink()
    with pytest.raises(LedgerError, match="source_untrusted"):
        initialize_epoch(ledger, manifest, now=NOW + timedelta(hours=2))


def test_72_hour_target_is_disclosure_and_does_not_extend_or_stop_authorization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, ledger, _collection, manifest, active = setup_collection(
        tmp_path, monkeypatch
    )
    sealed = ModelManifestV2.model_validate(
        json.loads((root / "model-manifest.json").read_bytes()) | {"format_version": 2}
    )
    (root / "model-manifest.json").write_bytes(canonical_bytes(sealed))
    manifest = sealed.model_copy(update={"cells": manifest.cells})
    initialize_epoch(ledger, manifest, now=NOW)
    report = review_normal_refresh(ledger, manifest, now=NOW + timedelta(hours=73))
    assert report.target_elapsed is True
    assert report.stopped is False
    assert report.next_batch == "A"
    assert not active


def test_missing_epoch_is_not_recreated_after_an_unfinished_auth_reservation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.live_evidence.ledger import LedgerError
    from paper_radar.live_evidence.normal_auth_refresh import epoch_path

    root, ledger, collection, manifest, _active = setup_collection(
        tmp_path, monkeypatch
    )
    sealed = ModelManifestV2.model_validate(
        json.loads((root / "model-manifest.json").read_bytes()) | {"format_version": 2}
    )
    manifest = sealed.model_copy(update={"cells": manifest.cells})
    initialize_epoch(ledger, manifest, now=NOW)
    cell = manifest.cells[0]
    run = collection.start_round(cell.plan.plan_id, binding=cell.binding, now=NOW)
    collection.reserve(run.round_id, run.case_ids[0], "auth", now=NOW)
    epoch_path(ledger, manifest).unlink()
    with pytest.raises(LedgerError, match="source_untrusted"):
        initialize_epoch(ledger, manifest, now=NOW + timedelta(seconds=1))
