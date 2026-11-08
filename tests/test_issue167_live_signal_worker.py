"""Independent D1 E01 seams; no OS signal, Pi, auth, root, or network."""

import signal
from collections.abc import Iterator
from typing import Any

import pytest

from scripts import issue167_live_signal_case as contract
from scripts import issue167_live_signal_worker as worker

RUN = contract.RUN
FP = "a" * 64


class Session:
    def close_stdin(self) -> None:
        pass

    def terminate(self, timeout: float) -> None:
        pass


def armed() -> tuple[worker.SignalWindow, worker.SignalMeter]:
    window = worker.SignalWindow(RUN, FP)
    meter = worker.SignalMeter(Session(), b"{}\n", "low", window, lambda _row: None)
    window.phase = "model_call"
    meter.prompt_completed = 1
    meter.prompt_ack_count = 1
    meter.prompt_ack_sequence = 10
    meter.agent_start_sequence = 11
    meter.counts["agent_start"] = 1
    return window, meter


def test_signal_does_not_interrupt_auth_or_postprocessing() -> None:
    for phase in (
        "before_auth",
        "auth",
        "prepared",
        "model_cleanup",
        "restoring",
        "complete",
    ):
        window, _ = armed()
        window.phase = phase
        window.receive(signal.SIGINT, None)
        assert window.received == window.late == 1
        assert window.effective == 0


def test_effective_sigint_raises_the_exact_keyboard_interrupt() -> None:
    window, _ = armed()
    with pytest.raises(KeyboardInterrupt) as caught:
        window.receive(signal.SIGINT, None)
    assert caught.value is window.interruption
    assert window.effective == window.received == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("settled", True),
        ("closing", True),
        ("eof", True),
        ("terminated", True),
        ("prompt_completed", 0),
        ("prompt_ack_count", 0),
        ("agent_start_sequence", None),
    ],
)
def test_expired_marker_cannot_trigger_model_interrupt(field: str, value: Any) -> None:
    window, meter = armed()
    setattr(meter, field, value)
    window.receive(signal.SIGINT, None)
    assert window.effective == 0 and window.late == 1


def test_marker_is_published_once_and_never_waits_for_ack() -> None:
    window, _ = armed()
    rows: list[dict[str, object]] = []
    window.observe(rows.append)
    window.observe(rows.append)
    assert len(rows) == 1
    assert contract.validate_marker(rows[0], run_id=RUN, fingerprint=FP) == rows[0]


def test_signal_during_publication_is_not_misrepresented_as_durable() -> None:
    window, _ = armed()
    rows = []

    def publish(value: dict[str, object]) -> None:
        rows.append(value)
        window.receive(signal.SIGINT, None)

    with pytest.raises(KeyboardInterrupt):
        window.observe(publish)
    assert len(rows) == 1 and window.marker_publications == 1
    assert "write_complete" not in rows[0]


def test_cleanup_entry_disarms_before_underlying_cleanup() -> None:
    window, meter = armed()
    meter.close_stdin()
    window.receive(signal.SIGINT, None)
    assert meter.closing and window.effective == 0 and window.late == 1


def test_multiple_signals_are_unknown_and_never_count_as_one() -> None:
    window, meter = armed()
    with pytest.raises(KeyboardInterrupt):
        window.receive(signal.SIGINT, None)
    window.phase = "model_cleanup"
    window.receive(signal.SIGINT, None)
    meter.terminated = True
    with pytest.raises(contract.CaseRejected, match="signal_observation_unknown"):
        window.finish(factory_count=1)


