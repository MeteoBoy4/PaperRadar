"""Live-05 的公共派发闸点;只替换 OS/RPC 边界。"""

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from paper_radar.llm.dispatch import DispatchDenied
from paper_radar.llm.rpc import run_call
from paper_radar.pi_execution import prepare_launch
from tests.a8_rpc_support import FakeFactory
from tests.pi_execution_support import launch_inputs
from tests.pi_placement_support import local_placement


def test_prompt_reservation_is_after_initialization_before_first_prompt_byte(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, description, _, _, _ = launch_inputs(tmp_path, monkeypatch)
    description = replace(
        description, provider="provider-a", model="real-model", thinking_level="low"
    )
    factory = FakeFactory()
    seen = []

    def reserve() -> None:
        seen.append([command["type"] for command in factory.sessions[0].commands])
        raise DispatchDenied("resource_unavailable")

    with pytest.raises(DispatchDenied, match="resource_unavailable"):
        run_call(
            description, b"fixed", factory, clock=factory.clock, before_prompt=reserve
        )
    assert seen == [
        [
            "new_session",
            "set_auto_retry",
            "set_auto_compaction",
            "set_model",
            "get_available_thinking_levels",
            "set_thinking_level",
            "get_commands",
            "get_state",
        ]
    ]
    assert all(command["type"] != "prompt" for command in factory.sessions[0].commands)
    assert factory.sessions[0].terminated


def test_auth_reservation_occurs_before_verified_target_release(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database, description, roots, credentials, _ = launch_inputs(tmp_path, monkeypatch)
    local_placement(monkeypatch)
    seen = []

    def reserve(*_metadata: Any) -> None:
        seen.append("auth")
        raise DispatchDenied("resource_unavailable")

    with (
        pytest.raises(DispatchDenied, match="resource_unavailable"),
        prepare_launch(
            database,
            description,
            roots=roots,
            credentials_dir=credentials,
            auth_mode="chatgpt_subscription",
            before_auth=reserve,
        ),
    ):
        pytest.fail("denied auth must not yield launch")
    assert seen == ["auth"]


def test_completed_case_requires_exact_binding_and_keeps_original_time(
    tmp_path: Path,
) -> None:
    from paper_radar.live_evidence.types import BindingComponent as B
    from tests.live_evidence_ledger_support import NOW
    from tests.test_live_collection_v2 import BINDING, collection, finished

    current = collection(tmp_path)
    run = current.start_round("live-plan", binding=BINDING, now=NOW)
    receipt = finished(current, run)
    current.complete_round(receipt, now=NOW)
    found = current.completed_case("auth-model", binding=BINDING)
    assert found == receipt
    assert (
        current.completed_case(
            "auth-model", binding=BINDING | {B.MODEL_TUPLE: "c" * 64}
        )
        is None
    )
    assert not current.ledger.list_received()


def test_collection_uses_actual_latest_install_without_registering_synthetic_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hashlib

    from paper_radar.llm import render_request
    from paper_radar.pi_execution.launcher import CollectionExecutionContext
    from paper_radar.pi_supply import activation_history

    database, description, roots, credentials, _ = launch_inputs(tmp_path, monkeypatch)
    latest = activation_history(database)[-1]
    synthetic = replace(
        description,
        semantic_snapshot_id="f" * 64,
        audit_snapshot_id="f" * 64,
        thinking_level="low",
    )
    context = CollectionExecutionContext(
        "boundary-low",
        "f" * 64,
        hashlib.sha256(render_request(synthetic)).hexdigest(),
        latest.snapshot_id,
        latest.supply_id,
        latest.install_id,
    )
    with prepare_launch(
        database,
        synthetic,
        roots=roots,
        credentials_dir=credentials,
        auth_mode="chatgpt_subscription",
        collection=context,
    ) as launch:
        assert launch.identity.install_id == latest.install_id
    assert activation_history(database)[-1] == latest


@pytest.mark.parametrize(
    "changes", [{"model": "wrong-model"}, {"api": "openai-responses-websocket"}]
)
def test_collection_rpc_safety_metadata_stops_without_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, changes: dict[str, str]
) -> None:
    from paper_radar.llm.rpc_types import RpcAudit, RpcFailure, RpcReason

    _, description, _, _, _ = launch_inputs(tmp_path, monkeypatch)
    description = replace(
        description, provider="provider-a", model="real-model", thinking_level="low"
    )

    def mutate(name: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if name == "prompt":
            for record in records:
                if (
                    record.get("type") == "message_start"
                    and record.get("message", {}).get("role") == "assistant"
                ):
                    record["message"].update(changes)
        return records

    factory = FakeFactory(mutate=mutate)
    audit = RpcAudit()
    result = run_call(description, b"fixed", factory, clock=factory.clock, audit=audit)
    assert isinstance(result, RpcFailure) and result.reason == RpcReason.MODEL_STATE
    assert audit.identity_mismatch
    assert factory.sessions[0].terminated


def test_terminal_metadata_and_deletion_are_observed_separately(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.pi_execution.resources import CleanupAudit

    database, description, roots, credentials, _ = launch_inputs(tmp_path, monkeypatch)
    audit = CleanupAudit()
    with prepare_launch(
        database,
        description,
        roots=roots,
        credentials_dir=credentials,
        auth_mode="chatgpt_subscription",
        cleanup_audit=audit,
    ) as launch:
        session = launch(description)
        session.terminate(2)
    assert (
        audit.auth_terminal,
        audit.auth_deleted,
        audit.model_terminal,
        audit.model_deleted,
    ) == (True, True, True, True)
