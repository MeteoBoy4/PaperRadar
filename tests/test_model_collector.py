"""Live-05 root 完成闭环与有限观察,不运行现场入口。"""

from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from paper_radar.live_evidence.collection import Operation
from paper_radar.live_evidence.model_collector import complete_model_case
from paper_radar.live_evidence.model_worker import ModelObservation
from paper_radar.live_evidence.receipt import content_sha256
from paper_radar.live_evidence.receipt_v2 import ApprovedPlanV2
from paper_radar.llm.rpc_types import RpcReason
from tests.live_evidence_ledger_support import NOW
from tests.test_live_collection_v2 import BINDING, collection


def test_root_completion_publishes_only_this_cell_claims_and_does_not_receive(
    tmp_path: Path,
) -> None:
    current = collection(tmp_path)
    plan = ApprovedPlanV2.model_validate(
        {
            **current.ledger.show_plan("live-plan").model_dump(),
            "plan_id": "boundary-low-plan",
            "cases": ["model-boundary-low"],
        }
    )
    current.approve_plan(plan, now=NOW)
    run = current.start_round(plan.plan_id, binding=BINDING, now=NOW)
    operations: tuple[Operation, ...] = ("auth", "model")
    reservations = [
        current.reserve(run.round_id, run.case_ids[0], op, now=NOW) for op in operations
    ]
    observed = ModelObservation(
        passed=True,
        authority="boundary",
        initialized=True,
        settled=True,
        eof=True,
        terminated=True,
        terminal_clean=True,
        deleted=True,
        input_tokens=None,
        output_tokens=None,
    )
    source = complete_model_case(
        current,
        plan,
        run,
        "boundary-low",
        observed,
        tuple(reservations),
        ipv4_verified=True,
        now=NOW + timedelta(seconds=1),
    )
    receipt = current.completed_case("model-boundary-low", binding=BINDING)
    assert receipt is not None and content_sha256(receipt) in source.name
    assert len(receipt.claims) == 7
    assert {claim.use_id for claim in receipt.claims} == {"boundary-low"}
    assert {claim.status.value for claim in receipt.claims} == {"verified"}
    assert not current.ledger.list_received()
    assert current.status(plan.plan_id, now=NOW).model_used == 1


