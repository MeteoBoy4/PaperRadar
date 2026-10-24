"""prepare→run_once 的四类故障边界、预算及安全修正。"""

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from paper_radar.llm.rpc_types import RpcCategory, RpcFailure, RpcLimits, RpcReason
from paper_radar.screening_tasks import (
    FailureKind,
    FailureReceipt,
    FailureReport,
    ScreeningTasks,
    SuccessCandidate,
    SuccessReceipt,
    TaskError,
    TaskReason,
)
from tests.a8_call_support import archive, prepare_call, request_for
from tests.a8_recovery_support import fault_factory
from tests.a8_rpc_support import BOUNDARY_RAW, FakeFactory
from tests.a8_rpc_task_support import FAILURE_KINDS, run_attempt

NOW = datetime(2026, 1, 1, tzinfo=UTC)
LIMITS = RpcLimits(initialization=0.1, total=0.2, close=0.05, terminate=0.05)


@pytest.mark.parametrize(
    "scenario,kind",
    [
        ("timeout", FailureKind.TIMEOUT),
        ("cancelled", FailureKind.CANCELLED),
        ("environment", FailureKind.EXECUTOR_ERROR),
        ("transport", FailureKind.EXECUTOR_ERROR),
        ("protocol", FailureKind.PROTOCOL_ERROR),
    ],
)
def test_rpc_failures_exhaust_one_generation_without_opening_a_third_session(
    tmp_path: Path, scenario: str, kind: FailureKind
) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    receipt = tasks.register(request_for(data))
    factories = []
    for number in (1, 2):
        factory = fault_factory(scenario)
        factories.append(factory)

        def cancelled(factory: FakeFactory = factory) -> bool:
            return scenario == "cancelled" and bool(factory.sessions)

        result = run_attempt(
            tasks,
            receipt.receipt_id,
            factory,
            clock=factory.clock,
            cancelled=cancelled,
            limits=LIMITS,
        )
        assert type(result) is FailureReceipt
        assert (result.kind, result.origin, result.attempt_no) == (
            kind,
            "executor",
            number,
        )
        assert tasks.status(receipt.receipt_id).remaining_attempts == 2 - number
        assert len(factory.sessions) == 1
    rebuilt = ScreeningTasks(
        data.database, data.data_root, clock=lambda: NOW + timedelta(days=3)
    )
    later = rebuilt.register(request_for(data, scheduled_day="2026-01-04"))
    assert later.budget_id == receipt.budget_id and later.task_id == receipt.task_id
    unused = FakeFactory()
    with pytest.raises(TaskError) as error:
        run_attempt(rebuilt, later.receipt_id, unused, clock=unused.clock)
    assert error.value.reason is TaskReason.BUDGET_EXHAUSTED
    assert unused.sessions == []
    assert factories[0].sessions[0] is not factories[1].sessions[0]
    attempts = (
        rebuilt.query(
            paper_id=data.paper_id, stage="boundary", snapshot_id=data.snapshot_id
        )
        .budgets[0]
        .tasks[0]
        .attempts
    )
    assert [attempt.failure.kind for attempt in attempts if attempt.failure] == [
        kind,
        kind,
    ]
    rebuilt.validate_all()


@pytest.mark.parametrize(
    "scenario,expected",
    [
        (
            "output_invalid",
            "上次输出未通过验证,请遵守冻结的输出契约。 $.<额外字段> [extra_field]",
        ),
        ("timeout", "上次执行超时,请在受支持的执行时限内完成。"),
        ("interrupt", "上次执行结果未知,请重新完成本次冻结输入。"),
    ],
)
def test_second_rpc_attempt_gets_only_frozen_input_and_actual_a7_safe_correction(
    tmp_path: Path, scenario: str, expected: str
) -> None:
    data = archive(tmp_path)
    now = NOW
    tasks = ScreeningTasks(data.database, data.data_root, clock=lambda: now)
    receipt = tasks.register(request_for(data))
    first = fault_factory(scenario)
    frozen = prepare_call(tasks, receipt.receipt_id)
    if scenario == "interrupt":
        with pytest.raises(KeyboardInterrupt):
            run_attempt(tasks, receipt.receipt_id, first, clock=first.clock)
        assert tasks.status(receipt.receipt_id).state == "running"
        pending = (
            tasks.query(
                paper_id=data.paper_id, stage="boundary", snapshot_id=data.snapshot_id
            )
            .budgets[0]
            .tasks[0]
            .attempts[0]
        )
        assert pending.failure is None and pending.success_id is None
        now += timedelta(seconds=600)
        # prepare 本身不回收;第二次 run_once 的 claim 才完成 outcome_unknown。
        assert prepare_call(tasks, receipt.receipt_id) == frozen
        assert tasks.status(receipt.receipt_id).state == "lease_expired"
    else:
        failure = run_attempt(
            tasks, receipt.receipt_id, first, clock=first.clock, limits=LIMITS
        )
        assert type(failure) is FailureReceipt
        assert failure.kind is (
            FailureKind.TIMEOUT if scenario == "timeout" else FailureKind.OUTPUT_INVALID
        )
        assert failure.origin == "executor"
    second = FakeFactory()
    success = run_attempt(tasks, receipt.receipt_id, second, clock=second.clock)
    assert type(success) is SuccessReceipt and success.attempt_no == 2
    assert second.sessions[0].description == frozen
    payloads = [
        json.loads(factory.sessions[0].commands[-1]["message"].split("\n", 1)[1])
        for factory in (first, second)
    ]
    assert payloads[0].pop("correction") is None
    assert payloads[1].pop("correction") == expected
    assert payloads[0] == payloads[1]
    assert "完整失败原文_SECRET" not in second.sessions[0].commands[-1]["message"]
    assert set(second.sessions[0].commands[-1]) == {"id", "type", "message"}
    assert tasks.status(receipt.receipt_id).used_attempts == 2
    tasks.validate_all()


