"""Read 权威结构输出与冻结价值词汇。"""

from paper_radar.reading.context import (
    EVIDENCE_RULE_VERSION,
    AllowedEvidence,
    Evidence,
    ExtractionIdentity,
    PageFact,
    Provenance,
    ReadContext,
    SourceBlock,
    SourceSlice,
)
from paper_radar.reading.diagnostics import NumericReason, ReadDiagnostic
from paper_radar.reading.errors import (
    ReadContextError,
    ReadErrorCategory,
    ReadIssue,
    ReadOutputError,
)
from paper_radar.reading.numbers import NUMERIC_RULE_VERSION
from paper_radar.reading.result import ReadValidationResult, ReadWarning
from paper_radar.reading.schema import (
    EvidenceRef,
    ReadAnalysisOutput,
    ReusablePoint,
    SupportedStatement,
)
from paper_radar.reading.validation import validate_read_output
from paper_radar.reading.value_types import VALUE_TYPE_DESCRIPTIONS_ZH, ValueType

__all__ = [
    "EVIDENCE_RULE_VERSION",
    "NUMERIC_RULE_VERSION",
    "VALUE_TYPE_DESCRIPTIONS_ZH",
    "AllowedEvidence",
    "Evidence",
    "EvidenceRef",
    "ExtractionIdentity",
    "NumericReason",
    "PageFact",
    "Provenance",
    "ReadAnalysisOutput",
    "ReadContext",
    "ReadContextError",
    "ReadDiagnostic",
    "ReadErrorCategory",
    "ReadIssue",
    "ReadOutputError",
    "ReadValidationResult",
    "ReadWarning",
    "ReusablePoint",
    "SourceBlock",
    "SourceSlice",
    "SupportedStatement",
    "ValueType",
    "validate_read_output",
]