def test_fixed_root_entry_resumes_six_cells_without_refreshing_claims(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.live_evidence.model_collector import collect_models_once
    from tests.model_collection_support import setup_collection

    runtime, ledger, collection, manifest, active = setup_collection(
        tmp_path, monkeypatch
    )
    from paper_radar.live_evidence.model_collector import site_prerequisite

    site_prerequisite(runtime, ledger, manifest, manifest.cells[0], now=NOW)
    assert collect_models_once(runtime, ledger, clock=lambda: NOW) == (
        "boundary-low",
        "boundary-high",
        "value-low",
        "value-high",
        "read-low",
        "read-high",
    )
    assert len(active) == 10
    before = collection.completed_receipts()
    assert len(before) == 7
    assert collect_models_once(
        runtime, ledger, clock=lambda: NOW + timedelta(seconds=1)
    ) == (
        "boundary-low",
        "boundary-high",
        "value-low",
        "value-high",
        "read-low",
        "read-high",
    )
    assert len(active) == 10
    assert collection.completed_receipts() == before
    assert not ledger.list_received()
    assert collection.status(manifest.cells[0].plan.plan_id, now=NOW).model_used == 6
    assert collection.status(manifest.cells[0].plan.plan_id, now=NOW).network_used == 10


def test_failed_cell_stops_group_then_resumes_exact_template_preserving_prior_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.live_evidence import model_ipc
    from paper_radar.live_evidence.model_collector import collect_models_once
    from tests.model_collection_support import setup_collection

    runtime, ledger, collection, manifest, active = setup_collection(
        tmp_path, monkeypatch
    )
    actual = model_ipc.product_worker
    fail = [True]

    def worker(*args: Any) -> Any:
        result = actual(*args)
        cell = args[2]
        if cell is not None and cell.use_id == "boundary-high" and fail[0]:
            return ModelObservation(
                passed=False,
                authority="none",
                failure="protocol_failed",
                rpc_reason=RpcReason.USAGE_SHAPE,
            )
        return result

    monkeypatch.setattr(model_ipc, "product_worker", worker)
    assert collect_models_once(runtime, ledger, clock=lambda: NOW) == ("boundary-low",)
    low = collection.completed_case(
        "model-boundary-low", binding=manifest.cells[0].binding
    )
    assert active[-2:] == ["model-boundary-low", "model-boundary-high"]
    assert not any(case.startswith("model-value") for case in active)
    fail[0] = False
    assert (
        len(
            collect_models_once(
                runtime, ledger, clock=lambda: NOW + timedelta(seconds=1)
            )
        )
        == 6
    )
    assert (
        collection.completed_case(
            "model-boundary-low", binding=manifest.cells[0].binding
        )
        == low
    )
    assert active.count("model-boundary-low") == 1
    assert active.count("model-boundary-high") == 2
    assert not ledger.list_received()


def test_current_observation_alone_cannot_replace_site_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import pytest

    from paper_radar.live_evidence.model_collector import collect_models_once
    from paper_radar.llm.dispatch import DispatchDenied
    from tests.model_collection_support import setup_collection

    runtime, ledger, collection, manifest, active = setup_collection(
        tmp_path, monkeypatch
    )
    (ledger.root / "inbox/site-fixed-round-1.json").unlink()
    with pytest.raises(DispatchDenied, match="source_untrusted"):
        collect_models_once(runtime, ledger, clock=lambda: NOW)
    assert not active
    status = collection.status(manifest.cells[0].plan.plan_id, now=NOW)
    assert status.auth_used == status.model_used == status.independent_network_used == 0


def test_safety_failure_first_stops_shared_domain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import pytest

    from paper_radar.live_evidence import model_ipc
    from paper_radar.live_evidence.ledger import LedgerError
    from paper_radar.live_evidence.model_collector import collect_models_once
    from tests.model_collection_support import setup_collection

    runtime, ledger, collection, manifest, active = setup_collection(
        tmp_path, monkeypatch
    )
    actual = model_ipc.product_worker

    def worker(*args: Any) -> Any:
        observed = actual(*args)
        return (
            ModelObservation(
                passed=False, authority="none", failure="identity_mismatch"
            )
            if args[2] is not None
            else observed
        )

    monkeypatch.setattr(model_ipc, "product_worker", worker)
    assert collect_models_once(runtime, ledger, clock=lambda: NOW) == ()
    assert (
        collection.status(manifest.cells[-1].plan.plan_id, now=NOW).stop_reason
        == "identity_mismatch"
    )
    with pytest.raises(LedgerError, match="plan_stopped"):
        collect_models_once(runtime, ledger, clock=lambda: NOW)
    assert len(active) == 5


def test_completed_receipt_publication_recovers_without_repeating_external_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.live_evidence import model_collector
    from tests.model_collection_support import setup_collection

    runtime, ledger, collection, manifest, active = setup_collection(
        tmp_path, monkeypatch
    )
    from paper_radar.live_evidence.sealed_runtime import _publish

    publish = _publish
    failed = [False]

    def interrupted(path: Path, data: bytes, **kwargs: Any) -> None:
        if path.name.startswith("model-") and not failed[0]:
            failed[0] = True
            raise OSError("synthetic publication interruption")
        publish(path, data, **kwargs)

    monkeypatch.setattr(model_collector, "_publish", interrupted)
    with pytest.raises(OSError, match="synthetic publication interruption"):
        model_collector.collect_models_once(runtime, ledger, clock=lambda: NOW)
    receipt = collection.completed_case(
        "model-boundary-low", binding=manifest.cells[0].binding
    )
    assert receipt is not None
    source = ledger.root / "inbox" / ("model-" + content_sha256(receipt) + ".json")
    assert not source.exists()
    assert list(ledger.root.glob("publish-*.pending"))
    assert (
        len(model_collector.collect_models_once(runtime, ledger, clock=lambda: NOW))
        == 6
    )
    from paper_radar.live_evidence.receipt import canonical_bytes

    assert source.read_bytes() == canonical_bytes(receipt)
    assert len(active) == 10
    assert not list(ledger.root.glob("publish-*.pending"))


def test_lost_published_source_is_not_recreated_as_interrupted_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.live_evidence.ledger import LedgerError
    from paper_radar.live_evidence.model_collector import collect_models_once
    from tests.model_collection_support import setup_collection

    runtime, ledger, collection, manifest, active = setup_collection(
        tmp_path, monkeypatch
    )
    collect_models_once(runtime, ledger, clock=lambda: NOW)
    receipt = collection.completed_case(
        "model-boundary-low", binding=manifest.cells[0].binding
    )
    assert receipt is not None
    source = ledger.root / "inbox" / ("model-" + content_sha256(receipt) + ".json")
    source.unlink()
    with pytest.raises(LedgerError, match="source_untrusted"):
        collect_models_once(runtime, ledger, clock=lambda: NOW)
    assert not source.exists() and len(active) == 10


def test_fixed_model_entry_rejects_arguments_before_any_root_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from paper_radar.live_evidence.model_collector import model_collector_main
    from paper_radar.live_evidence.sealed_runtime import runtime_main

    assert model_collector_main(["arbitrary-input"]) == 2
    monkeypatch.setattr("sys.argv", ["entry.py", "collect-models", "arbitrary-input"])
    assert runtime_main() == 2


def test_payload_does_not_require_postdeployment_binding_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    from tests.model_collection_support import setup_collection

    runtime, _, _, _, _ = setup_collection(tmp_path, monkeypatch)
    manifest = json.loads((runtime / "model-manifest.json").read_bytes())
    for cell in manifest["cells"]:
        assert (
            not {"observer", "ipv4_egress", "auth_cache_baseline", "cwd_ancestors"}
            & cell["binding"].keys()
        )
    assert "egress_digest" not in manifest["network"]
    assert "rule_handles" not in manifest["network"]


def test_runtime_binding_source_cannot_be_recreated_after_completed_collection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.live_evidence.model_collector import collect_models_once
    from paper_radar.llm.dispatch import DispatchDenied
    from tests.model_collection_support import setup_collection

    runtime, ledger, _, _, active = setup_collection(tmp_path, monkeypatch)
    collect_models_once(runtime, ledger, clock=lambda: NOW)
    sources = list((ledger.root / "inbox").glob("collection-bindings-*.json"))
    assert len(sources) == 1
    sources[0].unlink()
    with pytest.raises(DispatchDenied, match="source_untrusted"):
        collect_models_once(runtime, ledger, clock=lambda: NOW)
    assert len(active) == 10 and not sources[0].exists()
