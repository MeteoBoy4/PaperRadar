"""Read任务的安全公共值;正文、候选和令牌不进入repr。"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Literal

from paper_radar.llm import CallDescription
from paper_radar.reading.acceptance_v2 import ReadV2Issue
from paper_radar.reading.context import ExtractionIdentity
from paper_radar.reading.schema import ReadAnalysisOutput


class ReadReason(StrEnum):
    INVALID_REQUEST = "invalid_request"
    REQUEST_CONFLICT = "request_conflict"
    TASK_NOT_FOUND = "task_not_found"
    ANALYSIS_NOT_FOUND = "analysis_not_found"
    FACTS_CHANGED = "facts_changed"
    PREREQUISITES_FAILED = "prerequisites_failed"
    READ_INPUT_OVER_BUDGET = "read_input_over_budget"
    TASK_RUNNING = "task_running"
    BUDGET_EXHAUSTED = "budget_exhausted"
    ALREADY_SUCCEEDED = "already_succeeded"
    INVALID_CREDENTIAL = "invalid_credential"
    SETTLEMENT_CONFLICT = "settlement_conflict"
    NOT_LATEST = "not_latest"
    NOT_FAILED = "not_failed"
    VISIBILITY_DENIED = "visibility_denied"
    ORDINARY_CONSUMPTION_DENIED = "ordinary_consumption_denied"
    CORRUPT_REFERENCE = "corrupt_reference"
    UNSUPPORTED_RULE_VERSION = "unsupported_rule_version"
    DATABASE_FAILED = "database_failed"


class ReadTaskError(ValueError):
    def __init__(
        self, reason: ReadReason | str, *, reasons: tuple[str, ...] = ()
    ) -> None:
        self.reason = ReadReason(reason)
        self.reasons = reasons
        super().__init__(
            f"Read服务拒绝:{self.reason.value};请核查持久前置、任务所有权与历史依据。"
        )


class ReadFailure(StrEnum):
    OUTPUT_INVALID = "output_invalid"
    MODEL_MISMATCH = "model_mismatch"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    PROTOCOL_ERROR = "protocol_error"
    EXECUTOR_ERROR = "executor_error"
    OUTCOME_UNKNOWN = "outcome_unknown"


@dataclass(frozen=True)
class ReadAttempt:
    attempt_id: str
    ordinal: int
    claimed_at: datetime
    lease_until: datetime
    failure: ReadFailure | None
    settled_at: datetime | None
    issues: tuple[ReadV2Issue, ...] = ()
    basis: dict[str, str | None] = field(default_factory=dict, repr=False)
    metadata_basis: dict[str, str | int] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class ReadTask:
    task_id: str
    paper_id: str
    fingerprint: str
    generation: int
    parent_task_id: str | None
    snapshot_id: str
    identity: ExtractionIdentity
    output_language: Literal["zh", "en"]
    attempts: tuple[ReadAttempt, ...]
    analysis_id: str | None
    retry_reason: str | None = field(default=None, repr=False)
    retry_actor: str | None = field(default=None, repr=False)

    @property
    def remaining_attempts(self) -> int:
        return 2 - len(self.attempts)

    @property
    def status(self) -> Literal["ready", "running", "failed", "succeeded"]:
        if self.analysis_id:
            return "succeeded"
        if any(a.settled_at is None for a in self.attempts):
            return "running"
        return "failed" if self.remaining_attempts == 0 else "ready"


@dataclass(frozen=True)
class ReadHandle:
    task_id: str
    attempt_id: str
    ordinal: int
    token: str = field(repr=False)
    lease_until: datetime
    description: CallDescription = field(repr=False)
    correction: str | None = field(default=None, repr=False)


@dataclass(frozen=True)
class ReadAnalysis:
    analysis_id: str
    task_id: str
    paper_id: str
    fingerprint: str
    identity: ExtractionIdentity
    artifact_id: str
    candidate_artifact_id: str
    attempt_ordinal: int
    executor_kind: Literal["test", "pi_rpc"]
    root_purpose: str
    quality_basis: str
    output: ReadAnalysisOutput = field(repr=False)
    raw_candidate: bytes = field(repr=False)
    discards: tuple[dict[str, object], ...] = ()
    diagnostics: tuple[dict[str, object], ...] = ()
    warnings: tuple[dict[str, object], ...] = field(default=(), repr=False)
    evidence_rule_version: str = ""
    numeric_rule_version: str = ""
    limitation_rule_version: str = ""
    audit: dict[str, object] = field(default_factory=dict, repr=False)
