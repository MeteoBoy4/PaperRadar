"""Independent D1 timeout observation; no real Pi, auth, network or signals."""

import json
import time
from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

import pytest

from paper_radar.llm.rpc_frames import command_frame
from paper_radar.llm.rpc_types import SessionEvent
from scripts import issue167_live_timeout_case as contract
from scripts import issue167_live_timeout_worker as worker
from tests.test_issue167_live_timeout_case import FP, persistent_auth, plan, row


class Session:
    def close_stdin(self) -> None:
        pass

    def terminate(self, timeout: float) -> None:
        pass


def response() -> dict[str, object]:
    return {
        "type": "response",
        "id": "rpc-9",
        "command": "prompt",
        "success": True,
        "data": {"disposition": "started"},
    }


def update(
    kind: str = "text_delta", delta: Any = "synthetic content"
) -> dict[str, object]:
    return {
        "type": "message_update",
        "assistantMessageEvent": {
            "type": kind,
            "delta": delta,
            "contentIndex": 0,
        },
    }


@pytest.mark.parametrize(
    "tail",
    [
        "none",
        "message_end",
        "turn_end",
        "agent_end",
        "agent_settled",
        "stdout_eof",
        "stderr_eof",
        "exit",
        "duplicate_start",
    ],
)
def test_entire_real_batch_is_observed_before_first_text_marker(tail: str) -> None:
    frame = command_frame("rpc-9", "prompt", message="public synthetic")
    records: list[dict[str, object]] = [response(), {"type": "agent_start"}, update()]
    if tail in {"message_end", "turn_end", "agent_end", "agent_settled"}:
        records.append({"type": tail})
    if tail == "duplicate_start":
        records.append({"type": "agent_start"})
    expected = SessionEvent(
        written=len(frame),
        stdout=b"".join(json.dumps(r).encode() + b"\n" for r in records),
        stdout_eof=tail == "stdout_eof",
        stderr_eof=tail == "stderr_eof",
        exit_code=0 if tail == "exit" else None,
    )

    class Peer(Session):
        def pump(self, _pending: bytes, _timeout: float) -> SessionEvent:
            return expected

    window = worker.TimeoutWindow(contract.RUN, FP)
    window.phase = "model_call"
    published: list[dict[str, object]] = []
    meter = worker.TimeoutMeter(Peer(), frame, "low", window, published.append)
    assert meter.pump(frame, 0.1) is expected
    assert len(published) == int(tail == "none")
    if published:
        assert "synthetic content" not in json.dumps(published)
        assert published[0]["text_delta_sequence"] == 3
        assert contract.validate_marker(
            published[0], run_id=contract.RUN, fingerprint=FP
        )


@pytest.mark.parametrize(
    "kind,delta",
    [
        ("thinking_delta", "reason"),
        ("text_delta", ""),
        ("text_delta", 1),
        ("text_start", "x"),
    ],
)
def test_non_text_or_empty_content_never_arms_drop(kind: str, delta: Any) -> None:
    frame = command_frame("rpc-9", "prompt", message="public synthetic")
    data = b"".join(
        json.dumps(r).encode() + b"\n"
        for r in [response(), {"type": "agent_start"}, update(kind, delta)]
    )

    class Peer(Session):
        def pump(self, pending: bytes, _timeout: float) -> SessionEvent:
            return SessionEvent(written=len(pending), stdout=data)

    window = worker.TimeoutWindow(contract.RUN, FP)
    window.phase = "model_call"
    published: list[dict[str, object]] = []
    meter = worker.TimeoutMeter(Peer(), frame, "low", window, published.append)
    meter.pump(frame, 0.1)
    assert not published


