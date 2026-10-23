"""UTC 时间、能力摘要与状态的确定性规则。"""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from hashlib import sha256

from paper_radar.screening_tasks.attempt_models import (
    LEASE_SECONDS,
    AttemptRow,
    Clock,
    FailureKind,
    TaskStatus,
)
from paper_radar.screening_tasks.errors import TaskError, TaskReason
from paper_radar.screening_tasks.models import TaskState


def utc_now(clock: Clock | None) -> datetime:
    if clock is None:
        raise TaskError(TaskReason.INVALID_CLOCK)
    try:
        value = clock()
    except Exception:
        raise TaskError(TaskReason.INVALID_CLOCK) from None
    if type(value) is not datetime or value.tzinfo is not UTC:
        raise TaskError(TaskReason.INVALID_CLOCK)
    return value


def timestamp(value: datetime) -> str:
    return value.isoformat(timespec="microseconds")


def lease_expiry(now: datetime) -> datetime:
    try:
        return now + timedelta(seconds=LEASE_SECONDS)
    except OverflowError:
        raise TaskError(TaskReason.INVALID_CLOCK) from None


def read_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is not UTC or timestamp(parsed) != value:
        raise ValueError("invalid UTC timestamp")
    return parsed


def digest(value: str) -> str:
    return sha256(value.encode("ascii")).hexdigest()


def correction_for(kind: FailureKind | None) -> str | None:
    if kind is None:
        return None
    return {
        FailureKind.OUTPUT_INVALID: "上次输出未通过验证,请遵守冻结的输出契约。",
        FailureKind.MODEL_MISMATCH: "上次模型身份不匹配,请使用冻结的模型配置。",
        FailureKind.TIMEOUT: "上次执行超时,请在受支持的执行时限内完成。",
        FailureKind.CANCELLED: "上次执行已取消,请重新完成本次冻结输入。",
        FailureKind.PROTOCOL_ERROR: "上次执行未遵守输出协议,请遵守冻结的输出契约。",
        FailureKind.EXECUTOR_ERROR: "上次执行者异常,请重新完成本次冻结输入。",
        FailureKind.OUTCOME_UNKNOWN: "上次执行结果未知,请重新完成本次冻结输入。",
    }[kind]


def derive_status(
    task_id: str, rows: Sequence[AttemptRow], now: datetime
) -> TaskStatus:
    if not rows:
        return TaskStatus(task_id, "ready", 0, 2)
    if rows[-1]["success_id"] is not None:
        return TaskStatus(task_id, "succeeded", len(rows), 2 - len(rows))
    last_failure = FailureKind(rows[-1]["kind"]) if rows[-1]["kind"] else None
    if last_failure is not None:
        return TaskStatus(
            task_id,
            "failed" if len(rows) == 2 else "retryable",
            len(rows),
            2 - len(rows),
            last_failure,
        )
    state: TaskState = (
        "lease_expired" if now >= read_timestamp(rows[-1]["expires_at"]) else "running"
    )
    previous_kind = rows[-2]["kind"] if len(rows) > 1 else None
    previous = FailureKind(previous_kind) if previous_kind is not None else None
    return TaskStatus(task_id, state, len(rows), 2 - len(rows), previous)
