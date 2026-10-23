"""A7-03 领取、租约与失败预算的公共服务行为。"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from paper_radar.screening_tasks import ScreeningTasks, TaskError, TaskReason
from paper_radar.screening_tasks.attempt_models import FailureKind, FailureReport
from paper_radar.stage_inputs import StageInput
from tests.a7_registration_support import archive, request_for


def test_claim_persists_one_attempt_and_refuses_another_holder(tmp_path: Path) -> None:
    data = archive(tmp_path)
    service = ScreeningTasks(
        data.database, data.data_root, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    receipt = service.register(request_for(data))
    claim = service.claim(receipt.receipt_id)
    assert claim.attempt_no == 1
    assert claim.expires_at == datetime(2026, 1, 1, 0, 10, tzinfo=UTC)
    status = service.status(receipt.receipt_id)
    assert (status.state, status.used_attempts, status.remaining_attempts) == (
        "running",
        1,
        1,
    )
    assert claim.credential not in repr(claim)
    with pytest.raises(TaskError) as busy:
        service.claim(receipt.receipt_id)
    assert busy.value.reason == TaskReason.TASK_RUNNING
    service.validate_all()


def test_one_attempt_driver_uses_committed_frozen_input_and_safe_correction(
    tmp_path: Path,
) -> None:
    data = archive(tmp_path)
    service = ScreeningTasks(
        data.database, data.data_root, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    receipt = service.register(request_for(data))
    seen: list[str | None] = []

    def executor(
        stage_input: StageInput, correction: str | None, handle: str
    ) -> FailureReport:
        assert stage_input == service.load_input(receipt.receipt_id).stage_input
        assert service.status(receipt.receipt_id).state == "running"
        assert service.renew(handle) == datetime(2026, 1, 1, 0, 10, tzinfo=UTC)
        seen.append(correction)
        return FailureReport(FailureKind.PROTOCOL_ERROR)

    assert (
        service.run_once(receipt.receipt_id, executor).kind
        == FailureKind.PROTOCOL_ERROR
    )
    assert (
        service.run_once(receipt.receipt_id, executor).kind
        == FailureKind.PROTOCOL_ERROR
    )
    assert seen == [None, "上次执行未遵守输出协议,请遵守冻结的输出契约。"]


def test_executor_exception_is_safe_and_other_stage_is_independent(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data = archive(tmp_path)
    service = ScreeningTasks(
        data.database, data.data_root, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    boundary = service.register(request_for(data))
    value = service.register(
        request_for(data, stage="value", original_title_is_zh=False)
    )

    def executor(
        stage_input: StageInput, correction: str | None, handle: str
    ) -> FailureReport:
        raise RuntimeError("PRIVATE_MODEL_OUTPUT_AND_TOKEN")

    failure = service.run_once(boundary.receipt_id, executor)
    assert (failure.kind, failure.origin) == (FailureKind.EXECUTOR_ERROR, "exception")
    assert "PRIVATE_MODEL_OUTPUT_AND_TOKEN" not in repr(failure) + str(
        capsys.readouterr()
    )
    other = service.claim(value.receipt_id)
    assert other.attempt_no == 1
    service.fail(other, FailureReport(FailureKind.TIMEOUT))
    service.validate_all()


def test_failed_attempt_replays_exactly_and_budget_survives_reopen(
    tmp_path: Path,
) -> None:
    data = archive(tmp_path)

    def clock() -> datetime:
        return datetime(2026, 1, 1, tzinfo=UTC)

    service = ScreeningTasks(data.database, clock=clock)
    receipt = service.register(request_for(data))
    first = service.claim(receipt.receipt_id)
    report = FailureReport(FailureKind.TIMEOUT)
    failed = service.fail(first, report)
    assert service.fail(first, report) == failed
    with pytest.raises(TaskError) as conflict:
        service.fail(first, FailureReport(FailureKind.CANCELLED))
    assert conflict.value.reason == TaskReason.SETTLEMENT_CONFLICT
    assert service.status(receipt.receipt_id).state == "retryable"
    reopened = ScreeningTasks(data.database, clock=clock)
    second = reopened.claim(receipt.receipt_id)
    assert second.attempt_no == 2
    reopened.fail(second, report)
    status = reopened.status(receipt.receipt_id)
    assert (status.state, status.used_attempts, status.remaining_attempts) == (
        "failed",
        2,
        0,
    )
    with pytest.raises(TaskError) as exhausted:
        reopened.claim(receipt.receipt_id)
    assert exhausted.value.reason == TaskReason.BUDGET_EXHAUSTED
    reopened.validate_all()


def test_exact_expiry_is_read_only_and_unsettled_holder_can_renew_or_fail(
    tmp_path: Path,
) -> None:
    data = archive(tmp_path)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    service = ScreeningTasks(data.database, clock=lambda: now)
    receipt = service.register(request_for(data))
    first = service.claim(receipt.receipt_id)
    now = first.expires_at
    assert service.status(receipt.receipt_id).state == "lease_expired"
    assert service.renew(first.renewal_handle) == datetime(
        2026, 1, 1, 0, 20, tzinfo=UTC
    )
    now += timedelta(seconds=600)
    service.fail(first, FailureReport(FailureKind.CANCELLED))
    second = service.claim(receipt.receipt_id)
    now = second.expires_at
    expired = service.status(receipt.receipt_id)
    assert (expired.state, expired.remaining_attempts) == ("lease_expired", 0)
    recovered = service.reclaim(receipt.receipt_id)
    assert recovered.state == "failed"
    assert recovered.last_failure == FailureKind.OUTCOME_UNKNOWN
    for operation in (
        lambda: service.renew(second.renewal_handle),
        lambda: service.fail(second, FailureReport(FailureKind.TIMEOUT)),
    ):
        with pytest.raises(TaskError) as rejected:
            operation()
        assert rejected.value.reason == TaskReason.INVALID_CREDENTIAL
    service.validate_all()


def test_claim_can_recover_expired_attempt_but_never_refills_budget(
    tmp_path: Path,
) -> None:
    data = archive(tmp_path)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    service = ScreeningTasks(data.database, clock=lambda: now)
    receipt = service.register(request_for(data))
    first = service.claim(receipt.receipt_id)
    now = first.expires_at
    second = service.claim(receipt.receipt_id)
    assert second.attempt_no == 2
    assert (
        service.status(receipt.receipt_id).last_failure == FailureKind.OUTCOME_UNKNOWN
    )
    with pytest.raises(TaskError) as late:
        service.fail(first, FailureReport(FailureKind.TIMEOUT))
    assert late.value.reason == TaskReason.INVALID_CREDENTIAL
    now = second.expires_at
    with pytest.raises(TaskError) as exhausted:
        service.claim(receipt.receipt_id)
    assert exhausted.value.reason == TaskReason.BUDGET_EXHAUSTED
    status = service.status(receipt.receipt_id)
    assert (status.state, status.used_attempts, status.remaining_attempts) == (
        "failed",
        2,
        0,
    )
    service.validate_all()


@pytest.mark.parametrize(
    "kind",
    [
        FailureKind.OUTPUT_INVALID,
        FailureKind.MODEL_MISMATCH,
        FailureKind.OUTCOME_UNKNOWN,
    ],
)
def test_executor_cannot_forge_authoritative_output_or_recovery_failure(
    tmp_path: Path, kind: FailureKind
) -> None:
    data = archive(tmp_path)
    service = ScreeningTasks(
        data.database, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    receipt = service.register(request_for(data))
    claim = service.claim(receipt.receipt_id)
    with pytest.raises(TaskError) as invalid:
        service.fail(claim, FailureReport(kind))
    assert invalid.value.reason == TaskReason.INVALID_FAILURE
    assert service.status(receipt.receipt_id).state == "running"
    with pytest.raises(TaskError) as forged:
        service.fail(
            replace(claim, credential=claim.renewal_handle),
            FailureReport(FailureKind.TIMEOUT),
        )
    assert forged.value.reason == TaskReason.INVALID_CREDENTIAL
    service.fail(claim, FailureReport(FailureKind.TIMEOUT))


def test_clock_is_optional_for_registration_but_required_for_time_operations(
    tmp_path: Path,
) -> None:
    data = archive(tmp_path)
    service = ScreeningTasks(data.database)
    receipt = service.register(request_for(data))
    assert service.load_input(receipt.receipt_id).fingerprint == receipt.fingerprint
    service.validate_all()
    for operation in (
        lambda: service.claim(receipt.receipt_id),
        lambda: service.status(receipt.receipt_id),
        lambda: service.reclaim(receipt.receipt_id),
    ):
        with pytest.raises(TaskError) as missing:
            operation()
        assert missing.value.reason == TaskReason.INVALID_CLOCK
    valid = ScreeningTasks(
        data.database, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    assert valid.status(receipt.receipt_id).used_attempts == 0


def test_late_executor_exception_does_not_escape_in_controlled_error_context(
    tmp_path: Path,
) -> None:
    data = archive(tmp_path)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    service = ScreeningTasks(data.database, data.data_root, clock=lambda: now)
    receipt = service.register(request_for(data))

    def executor(
        stage_input: StageInput, correction: str | None, handle: str
    ) -> FailureReport:
        nonlocal now
        now += timedelta(seconds=600)
        service.reclaim(receipt.receipt_id)
        raise RuntimeError("PRIVATE_EXECUTOR_EXCEPTION")

    with pytest.raises(TaskError) as late:
        service.run_once(receipt.receipt_id, executor)
    assert late.value.reason == TaskReason.INVALID_CREDENTIAL
    assert late.value.__context__ is None


def test_untrusted_success_return_is_one_protocol_failure(tmp_path: Path) -> None:
    data = archive(tmp_path)
    service = ScreeningTasks(
        data.database, data.data_root, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    receipt = service.register(request_for(data))
    calls: list[int] = []

    def executor(stage_input: StageInput, correction: str | None, handle: str) -> Any:
        calls.append(1)
        return {"validated": True, "raw": "PRIVATE_UNVERIFIED_OUTPUT"}

    result = service.run_once(receipt.receipt_id, executor)
    assert (result.kind, result.origin, calls) == (
        FailureKind.PROTOCOL_ERROR,
        "executor",
        [1],
    )
    assert "PRIVATE_UNVERIFIED_OUTPUT" not in repr(result)
    assert service.status(receipt.receipt_id).used_attempts == 1