def test_partial_text_frame_then_eof_is_observation_failure() -> None:
    from paper_radar.llm.rpc_types import RpcProblem

    frame = command_frame("rpc-9", "prompt", message="public synthetic")
    initial = b"".join(
        json.dumps(r).encode() + b"\n" for r in [response(), {"type": "agent_start"}]
    )
    events = iter(
        [
            SessionEvent(
                written=len(frame), stdout=initial + b'{"type":"message_update"'
            ),
            SessionEvent(stdout_eof=True),
        ]
    )

    class Peer(Session):
        def pump(self, _pending: bytes, _timeout: float) -> SessionEvent:
            return next(events)

    published: list[dict[str, object]] = []
    window = worker.TimeoutWindow(contract.RUN, FP)
    window.phase = "model_call"
    meter = worker.TimeoutMeter(Peer(), frame, "low", window, published.append)
    meter.pump(frame, 0.1)
    with pytest.raises(RpcProblem) as caught:
        meter.pump(b"", 0.1)
    assert caught.value.reason.value == "partial_frame"
    assert not published


def test_marker_is_single_and_publication_failure_does_not_become_success() -> None:
    window = worker.TimeoutWindow(contract.RUN, FP)
    window.phase = "model_call"
    meter = worker.TimeoutMeter(Session(), b"{}\n", "low", window, lambda _row: None)
    meter.prompt_completed = meter.prompt_ack_count = 1
    meter.prompt_ack_sequence = 1
    meter.agent_start_sequence = 2
    meter.counts["agent_start"] = 1
    calls = []

    def publish(value: object) -> None:
        calls.append(value)
        raise ValueError("synthetic observer failure")

    with pytest.raises(ValueError, match="synthetic observer failure"):
        window.observe(3, publish)
    window.observe(4, calls.append)
    assert len(calls) == 1 and window.marker_publications == 1