@pytest.mark.parametrize("state", ["succeeded", "running"])
def test_unclaimable_rpc_tasks_never_construct_a_session(
    tmp_path: Path, state: str
) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    receipt = tasks.register(request_for(data))
    if state == "succeeded":
        first = FakeFactory()
        assert (
            type(run_attempt(tasks, receipt.receipt_id, first, clock=first.clock))
            is SuccessReceipt
        )
    else:
        tasks.claim(receipt.receipt_id)
    factory = FakeFactory()
    with pytest.raises(TaskError) as error:
        run_attempt(tasks, receipt.receipt_id, factory, clock=factory.clock)
    assert error.value.reason is (
        TaskReason.ALREADY_SUCCEEDED
        if state == "succeeded"
        else TaskReason.TASK_RUNNING
    )
    assert (
        factory.sessions == [] and tasks.status(receipt.receipt_id).used_attempts == 1
    )


def test_prepare_rejection_has_no_attempt_failure_or_external_session(
    tmp_path: Path,
) -> None:
    data = archive(tmp_path, pi_version="1.3.0")
    tasks = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    receipt = tasks.register(request_for(data))
    before = tasks.query(
        paper_id=data.paper_id, stage="boundary", snapshot_id=data.snapshot_id
    )
    factory = FakeFactory()
    with pytest.raises(TaskError) as error:
        run_attempt(tasks, receipt.receipt_id, factory, clock=factory.clock)
    assert error.value.reason is TaskReason.INVALID_CONTEXT
    assert (
        tasks.query(
            paper_id=data.paper_id, stage="boundary", snapshot_id=data.snapshot_id
        )
        == before
    )
    assert before.budgets[0].tasks[0].attempts == ()
    assert (
        tasks.status(receipt.receipt_id).used_attempts == 0 and factory.sessions == []
    )


@pytest.mark.parametrize(
    "variant", ["exception", "wrapper", "subclass", "failure_subclass"]
)
def test_faulty_adapter_does_not_masquerade_as_a_controlled_rpc_failure(
    tmp_path: Path, variant: str
) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    receipt = tasks.register(request_for(data))
    prepare_call(tasks, receipt.receipt_id)

    @dataclass(frozen=True)
    class Wrapper:
        candidate: SuccessCandidate

    class Derived(SuccessCandidate):
        pass

    class DerivedFailure(FailureReport):
        pass

    def adapter(*_: object) -> object:
        if variant == "exception":
            raise RuntimeError("FREE_ERROR_SECRET")
        if variant == "wrapper":
            return Wrapper(SuccessCandidate(BOUNDARY_RAW.encode()))
        if variant == "failure_subclass":
            return DerivedFailure(FailureKind.TIMEOUT)
        return Derived(BOUNDARY_RAW.encode())

    # 负例故意跨越类型契约,检验 A7 的运行期精确类型护栏。
    result = tasks.run_once(receipt.receipt_id, adapter)  # type: ignore[call-overload]
    assert type(result) is FailureReceipt
    assert (result.kind, result.origin) == (
        (FailureKind.EXECUTOR_ERROR, "exception")
        if variant == "exception"
        else (FailureKind.PROTOCOL_ERROR, "executor")
    )
    assert (
        result.issues == () and tasks.status(receipt.receipt_id).remaining_attempts == 1
    )
    assert "FREE_ERROR_SECRET" not in repr(result)
    tasks.validate_all()


def test_closed_rpc_reason_catalog_maps_exhaustively_to_existing_failure_kinds() -> (
    None
):
    expected = {
        FailureKind.TIMEOUT: "timeout close_timeout",
        FailureKind.CANCELLED: "cancelled",
        FailureKind.EXECUTOR_ERROR: (
            "session_cancelled model_rejected startup_error transport_error "
            "eof unexpected_exit"
        ),
        FailureKind.PROTOCOL_ERROR: (
            "invalid_description invalid_utf8 invalid_json non_object duplicate_key "
            "non_finite frame_limit stdout_limit stderr_limit request_limit "
            "candidate_limit partial_frame early_record response_mismatch "
            "command_rejected model_state thinking_unsupported thinking_state "
            "dirty_state commands_present prompt_disposition event_sequence "
            "event_not_allowed message_shape message_mismatch system_mismatch "
            "user_mismatch stop_reason channel usage_shape"
        ),
    }
    assert {name for names in expected.values() for name in names.split()} == {
        reason.value for reason in RpcReason
    }
    assert set(FAILURE_KINDS) == set(RpcCategory)
    for kind, names in expected.items():
        for name in names.split():
            assert FAILURE_KINDS[RpcFailure(RpcReason(name)).category] is kind