@pytest.mark.parametrize(
    "scenario",
    [
        "effective",
        "normal",
        "late",
        "non_target_ki",
        "transport_after_publication",
        "prepared_postcheck",
        "observer_incomplete",
    ],
)
def test_actual_single_case_chain_distinguishes_interrupt_normal_and_failures(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch, scenario: str
) -> None:
    from contextlib import contextmanager
    from types import SimpleNamespace

    from paper_radar.llm import rpc
    from paper_radar.llm.rpc_types import RpcCandidate, RpcFailure, RpcReason
    from paper_radar.screening import validation
    from scripts import issue167_live_resources as resources
    from scripts import issue167_live_runtime as runtime
    from scripts import issue167_live_worker as old_worker
    from tests.test_issue167_live_signal_case import (
        persistent_auth,
        plan,
        preflight,
        row,
    )

    p = plan()
    op = worker.ApplicationOperations.__new__(worker.ApplicationOperations)
    op.case = p
    op.root = tmp_path
    op.database = tmp_path / "synthetic.sqlite3"
    op.binding = {}
    op.supply = {"supply_id": "1" * 64, "install_id": "2" * 32}
    op.window = worker.SignalWindow(contract.RUN, FP)
    op.manifest = {"cases": [{"snapshot_id": "4" * 64}]}
    op.last_activation = op.last_snapshot = None
    op.auth_metadata_journal = []
    op.journal = []
    monkeypatch.setattr(type(p), "worker_root", property(lambda _self: tmp_path))
    monkeypatch.setattr(op, "wait", lambda *_args: None)
    monkeypatch.setattr(op, "assert_current_expected", lambda: None)
    monkeypatch.setattr(op, "expected_selection", lambda: {})
    monkeypatch.setattr(op, "record_selection", lambda *_args: None)
    monkeypatch.setattr(
        old_worker,
        "guarded_activate",
        lambda *_args: SimpleNamespace(activation_id=9, snapshot_id="4" * 64),
    )
    monkeypatch.setattr(old_worker, "check_core_site", lambda *_args: None)
    monkeypatch.setattr(runtime, "verify_binding", lambda *_args: None)
    monkeypatch.setattr(old_worker, "utc_now", lambda: "2026-11-08T00:00:00+00:00")
    monkeypatch.setattr(
        old_worker,
        "verification_timing",
        lambda started, start: {
            "started_at_utc": started,
            "verified_at_utc": "2026-11-08T00:00:05+00:00",
            "started_monotonic": start,
            "verified_monotonic": start + 5,
            "elapsed_seconds": 5.0,
        },
    )
    desc = SimpleNamespace(
        provider="openai",
        model="gpt-6.1-sol",
        stage="value",
        thinking_level="low",
        protocol="prompt_only",
        sampling="provider_default",
        temperature=None,
        top_p=None,
    )
    monkeypatch.setattr(op, "_input", lambda _name: (desc, b"public synthetic", {}))
    monkeypatch.setattr(validation, "validate_output", lambda *_args: None)
    auth = persistent_auth()

    class Prepared:
        identity = SimpleNamespace(
            supply_id="1" * 64, install_id="2" * 32, proxy_used=False
        )

        def __call__(self, _description: object) -> Session:
            return Session()

    @contextmanager
    def credentials(
        _sequence: int, _description: object
    ) -> Iterator[tuple[Prepared, dict[str, Any]]]:
        try:
            yield Prepared(), auth
        finally:
            if scenario == "prepared_postcheck":
                raise contract.CaseRejected("live_postcheck_unknown")

    monkeypatch.setattr(op, "credential_phase", credentials)

    class Observer:
        receipts = (row()["window"],)

        def assert_complete(self) -> None:
            if scenario == "observer_incomplete":
                raise contract.CaseRejected("resource_window_unknown")

    @contextmanager
    def observed(*_args: object, **_kwargs: object) -> Iterator[Observer]:
        yield Observer()

    monkeypatch.setattr(resources, "observe_launch_resources", observed)

    def run_call(
        description: object, _message: bytes, factory: Any, **_kwargs: object
    ) -> object:
        meter = factory(description)
        template = row(
            expected=scenario
            in {
                "effective",
                "non_target_ki",
                "prepared_postcheck",
                "observer_incomplete",
            }
        )
        meta = template["protocol_metadata"]
        meter.counts = dict(meta["event_counts"])
        meter.records = meta["total_records"]
        meter.prompt_completed = meter.prompt_ack_count = 1
        meter.prompt_ack_sequence = 9
        meter.agent_start_sequence = 10
        meter.clean = meter.commands = True
        try:
            if scenario == "transport_after_publication":
                # A published marker is not a successful publish-return. The
                # public RPC error category remains a failure, even if late.
                meter.window.observe(meter.publish)
                meter.closing = True
                meter.window.phase = "model_cleanup"
                meter.window.receive(signal.SIGINT, None)
                return RpcFailure(RpcReason.TRANSPORT_ERROR)
            if scenario in {"effective", "prepared_postcheck", "observer_incomplete"}:
                meter.window.observe(meter.publish)
                meter.window.receive(signal.SIGINT, None)
            if scenario == "non_target_ki":
                raise KeyboardInterrupt("unrelated synthetic interruption")
            meter.settled = meter.eof = meter.stderr_eof = True
            meter.exit_code = 0
            meter.usage = {
                "input": 10,
                "output": 3,
                "cacheRead": 0,
                "cacheWrite": 0,
                "totalTokens": 13,
            }
            if scenario == "late":
                meter.closing = True
                meter.window.phase = "model_cleanup"
                meter.window.receive(signal.SIGINT, None)
            return RpcCandidate(
                b"public synthetic candidate", "openai", "gpt-6.1-sol", 10, 3
            )
        finally:
            meter.close_stdin()
            meter.terminate(1)

    monkeypatch.setattr(rpc, "run_call", run_call)
    errors: list[BaseException] = []

    class Operations:
        def preflight(self) -> dict[str, object]:
            return preflight()

        def run_case(self) -> dict[str, object]:
            try:
                return op.run_case()
            except BaseException as error:
                errors.append(error)
                raise

        def restore_selection(self) -> dict[str, object]:
            return {
                "result": "original_selection_restored",
                "append_only_history_retained": True,
            }

        def auth_journal(self) -> list[dict[str, object]]:
            return []

    output: Any = worker.run_one(Operations(), run_id=contract.RUN)
    if scenario == "effective":
        assert output["result"] == "observed_expected", [
            (type(e).__name__, e.args) for e in errors
        ]
        assert output["case"]["signal"]["same_keyboard_interrupt_propagated"] is True
    elif scenario in {"normal", "late"}:
        assert output["result"] == "not_triggered", [
            (type(e).__name__, e.args) for e in errors
        ]
        assert output["case"]["normal_candidate_validated"] is True
    else:
        assert output["result"] == "unknown"
        assert output["failure_reason"] == "signal_case_unknown"
    assert output["selection_restoration"]["result"] == "original_selection_restored"
    assert "public synthetic candidate" not in str(output)


