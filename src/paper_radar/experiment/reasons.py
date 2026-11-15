"""实验产品边界的封闭原因词汇;未知运行时输入不进入用户输出。"""

from enum import StrEnum
from typing import Self


class _ControlledReason(StrEnum):
    @classmethod
    def _missing_(cls, value: object) -> Self:
        return cls("invalid_reason")


class AcceptanceReason(_ControlledReason):
    INVALID_REASON = "invalid_reason"
    ALREADY_ACCEPTED = "already_accepted"
    BOUNDARY_MISSING = "boundary_missing"
    FROZEN_VERSION_CHANGED = "frozen_version_changed"
    INVALID_REQUEST = "invalid_request"
    OUT_OF_SCOPE = "out_of_scope"
    REGISTRATION_INVALID = "registration_invalid"
    REQUEST_CONFLICT = "request_conflict"
    SELECTION_CHANGED = "selection_changed"
    SELECTION_MISMATCH = "selection_mismatch"
    SUCCESS_MISMATCH = "success_mismatch"
    TEST_SOURCE = "test_source"
    VALUE_MISSING = "value_missing"
    VISIBILITY_DENIED = "visibility_denied"


class BodySelectionReason(_ControlledReason):
    INVALID_REASON = "invalid_reason"
    INVALID_CLOCK = "invalid_clock"
    INVALID_IDENTITY = "invalid_identity"
    OWNER_AUTHORIZATION_REQUIRED = "owner_authorization_required"
    REQUEST_CONFLICT = "request_conflict"


class EgressReason(_ControlledReason):
    INVALID_REASON = "invalid_reason"
    EGRESS_ACTION_INVALID = "egress_action_invalid"
    EGRESS_CATEGORY_MISMATCH = "egress_category_mismatch"
    EGRESS_CLOCK_INVALID = "egress_clock_invalid"
    EGRESS_HISTORY_INVALID = "egress_history_invalid"
    EGRESS_MODEL_MISMATCH = "egress_model_mismatch"
    EGRESS_MODEL_UNCONFIGURED = "egress_model_unconfigured"
    EGRESS_NOT_AUTHORIZED = "egress_not_authorized"
    EGRESS_SCOPE_MISMATCH = "egress_scope_mismatch"
    EGRESS_UNAVAILABLE = "egress_unavailable"


class ExtractionReason(_ControlledReason):
    INVALID_REASON = "invalid_reason"
    CGROUP_CHANGED = "cgroup_changed"
    CGROUP_LIMIT_INVALID = "cgroup_limit_invalid"
    EXTRACTION_UNSELECTED = "extraction_unselected"
    MODEL_DEPLOYMENT_INVALID = "model_deployment_invalid"
    MODEL_DEPLOYMENT_MISSING = "model_deployment_missing"
    MODEL_SNAPSHOT_SPACE_INSUFFICIENT = "model_snapshot_space_insufficient"
    REGISTRATION_INVALID = "registration_invalid"
    RUNTIME_SELECTION_INVALID = "runtime_selection_invalid"


class LayoutReason(_ControlledReason):
    INVALID_REASON = "invalid_reason"
    AMBIGUOUS_EXTRACTIONS = "ambiguous_extractions"
    BODY_IDENTITY_MISMATCH = "body_identity_mismatch"
    EXTRACTION_ABSENT = "extraction_absent"
    MATERIALS_CONFLICT = "materials_conflict"
    OWNER_CONCLUSIONS_REQUIRED = "owner_conclusions_required"
    PDF_ABSENT = "pdf_absent"
    PDF_GEOMETRY_MISMATCH = "pdf_geometry_mismatch"
    PDF_PAGES_MISMATCH = "pdf_pages_mismatch"
    PDF_RENDER_FAILED = "pdf_render_failed"
    REGISTRATION_INVALID = "registration_invalid"
    RENDER_LIMIT_EXCEEDED = "render_limit_exceeded"
    RENDERER_DEPENDENCY_MISSING = "renderer_dependency_missing"
    REQUEST_CONFLICT = "request_conflict"
    ROOT_MISMATCH = "root_mismatch"
    UNSAFE_MATERIAL_PATH = "unsafe_material_path"
    VISIBILITY_DENIED = "visibility_denied"


