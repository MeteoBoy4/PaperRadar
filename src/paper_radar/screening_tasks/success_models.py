"""候选仅承载原始响应;结果只供显式内部消费。"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from paper_radar.papers import PaperReason
from paper_radar.screening.schema import BoundaryOutput, ValuePredictionOutput
from paper_radar.screening_tasks.models import Stage

Applicability = Literal["current", "historical", "undeterminable"]


@dataclass(frozen=True, slots=True)
class SuccessCandidate:
    raw_response: bytes = field(repr=False)
    executor_kind: Literal["test"] = field(default="test", repr=False)
    reported_provider: str | None = field(default=None, repr=False)
    reported_model: str | None = field(default=None, repr=False)
    provider_request_id: str | None = field(default=None, repr=False)
    input_tokens: int | None = field(default=None, repr=False)
    output_tokens: int | None = field(default=None, repr=False)


@dataclass(frozen=True, slots=True)
class SuccessReceipt:
    success_id: str
    task_id: str
    attempt_no: int
    artifact_id: str
    fingerprint: str
    stage: Stage
    executor_kind: Literal["test"]
    settled_at: datetime


@dataclass(frozen=True, slots=True)
class SuccessContent:
    receipt: SuccessReceipt
    raw_response: bytes = field(repr=False)
    output: BoundaryOutput | ValuePredictionOutput = field(repr=False)
    audit: dict[str, str | int | None] = field(repr=False)


@dataclass(frozen=True, slots=True)
class SuccessView:
    receipt: SuccessReceipt
    applicability: Applicability
    paper_reason: PaperReason | None = None