@pytest.mark.parametrize(
    "scenario",
    [
        "timeout",
        "normal",
        "buffered_normal",
        "early_sdk",
        "model_rejected",
        "transport",
        "too_short",
        "observer_failure",
        "prepare_postcheck",
        "publication_failure",
    ],
)
def test_actual_single_case_public_chain_keeps_cleanup_and_fails_closed(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch, scenario: str
) -> None:
    from paper_radar.llm import rpc
    from paper_radar.llm.rpc_types import RpcCandidate, RpcFailure, RpcReason
    from paper_radar.screening import validation
    from scripts import issue167_live_resources as resources
    from scripts import issue167_live_runtime as runtime
    from scripts import issue167_live_worker as old_worker
    from tests.test_issue167_live_signal_case import preflight

    p = plan()
    op = worker.ApplicationOperations.__new__(worker.ApplicationOperations)
    op.case = p
    op.root = tmp_path
    op.database = tmp_path / "synthetic.sqlite3"
    op.binding = {}
    op.supply = {"supply_id": "1" * 64, "install_id": "2" * 32}
    op.window = worker.TimeoutWindow(contract.RUN, FP)
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
    now = [10.0]
    monkeypatch.setattr(time, "monotonic", lambda: now[0])
    monkeypatch.setattr(old_worker, "utc_now", lambda: "2026-11-08T00:00:00+00:00")
    monkeypatch.setattr(
        old_worker,
        "verification_timing",
        lambda started, start: {
            "started_at_utc": started,
            "verified_at_utc": "2026-11-08T00:05:05+00:00",
            "started_monotonic": start,
            "verified_monotonic": now[0],
            "elapsed_seconds": now[0] - start,
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
            yield Prepared(), persistent_auth()
        finally:
            if scenario == "prepare_postcheck":
                raise contract.CaseRejected("live_postcheck_unknown")

    monkeypatch.setattr(op, "credential_phase", credentials)

    class Observer:
        receipts = (row()["window"],)

        def assert_complete(self) -> None:
            if scenario == "observer_failure":
                raise contract.CaseRejected("resource_window_unknown")

    @contextmanager
    def observed(*_args: object, **_kwargs: object) -> Iterator[Observer]:
        yield Observer()

    monkeypatch.setattr(resources, "observe_launch_resources", observed)
    calls = []

    def run_call(
        description: object, _message: bytes, factory: Any, **kwargs: object
    ) -> object:
        calls.append(kwargs)
        assert "clock" not in kwargs and "limits" not in kwargs
        meter = factory(description)
        template = row(
            reason="candidate"
            if scenario in {"normal", "buffered_normal"}
            else "timeout"
        )
        meta = template["protocol_metadata"]
        meter.counts = dict(meta["event_counts"])
        meter.records = meta["total_records"]
        meter.prompt_completed = meter.prompt_ack_count = 1
        meter.prompt_ack_sequence = 9
        meter.agent_start_sequence = 10
        meter.clean = meter.commands = True
        try:
            if scenario not in {"normal", "early_sdk", "model_rejected"}:
                if scenario == "publication_failure":

                    def broken(_value: object) -> None:
                        raise ValueError("synthetic observer failure")

                    meter.window.observe(11, broken)
                else:
                    meter.window.observe(11, meter.publish)
            now[0] += (
                299.9
                if scenario == "too_short"
                else 300.1
                if scenario in {"timeout", "observer_failure", "prepare_postcheck"}
                else 1.0
            )
            if scenario in {"normal", "buffered_normal"}:
                meter.settled = meter.eof = meter.stderr_eof = True
                meter.exit_code = 0
                meter.usage = {
                    "input": 10,
                    "output": 3,
                    "cacheRead": 0,
                    "cacheWrite": 0,
                    "totalTokens": 13,
                }
                return RpcCandidate(
                    b"public synthetic candidate", "openai", "gpt-6.1-sol", 10, 3
                )
            if scenario == "early_sdk":
                meter.model_error_terminal_count = 1
                return RpcFailure(RpcReason.STOP_REASON)
            if scenario == "model_rejected":
                return RpcFailure(RpcReason.MODEL_REJECTED)
            if scenario == "transport":
                return RpcFailure(RpcReason.TRANSPORT_ERROR)
            return RpcFailure(RpcReason.TIMEOUT)
        finally:
            meter.close_stdin()
            meter.terminate(1)

    monkeypatch.setattr(rpc, "run_call", run_call)
    errors = []

    class Operations:
        def preflight(self) -> dict[str, object]:
            return preflight()

        def run_case(self) -> dict[str, object]:
            try:
                return op.run_case()
            except BaseException as error:
                errors.append((type(error).__name__, error.args))
                raise

        def restore_selection(self) -> dict[str, object]:
            return {
                "result": "original_selection_restored",
                "append_only_history_retained": True,
            }

        def auth_journal(self) -> list[dict[str, object]]:
            return []

    result: Any = worker.run_one(Operations(), run_id=contract.RUN)
    expected = (
        "observed_expected"
        if scenario == "timeout"
        else "not_triggered"
        if scenario in {"normal", "buffered_normal", "early_sdk", "model_rejected"}
        else "unknown"
    )
    assert result["result"] == expected, errors
    assert result["selection_restoration"]["result"] == "original_selection_restored"
    assert len(calls) == 1
    assert "public synthetic candidate" not in json.dumps(result)


def test_user_and_system_message_end_are_not_assistant_terminal() -> None:
    frame = command_frame("rpc-9", "prompt", message="public synthetic")
    records = [
        response(),
        {"type": "agent_start"},
        {"type": "message_start", "message": {"role": "system"}},
        {"type": "message_end", "message": {"role": "system"}},
        {"type": "message_start", "message": {"role": "user"}},
        {"type": "message_end", "message": {"role": "user"}},
        {"type": "message_start", "message": {"role": "assistant"}},
        update(),
    ]
    expected = SessionEvent(
        written=len(frame),
        stdout=b"".join(json.dumps(r).encode() + b"\n" for r in records),
    )

    class Peer(Session):
        def pump(self, _pending: bytes, _timeout: float) -> SessionEvent:
            return expected

    window = worker.TimeoutWindow(contract.RUN, FP)
    window.phase = "model_call"
    published: list[dict[str, object]] = []
    meter = worker.TimeoutMeter(Peer(), frame, "low", window, published.append)
    meter.pump(frame, 0.1)
    assert len(published) == 1
    assert published[0]["text_delta_sequence"] == 8


def test_timeout_identity_has_conditional_refresh_and_no_signal() -> None:
    assert contract.RUN == "8b31f0a9d672"
    assert contract.AUTH_REFRESH_PLAN == "conditional_zero_or_one"
    assert worker.TimeoutWindow(contract.RUN, "a" * 64).marker_publications == 0
