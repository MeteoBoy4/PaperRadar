"""请求与安全回执;输入和语言事实只由显式内部消费入口取得。"""

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from paper_radar.config import RuntimeConfigSnapshot
from paper_radar.stage_inputs import StageInput

TASKS_FORMAT_VERSION = 1
Stage = Literal["boundary", "value"]
Source = Literal["scheduled", "manual"]
# 后续领取/查询沿用同一状态词表,不将 lease_expired 误作失败终态。
TaskState = Literal[
    "ready", "running", "lease_expired", "retryable", "failed", "succeeded"
]


class RegistrationRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, hide_input_in_errors=True
    )
    paper_id: str
    snapshot_id: str
    source: Source
    scheduled_day: str | None = None
    request_id: str | None = Field(default=None, repr=False)
    reason: str | None = Field(default=None, repr=False)
    actor: str | None = Field(default=None, repr=False)


class BoundaryRequest(RegistrationRequest):
    stage: Literal["boundary"] = "boundary"


class ValueRequest(RegistrationRequest):
    stage: Literal["value"] = "value"
    # 唯一上下文权威是 StageInput.value_prediction_context,不在请求层另造 bool 规则。
    original_title_is_zh: object = Field(default=None, repr=False)


@dataclass(frozen=True, slots=True)
class RequestReceipt:
    receipt_id: str
    task_id: str
    budget_id: str
    paper_id: str
    stage: Stage
    fingerprint: str
    generation: int
    source: Source
    version_id: str
    revision_no: int
    snapshot_id: str
    scheduled_day: str | None
    selection_id: str | None
    cached_success_id: str | None = None
    format_version: Literal[1] = field(default=1, init=False)


@dataclass(frozen=True, slots=True)
class FrozenInput:
    fingerprint: str
    stage_input: StageInput = field(repr=False)
    snapshot: RuntimeConfigSnapshot = field(repr=False)
    original_title_is_zh: bool | None = field(repr=False)
