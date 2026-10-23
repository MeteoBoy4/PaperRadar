"""task_query_result v1 的显式安全字段;不序列化内部行。"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from paper_radar.papers import PaperReason
from paper_radar.screening_tasks.attempt_models import FailureReceipt
from paper_radar.screening_tasks.models import RequestReceipt, Stage, TaskState

TASK_QUERY_FORMAT_VERSION = 1


@dataclass(frozen=True, slots=True)
class AttemptView:
    attempt_no: int
    receipt_id: str
    version_id: str
    revision_no: int
    selection_id: str | None
    claimed_at: datetime
    expires_at: datetime
    failure: FailureReceipt | None
    success_id: str | None


@dataclass(frozen=True, slots=True)
class TaskView:
    task_id: str
    budget_id: str
    generation: int
    parent_task_id: str | None
    state: TaskState
    used_attempts: int
    remaining_attempts: int
    requests: tuple[RequestReceipt, ...]
    attempts: tuple[AttemptView, ...]


@dataclass(frozen=True, slots=True)
class BudgetView:
    budget_id: str
    fingerprint: str
    applicability: Literal["current", "historical", "undeterminable"]
    reason: PaperReason | None
    latest_generation: int
    latest_task_id: str
    tasks: tuple[TaskView, ...]


@dataclass(frozen=True, slots=True)
class TaskQueryResult:
    paper_id: str
    stage: Stage
    snapshot_id: str
    current_fingerprint: str | None
    reason: PaperReason | None
    budgets: tuple[BudgetView, ...]
    current_failures: tuple[TaskView, ...]
    kind: Literal["task_query_result"] = field(default="task_query_result", init=False)
    format_version: Literal[1] = field(default=1, init=False)
