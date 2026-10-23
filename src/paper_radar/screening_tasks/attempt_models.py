"""执行能力与安全只读投影;领取凭据不属于普通输出。"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Literal, Protocol, TypedDict

from paper_radar.screening import OutputValidationIssue
from paper_radar.screening_tasks.models import TaskState
from paper_radar.screening_tasks.success_models import SuccessCandidate
from paper_radar.stage_inputs import StageInput

Clock = Callable[[], datetime]
LEASE_SECONDS = 600


class FailureKind(StrEnum):
    OUTPUT_INVALID = "output_invalid"
    MODEL_MISMATCH = "model_mismatch"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    PROTOCOL_ERROR = "protocol_error"
    EXECUTOR_ERROR = "executor_error"
    OUTCOME_UNKNOWN = "outcome_unknown"


FailureOrigin = Literal["executor", "exception", "recovery"]


class AttemptRow(TypedDict):
    """同连接读取的尝试/租约/结算事实;不携带明文领取能力。"""

    task_id: str
    attempt_no: int
    receipt_id: str
    version_id: str
    revision_no: int
    selection_id: str | None
    claimed_at: str
    credential_sha256: str
    renewal_sha256: str
    expires_at: str
    kind: str | None
    origin: FailureOrigin | None
    settled_at: str | None
    issues_json: str | None
    success_id: str | None


@dataclass(frozen=True, slots=True)
class FailureReport:
    kind: FailureKind


@dataclass(frozen=True, slots=True)
class FailureReceipt:
    task_id: str
    attempt_no: int
    kind: FailureKind
    origin: FailureOrigin
    settled_at: datetime
    issues: tuple[OutputValidationIssue, ...] = ()


class FailureExecutor(Protocol):
    def __call__(
        self, stage_input: StageInput, correction: str | None, renewal_handle: str, /
    ) -> FailureReport: ...


class TestExecutor(Protocol):
    def __call__(
        self, stage_input: StageInput, correction: str | None, renewal_handle: str, /
    ) -> FailureReport | SuccessCandidate: ...


@dataclass(frozen=True, slots=True)
class Claim:
    task_id: str
    attempt_no: int
    receipt_id: str
    claimed_at: datetime
    expires_at: datetime
    version_id: str
    revision_no: int
    selection_id: str | None
    credential: str = field(repr=False)
    renewal_handle: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class TaskStatus:
    task_id: str
    state: TaskState
    used_attempts: int
    remaining_attempts: int
    last_failure: FailureKind | None = None
