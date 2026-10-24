"""深度只读的 Read 接收依据与供显式消费的分析视图。"""

from dataclasses import dataclass, field
from typing import Literal

from paper_radar.reading.context import ExtractionIdentity, SourceSlice
from paper_radar.reading.numbers import NumericReason
from paper_radar.reading.schema import ReadAnalysisOutput


@dataclass(frozen=True, slots=True)
class ReadDiagnostic:
    location: str
    reason: NumericReason
    ordinal: int


@dataclass(frozen=True, slots=True)
class ReadWarning:
    origin: Literal["model", "program"]
    text: str = field(repr=False)
    diagnostic: ReadDiagnostic | None = None


@dataclass(frozen=True, slots=True)
class ReadValidationResult:
    identity: ExtractionIdentity
    mode: Literal["single", "reduce"]
    evidence_rule_version: str
    numeric_rule_version: str
    _analysis_json: bytes = field(repr=False)
    model_warnings: tuple[str, ...] = field(repr=False)
    diagnostics: tuple[ReadDiagnostic, ...]
    warnings: tuple[ReadWarning, ...]
    support: tuple[SourceSlice, ...] = field(repr=False)

    @property
    def analysis(self) -> ReadAnalysisOutput:
        """返回独立副本;调用方修改列表不改变已接收的结果。"""
        return ReadAnalysisOutput.model_validate_json(self._analysis_json)
