"""安全元数据结果;原始材料及全文摘要经显式入口读取。"""

from typing import Literal

from pydantic import Field, field_validator

from paper_radar.fixture_audit.abstract_models import AbstractCandidate, ExcludedBlock
from paper_radar.fixture_audit.acquisition_models import (
    HTTPFacts,
    Route,
    SourceReason,
    SourceRequest,
    require_utc_timestamp,
)
from paper_radar.fixture_audit.models import FrozenModel
from paper_radar.fixture_audit.sampling_models import CategoryBasis
from paper_radar.papers.models import SourceKind

RegistryApplicability = Literal[
    "agency_unknown", "agency_unsupported", "applicable", "not_applicable_no_doi"
]
MetadataMissing = Literal[
    "current_version_changed",
    "no_title",
    "no_abstract",
    "unknown_truncation",
    "no_source_url",
    "routes_incomplete",
    "agency_unknown",
    "agency_unsupported",
]


class MetadataBasis(FrozenModel):
    paper_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    version_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    doi: str | None
    revision_no: int = Field(ge=1)
    request_id: str = Field(min_length=1, max_length=128)
    observed_at: str

    @field_validator("observed_at")
    @classmethod
    def valid_timestamp(cls, value: str) -> str:
        return require_utc_timestamp(value)


class MetadataRoute(FrozenModel):
    route: Route
    request: SourceRequest
    observed_at: str
    reason: SourceReason = "outcome_unknown"
    http: HTTPFacts | None = None
    agency: str | None = None
    artifact_id: str | None = None
    payload_sha256: str | None = None
    candidates: tuple[AbstractCandidate, ...] = ()
    excluded_blocks: tuple[ExcludedBlock, ...] = ()
    categories: tuple[CategoryBasis, ...] = ()
    acquisition_id: str | None = None
    committed: bool = False
    abstract_rules_version: Literal["audit-abstract-v1"] = "audit-abstract-v1"
    truncation_rules_version: Literal["audit-truncation-v1"] = "audit-truncation-v1"


class MetadataResult(FrozenModel):
    request_key: str
    paper_id: str
    version_id: str
    revision_no: int
    title: str | None = None
    abstract_present: bool = False
    suspected_truncated: bool | None = None
    source_url: str | None = None
    routes: tuple[MetadataRoute, ...] = ()
    routes_settled: bool = False
    registry_applicability: RegistryApplicability = "agency_unknown"
    current_version: bool = True
    minimum_complete: bool = False
    nontruncated_complete: bool = False
    missing: tuple[MetadataMissing, ...] = ()
    scope: str = "仅证明元数据工程路径;真实 JGR 判据、来源假设及 B 入口未验证"


class MetadataContent(FrozenModel):
    result: MetadataResult
    abstract: str | None = None
    abstract_source_kind: SourceKind | None = None
    abstract_observed_at: str | None = None
    abstract_locator: str | None = None
