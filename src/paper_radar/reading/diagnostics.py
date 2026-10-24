"""不依赖上下文或结果层的安全 Read 降级诊断。"""

from dataclasses import dataclass
from enum import StrEnum


class NumericReason(StrEnum):
    NUMBER_NOT_SUPPORTED = "number_not_supported"
    RANGE_NOT_SUPPORTED = "range_not_supported"
    UNIT_NOT_SUPPORTED = "unit_not_supported"
    UNRECOGNIZED_NUMERIC_FORM = "unrecognized_numeric_form"
    RESTRICTED_NUMERIC_SUPPORT = "restricted_numeric_support"


@dataclass(frozen=True, slots=True)
class ReadDiagnostic:
    location: str
    reason: NumericReason
    ordinal: int
