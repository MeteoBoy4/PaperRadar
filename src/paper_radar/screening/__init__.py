"""Screening 结构输出与纯验证公共接口。"""

from paper_radar.screening.context import ReuseAssessmentContext, ValuePredictionContext
from paper_radar.screening.errors import (
    OutputErrorCategory,
    OutputValidationError,
    OutputValidationIssue,
)
from paper_radar.screening.excerpt_kinds import ExcerptKind
from paper_radar.screening.kinds import OutputKind
from paper_radar.screening.reasons import (
    DECISION_REASON_DEFINITIONS,
    DECISION_REASON_DESCRIPTIONS_ZH,
    SCREENING_RESULT_DESCRIPTIONS_ZH,
    SCREENING_SOURCE_DESCRIPTIONS_ZH,
    DecisionReason,
    DecisionReasonDefinition,
    ScreeningDecision,
    ScreeningFailureProjection,
    ScreeningReason,
    ScreeningResult,
    ScreeningSource,
    ScreeningSuggestion,
    screening_reason_json_schema,
)
from paper_radar.screening.schema import (
    BoundaryOutput,
    ReuseAssessmentOutput,
    ValuePredictionOutput,
)
from paper_radar.screening.text import (
    EXPLICIT_PLACEHOLDER_TEXTS,
    INSUFFICIENT_INPUT_MARKERS,
)
from paper_radar.screening.validation import validate_output, validate_screening_reason
from paper_radar.screening.value_types import VALUE_TYPE_DESCRIPTIONS_ZH, ValueType

__all__ = [
    "DECISION_REASON_DEFINITIONS",
    "DECISION_REASON_DESCRIPTIONS_ZH",
    "EXPLICIT_PLACEHOLDER_TEXTS",
    "INSUFFICIENT_INPUT_MARKERS",
    "SCREENING_RESULT_DESCRIPTIONS_ZH",
    "SCREENING_SOURCE_DESCRIPTIONS_ZH",
    "VALUE_TYPE_DESCRIPTIONS_ZH",
    "BoundaryOutput",
    "DecisionReason",
    "DecisionReasonDefinition",
    "ExcerptKind",
    "OutputErrorCategory",
    "OutputKind",
    "OutputValidationError",
    "OutputValidationIssue",
    "ReuseAssessmentContext",
    "ReuseAssessmentOutput",
    "ScreeningDecision",
    "ScreeningFailureProjection",
    "ScreeningReason",
    "ScreeningResult",
    "ScreeningSource",
    "ScreeningSuggestion",
    "ValuePredictionContext",
    "ValuePredictionOutput",
    "ValueType",
    "screening_reason_json_schema",
    "validate_output",
    "validate_screening_reason",
]
