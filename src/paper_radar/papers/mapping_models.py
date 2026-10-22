"""mapping_result v1:阶段输入与不参与身份计算的业务依据。"""

from dataclasses import dataclass, field
from typing import Literal

from paper_radar.papers.errors import PaperReason
from paper_radar.papers.models import RevisionView
from paper_radar.stage_inputs import StageInput


class MappingEvidence(RevisionView):
    snapshot_id: str
    source_bytes_verified: Literal[False] = False


@dataclass(frozen=True, slots=True)
class StageMappingResult:
    value: StageInput | None = field(repr=False)
    reason: PaperReason | None
    evidence: MappingEvidence | None = field(repr=False)
    snapshot_id: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class ScreeningMappingResult:
    snapshot_id: str = field(repr=False)
    evidence: MappingEvidence | None = field(repr=False)
    boundary: StageMappingResult
    value: StageMappingResult
    format_version: Literal[1] = field(default=1, init=False)
