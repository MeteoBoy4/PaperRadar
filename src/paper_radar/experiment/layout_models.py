"""版式编排与渲染共享的不可变正文 DTO;不执行查询或 I/O。"""

from dataclasses import dataclass, field

from paper_radar.body.models import ExtractionView
from paper_radar.experiment.pdf import FrozenSample
from paper_radar.fulltext.models import EvidenceMap, LoadedExtraction


@dataclass(frozen=True)
class LayoutBody:
    sample: FrozenSample
    view: ExtractionView
    loaded: LoadedExtraction = field(repr=False)
    evidence_map: EvidenceMap = field(repr=False)
    pdf: bytes = field(repr=False)
