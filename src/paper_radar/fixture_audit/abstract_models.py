"""摘要解释只保存安全投影;原文通过显式材料读取接口取得。"""

from typing import Literal

from pydantic import Field

from paper_radar.fixture_audit.acquisition_models import (
    Channel,
    SourceReason,
    SourceRequest,
)
from paper_radar.fixture_audit.models import FrozenModel, Journal
from paper_radar.fixture_audit.sampling_models import SamplingAuditView

ABSTRACT_RULES_VERSION = "audit-abstract-v1"
TRUNCATION_RULES_VERSION = "audit-truncation-v1"
MATRIX_RULES_VERSION = "audit-matrix-v1"
Signal = Literal[
    "short_under_100",
    "trailing_ellipsis",
    "read_more",
    "markup_residue",
    "missing_terminal_punctuation",
]


class AbstractCandidate(FrozenModel):
    candidate_id: str
    field: Literal["title", "abstract"]
    source_kind: Literal["publisher", "registry", "feed"]
    locator: str
    text_sha256: str
    codepoints: int
    signals: tuple[Signal, ...] = ()
    suspected_truncated: bool = False


class ExcludedBlock(FrozenModel):
    kind: Literal[
        "abstract_en",
        "significance",
        "plain_language_summary",
        "key_points",
        "preface",
        "citation_tail",
    ]
    locator: str


class MatrixRow(FrozenModel):
    row_id: str
    generation: int = Field(default=1, ge=1)
    previous_row_id: str | None = None
    interpretation_pending: bool = False
    plan_id: str
    member_id: str
    request: SourceRequest
    acquisition_id: str | None = None
    reason: SourceReason
    valid_record: bool = False
    observed_at: str | None = None
    payload_sha256: str | None = None
    candidates: tuple[AbstractCandidate, ...] = ()
    excluded_blocks: tuple[ExcludedBlock, ...] = ()
    abstract_rules_version: str = ABSTRACT_RULES_VERSION
    truncation_rules_version: str = TRUNCATION_RULES_VERSION
    matrix_rules_version: str = MATRIX_RULES_VERSION


class CandidateDecision(FrozenModel):
    candidate_id: str
    acquisition_id: str
    field: Literal["title", "abstract"]
    selected: bool
    reason: Literal[
        "selected", "lower_source_priority", "earlier_observation_or_stable_tiebreak"
    ]


class MemberAbstract(FrozenModel):
    member_id: str
    journal: Journal
    routes_settled: bool
    final_title_candidate_id: str | None = None
    final_abstract_candidate_id: str | None = None
    final_title_source: str | None = None
    final_abstract_source: str | None = None
    priority_truncation_conflict: bool = False
    decisions: tuple[CandidateDecision, ...] = ()
    registry_applicability: Literal[
        "applicable", "not_applicable_no_doi", "agency_unsupported", "agency_unknown"
    ]
    publisher_applicability: Literal[
        "applicable", "not_applicable_no_doi", "target_unknown"
    ]


class Fraction(FrozenModel):
    numerator: int
    denominator: int
    ratio: float | None
    zero_denominator: Literal["not_applicable", "unknown"] | None = None


class RouteSummary(FrozenModel):
    journal: Journal
    route: str
    strategy_version: str
    channel: Channel
    applicable: int
    attempted: int
    not_attempted: int
    channel_not_installed: int
    valid_records: int
    nonempty_abstracts: int
    suspected_truncated: int
    errors: int
    abstract_coverage: Fraction
    executor_delivered: bool
    channel_status: Literal["installed", "channel_not_installed", "not_applicable"]


class JournalSummary(FrozenModel):
    journal: Journal
    target: int
    selected: int
    considered: int
    excluded: int
    unknown: int
    conflicts: int
    shortfall: int | None
    sampling_status: str
    date_start: str | None
    date_end: str | None
    unknown_dates: int
    priority_truncation_conflicts: int
    final_abstract_sources: dict[str, int]
    registry_not_applicable_no_doi: int
    registry_agency_unsupported: int
    registry_agency_unknown: int
    publisher_target_unknown: int


class AbstractAuditView(SamplingAuditView):
    status: Literal["partial", "complete"] = "partial"
    matrix: tuple[MatrixRow, ...] = ()
    matrix_history: tuple[MatrixRow, ...] = ()
    members: tuple[MemberAbstract, ...] = ()
    route_summaries: tuple[RouteSummary, ...] = ()
    journal_summaries: tuple[JournalSummary, ...] = ()
    physical_http_requests: int = 0
    physical_http_unknown_executions: int = 0
    http_redirects: int = 0
    http_retries: int = 0
    next_step: str = (
        "显式运行或继续未结算路线;complete 仅表示终态齐备，"
        "来源稳定性和阶段 B 门禁待裁决"
    )
