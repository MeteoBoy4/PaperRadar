"""通过公共单次调用验证取消锁定与有界收尾。"""

import ast
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from paper_radar.llm.models import CallDescription
from paper_radar.llm.rpc import run_call
from paper_radar.llm.rpc_types import (
    RpcCandidate,
    RpcFailure,
    RpcLimits,
    RpcReason,
    SessionEvent,
)
from paper_radar.papers import PaperFacts
from paper_radar.screening_tasks import (
    FailureKind,
    FailureReceipt,
    ScreeningTasks,
    SuccessReceipt,
)
from tests.a8_call_support import archive, prepare_call, request_for
from tests.a8_rpc_support import FakeClock, FakeFactory, ScriptedSession, wire
from tests.a8_rpc_task_support import run_attempt
from tests.test_paper_mapping import screening_fields
from tests.test_paper_service import observation

FAST = RpcLimits(initialization=0.2, total=0.5, close=0.2, terminate=0.2, poll=0.01)


@pytest.fixture(scope="module")
def description(tmp_path_factory: pytest.TempPathFactory) -> CallDescription:
    data = archive(tmp_path_factory.mktemp("rpc-lifecycle"))
    tasks = ScreeningTasks(data.database)
    receipt = tasks.register(request_for(data))
    return prepare_call(tasks, receipt.receipt_id)


class CancelSession(ScriptedSession):
    cancel_reply: str = "normal"

    def pump(self, pending: bytes, timeout: float) -> SessionEvent:
        if pending and json.loads(pending)["type"] in {"clear_queue", "abort"}:
            command = json.loads(pending)
            self.commands.append(command)
            response = {
                "type": "response",
                "id": command["id"],
                "command": command["type"],
                "success": True,
                "data": {"steering": ["QUEUE_SECRET"], "followUp": []},
            }
            if self.cancel_reply == "wrong_id":
                response["id"] = "unrelated"
            elif self.cancel_reply == "wrong_command":
                response["command"] = "prompt"
            elif self.cancel_reply == "rejected":
                response["success"] = False
            elif self.cancel_reply == "bad_data":
                response["data"] = []
            elif self.cancel_reply == "missing_data":
                del response["data"]
            elif self.cancel_reply == "empty_data":
                response["data"] = {}
            elif self.cancel_reply == "empty_queue":
                response["data"] = {"steering": [], "followUp": []}
            elif self.cancel_reply == "missing_steering":
                response["data"] = {"followUp": []}
            elif self.cancel_reply == "missing_followup":
                response["data"] = {"steering": []}
            elif self.cancel_reply == "steering_not_array":
                response["data"] = {"steering": "text", "followUp": []}
            elif self.cancel_reply == "followup_not_array":
                response["data"] = {"steering": [], "followUp": None}
            elif self.cancel_reply == "steering_non_string":
                response["data"] = {"steering": [True], "followUp": []}
            elif self.cancel_reply == "followup_non_string":
                response["data"] = {"steering": [], "followUp": [123]}
            if self.cancel_reply != "lost":
                self.pending.append(wire([response]))
            return SessionEvent(written=len(pending))
        return super().pump(pending, timeout)


@pytest.mark.parametrize("reply", ["normal", "empty_queue"])
def test_cancellation_clears_queue_then_aborts_and_never_accepts_late_completion(
    description: CallDescription,
    reply: str,
) -> None:
    desc = description
    clock = FakeClock()
    session = CancelSession(desc, clock=clock)
    session.cancel_reply = reply
    result = run_call(
        desc,
        b"request",
        lambda _: session,
        clock=clock,
        cancelled=lambda: len(session.commands) >= 9,
        limits=FAST,
    )
    assert result == RpcFailure(RpcReason.CANCELLED)
    assert [command["type"] for command in session.commands[-2:]] == [
        "clear_queue",
        "abort",
    ]
    assert session.commands[-2]["id"] != session.commands[-1]["id"]
    assert session.closed and session.terminated
    assert "QUEUE_SECRET" not in repr(result)


def test_success_also_reclaims_group_and_closes_handles(
    description: CallDescription,
) -> None:
    desc = description
    session = ScriptedSession(desc)
    result = run_call(desc, b"request", lambda _: session, clock=session.clock)
    assert isinstance(result, RpcCandidate)
    assert session.closed and session.terminated


