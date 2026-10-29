"""组合读面默认只返回依据和受控状态。"""

from dataclasses import dataclass, field
from typing import Literal

from paper_radar.feed_ingestion.models import FeedItemReason
from paper_radar.feed_metadata.models import MetadataResult
from paper_radar.papers.models import (
    AcquisitionFact,
    CandidateDecision,
    ConflictView,
    DiscoveryFact,
    FieldFact,
    SelectionFact,
    SourceKind,
)
from paper_radar.screening_tasks.language import LanguageBasis, LanguageTrace
from paper_radar.screening_tasks.models import RequestReceipt


@dataclass(frozen=True)
class PreparedItem:
    position: int
    paper_id: str | None
    metadata_request_key: str | None = None
    metadata: MetadataResult | None = None
    conflict_id: str | None = None
    reason: FeedItemReason | Literal["metadata_incomplete"] | None = None


@dataclass(frozen=True)
class Preparation:
    check_id: str
    items: tuple[PreparedItem, ...]
    scope: str = "仅为工程准备结果;真实来源、B入口及自动执行资格未验证"


@dataclass(frozen=True)
class ValueRegistration:
    purpose: Literal["production", "test"]
    receipt: RequestReceipt
    metadata_request_key: str
    boundary_success_id: str
    language_basis: LanguageBasis
    scope: str = "仅登记任务;不执行模型、不授予B或自动Read资格"


@dataclass(frozen=True)
class CandidateReference:
    """候选/获选的来源依据投影;不携带字段文本。"""

    version_id: str
    field_name: str
    candidate_id: str
    observation_id: str
    acquisition_id: str | None
    artifact_id: str
    source_kind: SourceKind
    provider: str
    query_key: str
    parser_version: int
    observed_at: str
    source_observed_at: str
    locator: str
    rule_version: int
    text_norm: int

    @classmethod
    def from_fact(
        cls, version_id: str, field_name: str, fact: FieldFact
    ) -> "CandidateReference":
        return cls(
            version_id=version_id,
            field_name=field_name,
            **fact.model_dump(exclude={"value"}),
        )


@dataclass(frozen=True)
class PipelineTrace:
    paper_id: str
    version_id: str
    revision_no: int
    metadata: tuple[MetadataResult, ...]
    conflicts: tuple[ConflictView, ...]
    language: LanguageTrace
    receipts: tuple[RequestReceipt, ...]
    fields: dict[str, CandidateReference] = field(default_factory=dict)
    selection: SelectionFact | None = None
    candidates: tuple[CandidateReference, ...] = ()
    decisions: tuple[CandidateDecision, ...] = ()
    discoveries: tuple[DiscoveryFact, ...] = ()
    acquisitions: tuple[AcquisitionFact, ...] = ()
