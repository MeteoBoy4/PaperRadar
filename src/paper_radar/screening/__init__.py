"""Screening 结构输出与纯验证公共接口。"""

from paper_radar.screening.context import ReuseAssessmentContext, ValuePredictionContext
from paper_radar.screening.errors import (
    OutputErrorCategory,
    OutputValidationError,
    OutputValidationIssue,
)
from paper_radar.screening.kinds import OutputKind
from paper_radar.screening.schema import (
    BoundaryOutput,
    ReuseAssessmentOutput,
    ValuePredictionOutput,
)
from paper_radar.screening.text import (
    EXPLICIT_PLACEHOLDER_TEXTS,
    INSUFFICIENT_INPUT_MARKERS,
)
from paper_radar.screening.validation import validate_output
from paper_radar.screening.value_types import VALUE_TYPE_DESCRIPTIONS_ZH, ValueType

__all__ = [
    "EXPLICIT_PLACEHOLDER_TEXTS",
    "INSUFFICIENT_INPUT_MARKERS",
    "VALUE_TYPE_DESCRIPTIONS_ZH",
    "BoundaryOutput",
    "OutputErrorCategory",
    "OutputKind",
    "OutputValidationError",
    "OutputValidationIssue",
    "ReuseAssessmentContext",
    "ReuseAssessmentOutput",
    "ValuePredictionContext",
    "ValuePredictionOutput",
    "ValueType",
    "validate_output",
]
