"""封闭论文事实公共边界。"""

from typing import TYPE_CHECKING

from paper_radar.papers.doi import normalize_doi
from paper_radar.papers.errors import PaperError, PaperReason
from paper_radar.papers.models import (
    AbstractValue,
    CandidateInput,
    DateValue,
    ObservationInput,
    WriteResult,
)

if TYPE_CHECKING:
    from paper_radar.papers.service import PaperFacts


def __getattr__(name: str) -> object:
    if name == "PaperFacts":
        from paper_radar.papers.service import PaperFacts

        return PaperFacts
    raise AttributeError(name)


__all__ = [
    "AbstractValue",
    "CandidateInput",
    "DateValue",
    "ObservationInput",
    "PaperError",
    "PaperFacts",
    "PaperReason",
    "WriteResult",
    "normalize_doi",
]