@pytest.mark.parametrize("end", ["none", "settled", "eof", "duplicate_start"])
def test_real_event_batch_is_fully_decoded_before_marker_decision(end: str) -> None:
    import json

    from paper_radar.llm.rpc_frames import command_frame
    from paper_radar.llm.rpc_types import SessionEvent

    frame = command_frame("rpc-9", "prompt", message="public synthetic")
    rows = [
        {
            "type": "response",
            "id": "rpc-9",
            "command": "prompt",
            "success": True,
            "data": {"disposition": "started"},
        },
        {"type": "agent_start"},
    ]
    if end == "settled":
        rows.append({"type": "agent_settled"})
    if end == "duplicate_start":
        rows.append({"type": "agent_start"})

    class Peer(Session):
        def pump(self, pending: bytes, _timeout: float) -> SessionEvent:
            return SessionEvent(
                written=len(pending),
                stdout=b"".join(json.dumps(r).encode() + b"\n" for r in rows),
                stdout_eof=end == "eof",
            )

    window = worker.SignalWindow(RUN, FP)
    window.phase = "model_call"
    published: list[dict[str, object]] = []
    meter = worker.SignalMeter(Peer(), frame, "low", window, published.append)
    event = meter.pump(frame, 0.1)
    assert event.written == len(frame)
    assert len(published) == (1 if end == "none" else 0)