@pytest.mark.parametrize(
    "reply",
    [
        "wrong_id",
        "wrong_command",
        "rejected",
        "bad_data",
        "lost",
        "missing_data",
        "empty_data",
        "missing_steering",
        "missing_followup",
        "steering_not_array",
        "followup_not_array",
        "steering_non_string",
        "followup_non_string",
    ],
)
def test_unmatched_clear_queue_never_sends_abort(
    description: CallDescription, reply: str
) -> None:
    session = CancelSession(description)
    session.cancel_reply = reply
    result = run_call(
        description,
        b"request",
        lambda _: session,
        clock=session.clock,
        cancelled=lambda: len(session.commands) >= 9,
        limits=FAST,
    )
    assert result == RpcFailure(RpcReason.CANCELLED)
    assert session.commands[-1]["type"] == "clear_queue"
    assert session.closed and session.terminated
    assert session.clock.now <= 0.21


def test_cancel_after_settled_closes_without_sending_more_commands(
    description: CallDescription,
) -> None:
    session = CancelSession(description)
    result = run_call(
        description,
        b"request",
        lambda _: session,
        clock=session.clock,
        cancelled=lambda: session.closed,
        limits=FAST,
    )
    assert result == RpcFailure(RpcReason.CANCELLED)
    assert len(session.commands) == 9
    assert session.terminated


class EdgeSession(ScriptedSession):
    scenario: str = "normal"

    def pump(self, pending: bytes, timeout: float) -> SessionEvent:
        if self.scenario == "write_stall" and pending:
            self.clock.now += timeout
            return SessionEvent()
        if self.scenario == "partial_write":
            return super().pump(pending[:7], timeout)
        if self.scenario == "idle":
            self.clock.now += timeout
            return SessionEvent()
        if self.closed:
            if self.scenario == "close_stall":
                self.clock.now += timeout
                return SessionEvent()
            if self.scenario == "nonzero":
                return SessionEvent(stdout_eof=True, stderr_eof=True, exit_code=17)
            if self.scenario == "exit_without_eof":
                self.clock.now += timeout
                return SessionEvent(exit_code=0)
            if self.scenario == "extra_stdout":
                return SessionEvent(
                    stdout=b'{"type":"agent_settled","aborted":false}\n'
                )
        event = super().pump(pending, timeout)
        if self.scenario == "transport":
            raise OSError("SENSITIVE_TRANSPORT_SECRET")
        return event

    def close_stdin(self) -> None:
        super().close_stdin()
        if self.scenario == "close_error":
            raise OSError("SENSITIVE_CLOSE_SECRET")

    def terminate(self, timeout: float) -> None:
        super().terminate(timeout)
        if self.scenario == "terminate_error":
            raise OSError("SENSITIVE_TERMINATE_SECRET")


@pytest.mark.parametrize(
    ("scenario", "reason"),
    [
        ("idle", RpcReason.TIMEOUT),
        ("write_stall", RpcReason.TIMEOUT),
        ("close_stall", RpcReason.CLOSE_TIMEOUT),
        ("exit_without_eof", RpcReason.CLOSE_TIMEOUT),
        ("nonzero", RpcReason.UNEXPECTED_EXIT),
        ("extra_stdout", RpcReason.EVENT_SEQUENCE),
        ("transport", RpcReason.TRANSPORT_ERROR),
        ("close_error", RpcReason.TRANSPORT_ERROR),
        ("terminate_error", RpcReason.TRANSPORT_ERROR),
    ],
)
def test_bounded_lifecycle_failures_return_controlled_reason(
    description: CallDescription, scenario: str, reason: RpcReason
) -> None:
    session = EdgeSession(description)
    session.scenario = scenario
    result = run_call(
        description, b"request", lambda _: session, clock=session.clock, limits=FAST
    )
    assert result == RpcFailure(reason)
    assert session.closed and session.terminated
    assert "SENSITIVE" not in repr(result)


def test_partial_writes_preserve_exact_single_request(
    description: CallDescription,
) -> None:
    session = EdgeSession(description)
    session.scenario = "partial_write"
    message = "中文/emoji 😀\n".encode() * 10
    result = run_call(
        description, message, lambda _: session, clock=session.clock, limits=FAST
    )
    assert isinstance(result, RpcCandidate)
    assert session.commands[-1]["message"].encode() == message
    assert len(session.commands) == 9


@pytest.mark.parametrize("interruption", [KeyboardInterrupt(), SystemExit(42)])
def test_process_interruptions_clean_up_and_propagate_original_object(
    description: CallDescription, interruption: BaseException
) -> None:
    class Interrupted(EdgeSession):
        def pump(self, pending: bytes, timeout: float) -> SessionEvent:
            raise interruption

    session = Interrupted(description)
    session.scenario = "close_error"
    with pytest.raises(type(interruption)) as caught:
        run_call(
            description, b"request", lambda _: session, clock=session.clock, limits=FAST
        )
    assert caught.value is interruption
    assert session.closed and session.terminated


