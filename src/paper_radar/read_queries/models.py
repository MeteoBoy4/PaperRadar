"""安全展示值;仅保留接受后的模型输出及受控状态。"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

from paper_radar.body.models import BodyIdentityReason
from paper_radar.reading.context import ExtractionIdentity
from paper_radar.reading.schema import ReadAnalysisOutput


class ReadConfigComponent(StrEnum):
    PROFILE = "profile"
    MODEL = "model"
    PROMPT = "prompt"
    CONTRACT = "contract"
    ADAPTER = "adapter"
    CHUNKING = "chunking"


DiscardCategory = Literal["main_findings", "reusable_points", "key_limitations"]


@dataclass(frozen=True)
class DiscardCount:
    category: DiscardCategory
    count: int


@dataclass(frozen=True)
class AnalysisView:
    analysis_id: str
    paper_id: str
    output_language: Literal["zh", "en"]
    identity: ExtractionIdentity
    body_status: Literal["current", "historical", "undeterminable"]
    body_reason: BodyIdentityReason | None
    config_status: Literal["current", "old", "unknown"]
    changed_components: tuple[ReadConfigComponent, ...]
    executor_kind: Literal["test", "pi_rpc"]
    root_purpose: str
    quality_basis: str
    output: ReadAnalysisOutput = field(repr=False)
    has_discards: bool
    discard_counts: tuple[DiscardCount, ...]
    restricted_content_warning: bool


@dataclass(frozen=True)
class CurrentRead:
    paper_id: str
    state: Literal["undeterminable", "no_analysis", "available"]
    identity: ExtractionIdentity | None
    analyses: tuple[AnalysisView, ...]
    identity_reason: BodyIdentityReason | None = None


@dataclass(frozen=True)
class OldReadConfig:
    paper_id: str
    analysis_id: str
    output_language: Literal["zh", "en"]
    changed_components: tuple[ReadConfigComponent, ...]