class PdfReason(_ControlledReason):
    INVALID_REASON = "invalid_reason"
    ACCEPTANCE_MISSING = "acceptance_missing"
    CONFIRMATION_MISMATCH = "confirmation_mismatch"
    FROZEN_VERSION_CHANGED = "frozen_version_changed"
    INVALID_CLOCK = "invalid_clock"
    INVALID_PDF = "invalid_pdf"
    INVALID_REQUEST = "invalid_request"
    OWNER_CONFIRMATION_REQUIRED = "owner_confirmation_required"
    PDF_UNREADABLE = "pdf_unreadable"
    REGISTRATION_INVALID = "registration_invalid"
    REQUEST_CONFLICT = "request_conflict"
    SAMPLE_MISMATCH = "sample_mismatch"
    SAMPLE_MISSING = "sample_missing"
    SELECTION_CHANGED = "selection_changed"
    VISIBILITY_DENIED = "visibility_denied"


class ReadingReason(_ControlledReason):
    INVALID_REASON = "invalid_reason"
    BODY_IDENTITY_MISMATCH = "body_identity_mismatch"
    DOCUMENT_GATE_REQUIRED = "document_gate_required"
    INVALID_EXECUTION_MODE = "invalid_execution_mode"
    OWNER_REVIEW_REQUIRED = "owner_review_required"
    REGISTRATION_INVALID = "registration_invalid"
    REQUEST_CONFLICT = "request_conflict"
    SAMPLE_CHANGED = "sample_changed"
    TASK_RUNNING = "task_running"
    TASK_SCOPE_MISMATCH = "task_scope_mismatch"


class ReportReason(_ControlledReason):
    INVALID_REASON = "invalid_reason"
    OUTPUT_DIRECTORY_REQUIRED = "output_directory_required"
    ANALYSIS_NOT_FOUND = "analysis_not_found"
    ANALYSIS_SCOPE_INVALID = "analysis_scope_invalid"
    CONTENT_CORRUPT = "content_corrupt"
    FACTS_CHANGED = "facts_changed"
    FILE_MISSING = "file_missing"
    INVALID_CLOCK = "invalid_clock"
    INVALID_DATE_TIMEZONE = "invalid_date_timezone"
    ORDINARY_CONSUMPTION_DENIED = "ordinary_consumption_denied"
    REGISTRATION_INVALID = "registration_invalid"
    REPORT_NOT_FOUND = "report_not_found"
    UNSAFE_PATH = "unsafe_path"
    VISIBILITY_DENIED = "visibility_denied"


class ScreenReason(_ControlledReason):
    INVALID_REASON = "invalid_reason"
    ALREADY_SUCCEEDED = "already_succeeded"
    BASIS_CHANGED = "basis_changed"
    BOUNDARY_MISSING = "boundary_missing"
    BUDGET_EXHAUSTED = "budget_exhausted"
    CANDIDATE_NOT_FOUND = "candidate_not_found"
    CANDIDATE_NOT_READY = "candidate_not_ready"
    EGRESS_ACTION_INVALID = "egress_action_invalid"
    EGRESS_CATEGORY_MISMATCH = "egress_category_mismatch"
    EGRESS_CLOCK_INVALID = "egress_clock_invalid"
    EGRESS_HISTORY_INVALID = "egress_history_invalid"
    EGRESS_MODEL_MISMATCH = "egress_model_mismatch"
    EGRESS_MODEL_UNCONFIGURED = "egress_model_unconfigured"
    EGRESS_NOT_AUTHORIZED = "egress_not_authorized"
    EGRESS_SCOPE_MISMATCH = "egress_scope_mismatch"
    EGRESS_UNAVAILABLE = "egress_unavailable"
    FROZEN_VERSION_CHANGED = "frozen_version_changed"
    INVALID_CLOCK = "invalid_clock"
    INVALID_EXECUTION_MODE = "invalid_execution_mode"
    INVALID_REQUEST = "invalid_request"
    LEASE_UNSETTLED = "lease_unsettled"
    METADATA_NOT_READY = "metadata_not_ready"
    RECEIPT_SCOPE_MISMATCH = "receipt_scope_mismatch"
    REGISTRATION_INVALID = "registration_invalid"
    REPLACEMENT_REQUIRED = "replacement_required"
    REQUEST_CONFLICT = "request_conflict"
    SELECTION_CHANGED = "selection_changed"
    TASK_RUNNING = "task_running"
    TEST_SOURCE = "test_source"
    VISIBILITY_DENIED = "visibility_denied"