@pytest.mark.parametrize("interruption", [KeyboardInterrupt(), SystemExit(42)])
@pytest.mark.parametrize("phase", ["communication", "cleanup"])
def test_interrupt_leaves_a7_unsettled_until_existing_lease_recovery(
    tmp_path: Path, interruption: BaseException, phase: str
) -> None:
    data = archive(tmp_path)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    tasks = ScreeningTasks(data.database, data.data_root, clock=lambda: now)
    receipt = tasks.register(request_for(data))

    class CleanupSession(ScriptedSession):
        interrupted = False

        def terminate(self, timeout: float) -> None:
            if phase == "cleanup" and not self.interrupted:
                self.interrupted = True
                raise interruption
            super().terminate(timeout)

    session = CleanupSession(prepare_call(tasks, receipt.receipt_id))

    def cancelled() -> bool:
        if phase == "communication" and len(session.commands) == 9:
            raise interruption
        return False

    with pytest.raises(type(interruption)) as caught:
        run_attempt(
            tasks,
            receipt.receipt_id,
            lambda _: session,
            cancelled=cancelled,
            clock=session.clock,
            limits=FAST,
        )
    assert caught.value is interruption
    assert session.closed and session.terminated
    status = tasks.status(receipt.receipt_id)
    assert status.state == "running" and status.last_failure is None
    assert status.used_attempts == 1
    now += timedelta(seconds=601)
    recovered = tasks.reclaim(receipt.receipt_id)
    assert recovered.last_failure is FailureKind.OUTCOME_UNKNOWN
    assert recovered.remaining_attempts == 1


