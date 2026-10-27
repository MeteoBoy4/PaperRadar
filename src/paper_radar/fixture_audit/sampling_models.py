"""固定 Feed、显式类别依据与只追加选样台账。"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from paper_radar.fixture_audit.acquisition_models import (
    CATEGORY_RULES_VERSION,
    SAMPLING_RULES_VERSION,
    AuditView,
    Route,
    SourceReason,
)
from paper_radar.fixture_audit.models import FrozenModel, Journal


class RawCategory(FrozenModel):
    field: Literal["category", "prism:section", "dc:type", "other:type"]
    value: str


class IdentityField(FrozenModel):
    locator: str
    value: str
    doi: str | None = None


class FeedCandidate(FrozenModel):
    position: int = Field(ge=1, le=50)
    entry_locator: str
    order_locator: str
    entry_id: str | None = None
    entry_id_locator: str | None = None
    doi: str | None = None
    identity_fields: tuple[IdentityField, ...] = ()
    identity_issue: Literal["invalid_doi", "conflicting_dois"] | None = None
    publisher_url: str | None = None
    publisher_link_reason: SourceReason | None = None
    raw_categories: tuple[RawCategory, ...] = ()
    published_raw: str | None = None
    published_value: str | None = None
    published_precision: Literal["unknown", "year", "month", "day", "second"] = (
        "unknown"
    )


class FrozenFeed(FrozenModel):
    freeze_id: str
    plan_id: str
    journal: Journal
    acquisition_id: str
    artifact_id: str
    payload_sha256: str
    parser_version: str
    total_candidates: int = Field(ge=0)
    candidates: tuple[FeedCandidate, ...]
    payload_scope: Literal["whole_feed"] = "whole_feed"


CategoryDecision = Literal["journal_article", "non_journal_article", "unknown"]
CategoryResult = Literal[
    "journal_article", "non_journal_article", "conflict", "unknown"
]


class CategoryBasis(FrozenModel):
    route: Route
    locator: str
    value: str
    decision: CategoryDecision
    acquisition_id: str | None = None


class SamplingRoute(FrozenModel):
    route: Route
    acquisition_id: str | None = None
    reason: SourceReason
    applicable: bool = True


SamplingReason = Literal[
    "selected",
    "duplicate",
    "no_stable_identifier",
    "identity_unavailable",
    "invalid_identity",
    "identity_conflict",
    "category_unknown",
    "category_conflict",
    "not_journal_article",
    "source_blocked",
    "feed_unavailable",
    "invalid_feed",
]


class SamplingOutcome(FrozenModel):
    event_id: str
    plan_id: str
    journal: Journal
    previous_event_id: str | None = None
    position: int | None = Field(default=None, ge=1, le=50)
    candidate: FeedCandidate | None = None
    result: Literal["selected", "excluded_deterministic", "blocked_pending"]
    reason: SamplingReason
    doi: str | None = None
    entry_id: str | None = None
    category_bases: tuple[CategoryBasis, ...] = ()
    routes: tuple[SamplingRoute, ...] = ()
    member_id: str | None = None
    sampling_rules_version: str = SAMPLING_RULES_VERSION
    category_rules_version: str = CATEGORY_RULES_VERSION


class SamplingMember(FrozenModel):
    member_id: str
    journal: Journal
    position: int
    doi: str | None
    entry_id: str | None
    feed_freeze_id: str
    selection_event_id: str


class JournalSampling(FrozenModel):
    journal: Journal
    feed: FrozenFeed | None = None
    status: Literal["feed_pending", "selecting", "blocked_pending", "complete"]
    next_position: int
    target_count: int
    total_candidates: int | None
    considered: int
    shortfall: int | None
    members: tuple[SamplingMember, ...] = ()
    entries: tuple[SamplingOutcome, ...] = ()
    history: tuple[SamplingOutcome, ...] = ()


class SamplingAuditView(AuditView):
    sampling: tuple[JournalSampling, ...] = ()
