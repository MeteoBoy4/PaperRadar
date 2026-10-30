"""资格的最小内存投影;引用只比较身份,不在此解引用。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

from paper_radar.calibration.visibility import Visibility
from paper_radar.screening.reasons import ScreeningReasonInput

if TYPE_CHECKING:
    from paper_radar.feed_metadata.models import MetadataMissing, MetadataResult
    from paper_radar.screening_tasks.success_models import SuccessView


class Concept(StrEnum):
    CANONICAL_PAPER = "canonical_paper"
    CURRENT_VERSION = "current_version"
    METADATA_READY = "metadata_ready"
    EFFECTIVE_SCREENING_DECISION = "effective_screening_decision"
    DECISION_BASIS_STALE = "decision_basis_stale"
    CURRENT_SCREENING_ARTIFACT = "current_screening_artifact"
    NEEDS_PDF = "needs_pdf"
    NEEDS_EXTRACTION = "needs_extraction"
    EXTRACTION_FAILED = "extraction_failed"
    ELIGIBLE_FOR_AUTO_READ = "eligible_for_auto_read"
    REQUESTED_MANUAL_READ = "requested_manual_read"
    WAITING_CALIBRATION = "waiting_calibration"
    METADATA_UNOBTAINABLE = "metadata_unobtainable"
    CURRENT_SCREENING_SUGGESTION = "current_screening_suggestion"
    NEEDS_REFERENCE_HARVEST = "needs_reference_harvest"
    REFERENCE_LIST_COMPLETENESS = "reference_list_completeness"
    NEEDS_REUSE_ASSESSMENT = "needs_reuse_assessment"
    REUSE_ESCALATION_UNAVAILABLE = "reuse_escalation_unavailable"
    MANUAL_ACCEPTED_CHANNEL = "manual_accepted_channel"
    ACCEPTED_READ_BACKLOG = "accepted_read_backlog"
    MODEL_FAILURE_QUEUE = "model_failure_queue"
    WAITING_REVIEW = "waiting_review"
    WAITING_REPORT = "waiting_report"
    CAPACITY_WARNING = "capacity_warning"


class EligibilityReason(StrEnum):
    CANONICAL_UNKNOWN = "canonical_unknown"
    NOT_CANONICAL = "not_canonical"
    VERSION_UNKNOWN = "version_unknown"
    NOT_CURRENT_VERSION = "not_current_version"
    IDENTITY_CONTRADICTORY = "identity_contradictory"
    METADATA_UNKNOWN = "metadata_unknown"
    METADATA_INCOMPLETE = "metadata_incomplete"
    METADATA_STALE = "metadata_stale"
    METADATA_CONTRADICTORY = "metadata_contradictory"
    METADATA_NO_TITLE = "metadata_no_title"
    METADATA_NO_ABSTRACT = "metadata_no_abstract"
    METADATA_UNKNOWN_TRUNCATION = "metadata_unknown_truncation"
    METADATA_NO_SOURCE_URL = "metadata_no_source_url"
    METADATA_ROUTES_INCOMPLETE = "metadata_routes_incomplete"
    METADATA_AGENCY_UNKNOWN = "metadata_agency_unknown"
    METADATA_AGENCY_UNSUPPORTED = "metadata_agency_unsupported"
    DECISION_ABSENT = "decision_absent"
    DECISION_CONTRADICTORY = "decision_contradictory"
    DECISION_NOT_CURRENT = "decision_not_current"
    DECISION_BASIS_UNKNOWN = "decision_basis_unknown"
    DECISION_BASIS_CURRENT = "decision_basis_current"
    PROJECTION_NOT_DECISION = "projection_not_decision"
    GATE_PAUSED = "gate_paused"
    GATE_DISABLED = "gate_disabled"
    GATE_UNKNOWN = "gate_unknown"
    SCREENING_ABSENT = "screening_absent"
    SCREENING_UNKNOWN = "screening_unknown"
    SCREENING_HISTORICAL = "screening_historical"
    SCREENING_CONTRADICTORY = "screening_contradictory"
    DECISION_NOT_ACCEPTED = "decision_not_accepted"
    PDF_ABSENT = "pdf_absent"
    PDF_UNKNOWN = "pdf_unknown"
    PDF_HISTORICAL = "pdf_historical"
    PDF_CONTRADICTORY = "pdf_contradictory"
    PDF_ALREADY_PRESENT = "pdf_already_present"
    EXTRACTION_ABSENT = "extraction_absent"
    EXTRACTION_UNKNOWN = "extraction_unknown"
    EXTRACTION_HISTORICAL = "extraction_historical"
    EXTRACTION_CONTRADICTORY = "extraction_contradictory"
    EXTRACTION_ALREADY_PRESENT = "extraction_already_present"
    EXTRACTION_RETRY_REQUIRED = "extraction_retry_required"
    EXTRACTION_NOT_FAILED = "extraction_not_failed"
    QUALITY_FAILED = "quality_failed"
    QUALITY_ABSENT = "quality_absent"
    QUALITY_UNKNOWN = "quality_unknown"
    QUALITY_CONTRADICTORY = "quality_contradictory"
    QUALITY_NOT_FORMAL = "quality_not_formal"
    ROOT_UNKNOWN = "root_unknown"
    EXPERIMENT_NO_AUTO_QUEUE = "experiment_no_auto_queue"
    EXECUTION_SOURCE_UNKNOWN = "execution_source_unknown"
    TEST_EXECUTION_SOURCE = "test_execution_source"
    VISIBILITY_UNKNOWN = "visibility_unknown"
    VISIBILITY_DENIED = "visibility_denied"
    MANUAL_REQUEST_ABSENT = "manual_request_absent"
    MANUAL_REQUEST_CONTRADICTORY = "manual_request_contradictory"
    MANUAL_REQUEST_SUPERSEDED = "manual_request_superseded"
    MANUAL_DECISION_REQUIRED = "manual_decision_required"
    NOT_WAITING_CALIBRATION = "not_waiting_calibration"
    DUPLICATE_PAPER = "duplicate_paper"


class Support(StrEnum):
    SUPPORTED = "supported"
    PARTIAL = "partial"
    DEFERRED = "deferred"


class GateState(StrEnum):
    ENABLED = "enabled"
    PAUSED = "paused"
    DISABLED = "disabled"
    UNKNOWN = "unknown"


class Presence(StrEnum):
    PRESENT = "present"
    ABSENT = "absent"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ArtifactFact:
    presence: Presence = Presence.UNKNOWN
    reference: str | None = None
    version_id: str | None = None
    applicability: str = "undeterminable"

    @classmethod
    def from_success(cls, view: SuccessView, *, version_id: str) -> ArtifactFact:
        return cls(
            Presence.PRESENT, view.receipt.success_id, version_id, view.applicability
        )


class ExtractionState(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ABSENT = "absent"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ExtractionFact:
    state: ExtractionState = ExtractionState.UNKNOWN
    reference: str | None = None
    pdf_reference: str | None = None
    applicability: str = "undeterminable"


class QualityBasis(StrEnum):
    FORMAL_GATE = "formal_gate"
    EXPERIMENT_DOCUMENT_GATE = "experiment_document_gate"
    FAILED = "failed"
    ABSENT = "absent"
    UNKNOWN = "unknown"


class QualityFailure(StrEnum):
    PDF_TEXT_LAYER = "pdf_text_layer"
    BODY_BOUNDARY = "body_boundary"
    READING_ORDER = "reading_order"
    EVIDENCE_REPLAY = "evidence_replay"
    CONTENT_IDENTITY = "content_identity"
    LAYOUT_REVIEW = "layout_review"
    REPRESENTATIVE_COVERAGE = "representative_coverage"


@dataclass(frozen=True)
class QualityFact:
    basis: QualityBasis = QualityBasis.UNKNOWN
    extraction_reference: str | None = None
    failure: QualityFailure | None = None


class RootPurpose(StrEnum):
    PRODUCTION = "production"
    EXPERIMENT = "experiment"
    UNKNOWN = "unknown"


class ExecutionSource(StrEnum):
    PRODUCTION = "production"
    TEST = "test"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ManualReadRequest:
    reference: str
    paper_id: str
    accepted_decision_reference: str


@dataclass(frozen=True)
class DecisionFact:
    reference: str
    paper_id: str
    sequence: int
    record: ScreeningReasonInput
    applicability: str
    screening_reference: str | None = None


@dataclass(frozen=True)
class MetadataFacts:
    paper_id: str
    version_id: str
    revision_no: int
    minimum_complete: bool
    nontruncated_complete: bool
    current_version: bool
    missing: tuple[MetadataMissing, ...]

    @classmethod
    def from_result(cls, result: MetadataResult) -> MetadataFacts:
        return cls(
            result.paper_id,
            result.version_id,
            result.revision_no,
            result.minimum_complete,
            result.nontruncated_complete,
            result.current_version,
            result.missing,
        )


@dataclass(frozen=True)
class PaperProjection:
    paper_id: str
    version_id: str
    current_version_id: str | None
    canonical_id: str | None = None
    revision_no: int = 1
    metadata: MetadataFacts | None = None
    decisions: tuple[DecisionFact, ...] = ()
    gate: GateState = GateState.UNKNOWN
    screening: ArtifactFact = field(default_factory=ArtifactFact)
    pdf: ArtifactFact = field(default_factory=ArtifactFact)
    extraction: ExtractionFact = field(default_factory=ExtractionFact)
    quality: QualityFact = field(default_factory=QualityFact)
    root_purpose: RootPurpose = RootPurpose.UNKNOWN
    execution_source: ExecutionSource = ExecutionSource.UNKNOWN
    visibility: Visibility | None = None
    manual_request: ManualReadRequest | None = None
    # E 装配的独立失败事实;资格规则不由它推导全文或参考文献生命周期。
    reference_harvest_failed: bool | None = None


@dataclass(frozen=True)
class Eligibility:
    eligible: bool | None
    reasons: tuple[EligibilityReason, ...] = ()
    support: Support = Support.SUPPORTED
    scope: str = "predicate_only"
    decision: DecisionFact | None = None
    quality_failure: QualityFailure | None = None
    owner: str | None = None
