"""Screening 结构输出与纯验证公共接口。"""

from paper_radar.screening.errors import (
    OutputErrorCategory,
    OutputValidationError,
    OutputValidationIssue,
)
from paper_radar.screening.kinds import OutputKind
from paper_radar.screening.schema import BoundaryOutput
from paper_radar.screening.text import EXPLICIT_PLACEHOLDER_TEXTS
from paper_radar.screening.validation import validate_output

__all__ = [
    "EXPLICIT_PLACEHOLDER_TEXTS",
    "BoundaryOutput",
    "OutputErrorCategory",
    "OutputKind",
    "OutputValidationError",
    "OutputValidationIssue",
    "validate_output",
]
