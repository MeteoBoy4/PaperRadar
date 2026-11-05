"""Body 安全查询与受控 parser 边界;业务文本不进入 repr。"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from paper_radar.config.extraction import ExtractionSemantics
from paper_radar.eligibility import (
    DecisionFact,
    ExecutionSource,
    QualityFact,
    RootPurpose,
)
from paper_radar.fulltext.canonical import CanonicalDocument
from paper_radar.fulltext.execution_audit import ExtractionExecutionAudit
from paper_radar.reading.context import ExtractionIdentity


class BodyReason(StrEnum):
    ROOT_CONFLICT = "root_conflict"
    INVALID_REQUEST = "invalid_request"
    REQUEST_CONFLICT = "request_conflict"
    INVALID_PDF = "invalid_pdf"
    VERSION_MISMATCH = "version_mismatch"
    PDF_ABSENT = "pdf_absent"
    FACTS_CHANGED = "facts_changed"
    SOURCE_REQUIRES_DEDICATED_PATH = "source_requires_dedicated_path"
    VISIBILITY_DENIED = "visibility_denied"
    SCREENING_MISMATCH = "screening_mismatch"
    SAMPLE_MISMATCH = "sample_mismatch"
    ROOT_UNKNOWN = "root_unknown"
    DECISION_NOT_ACCEPTED = "decision_not_accepted"
    EXECUTION_SOURCE_UNKNOWN = "execution_source_unknown"
    TEST_EXECUTION_SOURCE = "test_execution_source"
    EXTRACTION_ABSENT = "extraction_absent"
    EXTRACTION_FAILED = "extraction_failed"
    QUALITY_ABSENT = "quality_absent"
    QUALITY_FAILED = "quality_failed"
    ORDINARY_CONSUMPTION_DENIED = "ordinary_consumption_denied"
    BUDGET_EXHAUSTED = "budget_exhausted"
    PERMANENT_FAILURE = "permanent_failure"
    LAYOUT_CONFLICT = "layout_conflict"
    UNSAFE_LOCK = "unsafe_lock"
    CORRUPT_REFERENCE = "corrupt_reference"
    DATABASE_FAILED = "database_failed"


class BodyError(ValueError):
    def __init__(self, reason: BodyReason | str) -> None:
        self.reason = BodyReason(reason)
        guidance = {
            BodyReason.SOURCE_REQUIRES_DEDICATED_PATH: (
                "请使用该来源所属的专用流程;"
                "Body 只接受直接人工决定,不建立 read_requests。"
            ),
            BodyReason.INVALID_PDF: "请附加至少 1024 字节且具有 %PDF- 签名的合法 PDF。",
            BodyReason.ROOT_CONFLICT: "根用途已冻结,请使用独立数据库登记另一用途。",
            BodyReason.VISIBILITY_DENIED: "隐藏条件尚未解除,请先完成专用校准流程。",
        }.get(self.reason, "请核查已登记的前置事实与请求;不得绕过预算或质量门槛。")
        super().__init__(f"正文服务拒绝:{self.reason.value};{guidance}")


@dataclass(frozen=True)
class RootRegistration:
    root_id: str | None = None
    purpose: RootPurpose = RootPurpose.UNKNOWN
    registered_at: str | None = None


@dataclass(frozen=True)
class PdfAttachment:
    attachment_id: str
    paper_id: str
    version_id: str
    sequence: int
    artifact_id: str
    pdf_sha256: str
    attached_at: str
    access_basis: str = "manual"


@dataclass(frozen=True)
class DecisionEvent:
    fact: DecisionFact
    version_id: str
    revision_no: int
    screening_references: tuple[str, ...]
    actor: str = field(repr=False)
    decided_at: str = ""


@dataclass(frozen=True)
class SampleAdmission:
    sample_id: str
    paper_id: str
    version_id: str
    sequence: int
    feed_id: str
    pdf_sha256: str
    frozen_at: str
    reason: str = field(repr=False)


@dataclass(frozen=True)
class ParserResult:
    document: CanonicalDocument = field(repr=False)
    document_json: bytes | None = field(default=None, repr=False)
    peak_memory_bytes: int = 0
    warnings: tuple[str, ...] = ()


class ExtractionFailure(StrEnum):
    TIMEOUT = "timeout"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    EXECUTOR_ERROR = "executor_error"
    OUTCOME_UNKNOWN = "outcome_unknown"
    NO_TEXT_LAYER = "extraction_failed_no_text_layer"
    QUALITY_GATE = "extraction_failed_quality_gate"


class ParserFailure(Exception):
    def __init__(
        self, failure: ExtractionFailure | str, *, peak_memory_bytes: int = 0
    ) -> None:
        self.failure = ExtractionFailure(failure)
        self.peak_memory_bytes = peak_memory_bytes
        super().__init__(self.failure.value)


class PreparedParser(Protocol):
    audit: ExtractionExecutionAudit

    def convert(self, pdf: bytes, semantics: ExtractionSemantics) -> ParserResult: ...

    def close(self) -> None: ...


class CanonicalParser(Protocol):
    def preflight(self, semantics: ExtractionSemantics) -> PreparedParser | None:
        """外部 probe 与模型核验;在锁/领取前运行,失败不占预算。"""
        ...

    def convert(self, pdf: bytes, semantics: ExtractionSemantics) -> ParserResult: ...


@dataclass(frozen=True)
class ExtractionAttempt:
    attempt_id: str
    ordinal: int
    claimed_at: str
    failure: ExtractionFailure | None
    settled_at: str | None
    artifact_id: str | None
    elapsed_seconds: float | None
    peak_memory_bytes: int | None
    executor_audit: ExtractionExecutionAudit | None = None


@dataclass(frozen=True)
class ExtractionView:
    fingerprint: str
    backend: str
    pdf_sha256: str
    attempts: tuple[ExtractionAttempt, ...]
    artifact_id: str | None
    identity: ExtractionIdentity | None
    quality: QualityFact
    permanent_failure: bool

    def __post_init__(self) -> None:
        if (self.quality.basis == "failed") != (self.quality.failure is not None):
            raise BodyError("corrupt_reference")

    @property
    def remaining_attempts(self) -> int:
        return 2 - len(self.attempts)


@dataclass(frozen=True)
class BodyFacts:
    paper_id: str
    version_id: str
    revision_no: int
    root: RootRegistration
    decision: DecisionEvent | None
    execution_source: ExecutionSource
    pdf: PdfAttachment | None
    extraction: ExtractionView | None
    sample: SampleAdmission | None
    reasons: tuple[BodyReason, ...]

    @property
    def eligible(self) -> bool:
        return not self.reasons