@pytest.mark.parametrize(
    "scenario", ["idle", "transport", "close_error", "terminate_error"]
)
def test_failed_lifecycle_cannot_publish_or_contaminate_next_paper(
    tmp_path: Path, scenario: str
) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(
        data.database, data.data_root, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    receipt = tasks.register(request_for(data))
    session = EdgeSession(prepare_call(tasks, receipt.receipt_id))
    session.scenario = scenario
    result = run_attempt(
        tasks, receipt.receipt_id, lambda _: session, clock=session.clock, limits=FAST
    )
    assert isinstance(result, FailureReceipt)
    assert result.kind is (
        FailureKind.TIMEOUT if scenario == "idle" else FailureKind.EXECUTOR_ERROR
    )
    assert result.origin == "executor"
    assert tasks.status(receipt.receipt_id).remaining_attempts == 1
    assert (
        tasks.query_successes(
            paper_id=data.paper_id, stage="boundary", snapshot_id=data.snapshot_id
        )
        == ()
    )
    second = PaperFacts(data.database, data.data_root).submit(
        observation(
            doi="10.1234/rpc-after-lifecycle",
            fields=screening_fields(title="Independent lifecycle paper"),
        )
    )
    next_receipt = tasks.register(request_for(data, paper_id=second.paper_id))
    factory = FakeFactory()
    success = run_attempt(
        tasks, next_receipt.receipt_id, factory, clock=factory.clock, limits=FAST
    )
    assert isinstance(success, SuccessReceipt)
    assert "Independent lifecycle paper" in factory.sessions[0].commands[-1]["message"]
    assert "SENSITIVE" not in repr(result)
    assert b"SENSITIVE" not in data.database.read_bytes()
    tasks.validate_all()


def test_a8_tests_use_no_sleep_for_synchronization() -> None:
    for path in Path(__file__).parent.glob("*a8_*.py"):
        for node in ast.walk(ast.parse(path.read_bytes())):
            if isinstance(node, ast.Call):
                target = node.func
                assert not (
                    isinstance(target, ast.Attribute) and target.attr == "sleep"
                ), path.name
                assert not (isinstance(target, ast.Name) and target.id == "sleep"), (
                    path.name
                )


@pytest.mark.parametrize(
    ("phase", "reason"),
    [
        ("initialization", RpcReason.TIMEOUT),
        ("run", RpcReason.TIMEOUT),
        ("close", RpcReason.CLOSE_TIMEOUT),
    ],
)
def test_data_at_exact_deadline_cannot_complete(
    description: CallDescription, phase: str, reason: RpcReason
) -> None:
    class DeadlineSession(ScriptedSession):
        def pump(self, pending: bytes, timeout: float) -> SessionEvent:
            event = super().pump(pending, timeout)
            if phase == "initialization" and len(self.commands) == 1 and event.stdout:
                self.clock.now = 0.2
            if phase == "run" and len(self.commands) == 9 and event.stdout:
                self.clock.now = 0.5
            if phase == "close" and self.closed:
                self.clock.now = 0.5
            return event

    session = DeadlineSession(description)
    assert run_call(
        description, b"request", lambda _: session, clock=session.clock, limits=FAST
    ) == RpcFailure(reason)
    assert session.terminated


def test_cancellation_at_same_instant_as_deadline_is_locked_first(
    description: CallDescription,
) -> None:
    class LateComplete(CancelSession):
        observed = False

        def pump(self, pending: bytes, timeout: float) -> SessionEvent:
            event = super().pump(pending, timeout)
            if len(self.commands) == 9 and event.stdout:
                self.clock.now = 0.5
                self.observed = True
            return event

    session = LateComplete(description)
    result = run_call(
        description,
        b"request",
        lambda _: session,
        clock=session.clock,
        cancelled=lambda: session.observed,
        limits=FAST,
    )
    assert result == RpcFailure(RpcReason.CANCELLED)
    assert session.terminated


@pytest.mark.parametrize("command_count", [1, 4, 8])
def test_initialization_cancellation_still_clears_before_abort(
    description: CallDescription, command_count: int
) -> None:
    session = CancelSession(description)
    result = run_call(
        description,
        b"request",
        lambda _: session,
        clock=session.clock,
        cancelled=lambda: len(session.commands) >= command_count,
        limits=FAST,
    )
    assert result == RpcFailure(RpcReason.CANCELLED)
    assert [c["type"] for c in session.commands[-2:]] == ["clear_queue", "abort"]
    assert not any(c["type"] == "prompt" for c in session.commands)


def test_cancel_during_partial_frame_terminates_without_appending_commands(
    description: CallDescription,
) -> None:
    class PartialCancelled(CancelSession):
        observed = False

        def pump(self, pending: bytes, timeout: float) -> SessionEvent:
            event = ScriptedSession.pump(self, pending[:5], timeout)
            if pending:
                self.observed = True
            return event

    session = PartialCancelled(description)
    result = run_call(
        description,
        b"request",
        lambda _: session,
        clock=session.clock,
        cancelled=lambda: session.observed,
        limits=FAST,
    )
    assert result == RpcFailure(RpcReason.CANCELLED)
    assert session.commands == [] and session.terminated


def test_cancellation_before_start_never_opens_session(
    description: CallDescription,
) -> None:
    factory = FakeFactory()
    assert run_call(
        description,
        b"request",
        factory,
        clock=factory.clock,
        cancelled=lambda: True,
        limits=FAST,
    ) == RpcFailure(RpcReason.CANCELLED)
    assert factory.sessions == []


@pytest.mark.parametrize("interruption", [KeyboardInterrupt(), SystemExit(42)])
@pytest.mark.parametrize("phase", ["success", "failure", "interrupted"])
@pytest.mark.parametrize("elapsed", [0.05, 0.2])
def test_cleanup_interruption_reclaims_session_with_original_deadline(
    description: CallDescription,
    interruption: BaseException,
    phase: str,
    elapsed: float,
) -> None:
    original = (
        KeyboardInterrupt("communication") if phase == "interrupted" else interruption
    )

    class InterruptedCleanup(ScriptedSession):
        termination_calls = 0

        def pump(self, pending: bytes, timeout: float) -> SessionEvent:
            if phase == "failure":
                raise OSError("transport failed")
            if phase == "interrupted":
                raise original
            return super().pump(pending, timeout)

        def terminate(self, timeout: float) -> None:
            self.termination_calls += 1
            if self.termination_calls == 1:
                self.clock.now += elapsed
                raise interruption
            assert timeout == pytest.approx(0.2 - elapsed)
            super().terminate(timeout)

    session = InterruptedCleanup(description)
    with pytest.raises(type(original)) as caught:
        run_call(
            description, b"request", lambda _: session, clock=session.clock, limits=FAST
        )
    assert caught.value is original
    assert session.closed and session.terminated
    assert session.clock.now <= 0.2


@pytest.mark.parametrize("interruption", [KeyboardInterrupt(), SystemExit(42)])
@pytest.mark.parametrize("sample", [1, 2, 3, 4])
def test_post_eof_clock_interruption_cannot_skip_cleanup(
    description: CallDescription, interruption: BaseException, sample: int
) -> None:
    class EofSession(ScriptedSession):
        eof_returned = False

        def pump(self, pending: bytes, timeout: float) -> SessionEvent:
            event = super().pump(pending, timeout)
            self.eof_returned = event.stdout_eof and event.stderr_eof
            return event

    session = EofSession(description)
    samples = 0

    def clock() -> float:
        nonlocal samples
        if session.eof_returned:
            samples += 1
            if samples == sample:
                raise interruption
        return session.clock()

    with pytest.raises(type(interruption)) as caught:
        run_call(description, b"request", lambda _: session, clock=clock, limits=FAST)
    assert caught.value is interruption
    assert session.closed and session.terminated
