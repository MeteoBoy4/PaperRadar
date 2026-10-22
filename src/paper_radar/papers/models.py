"""论文事实边界的封闭类型;无 I/O。"""

from datetime import datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, ValidationError

from paper_radar.papers.errors import PaperError, PaperReason

PAPER_FACTS_VERSION = 1
TEXT_NORM_VERSION = 1
FieldName = Literal[
    "title",
    "abstract",
    "authors",
    "journal",
    "volume",
    "issue",
    "pages",
    "online_date",
    "print_date",
    "source_url",
]
VersionKind = Literal["preprint", "journal"]
ConflictKind = Literal[
    "doi_owner_conflict",
    "target_mismatch",
    "version_kind_conflict",
    "entry_doi_changed",
]


class ClosedModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        hide_input_in_errors=True,
        revalidate_instances="always",
    )

    def __init__(self, **data: Any) -> None:
        try:
            super().__init__(**data)
        except ValidationError:
            raise ValueError("invalid_observation") from None

    @classmethod
    def model_validate(
        cls,
        obj: Any,
        *,
        strict: bool | None = None,
        extra: Literal["allow", "ignore", "forbid"] | None = None,
        from_attributes: bool | None = None,
        context: Any | None = None,
        by_alias: bool | None = None,
        by_name: bool | None = None,
    ) -> Self:
        try:
            return super().model_validate(
                obj,
                strict=strict,
                extra=extra,
                from_attributes=from_attributes,
                context=context,
                by_alias=by_alias,
                by_name=by_name,
            )
        except (ValidationError, ValueError):
            raise PaperError(PaperReason.INVALID_OBSERVATION) from None

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"

    def __str__(self) -> str:
        return repr(self)


class AbstractValue(ClosedModel):
    text: str
    is_truncated: bool | None
    rule: str


class DateValue(ClosedModel):
    value: str
    precision: Literal["year", "month", "day"]


class CandidateInput(ClosedModel):
    value: str | tuple[str, ...] | AbstractValue | DateValue
    locator: str


class ObservationInput(ClosedModel):
    doi: str | None
    scheme: str = "doi"
    version_kind: VersionKind
    source_kind: str
    provider: str = ""
    query_key: str = ""
    feed_id: str | None = None
    entry_id: str | None = None
    payload_scope: Literal["single_item"] | None = None
    observed_at: datetime
    parser_version: int
    payload: bytes
    fields: dict[str, CandidateInput]
    interpretation: Literal["complete"]
    target_paper_id: str | None = None
    target_version_id: str | None = None
    relations: tuple[object, ...] = ()


class WriteResult(ClosedModel):
    status: Literal["retained", "not_retained", "rejected"]
    reason_catalog_version: Literal[1] = 1
    reason: PaperReason | None = None
    conflict: ConflictKind | None = None
    paper_id: str | None = None
    version_id: str | None = None
    revision_no: int | None = None
    observation_id: str | None = None
    acquisition_id: str | None = None
    discovery_id: str | None = None


class FieldFact(ClosedModel):
    acquisition_id: str | None = None
    source_observed_at: str
    source_kind: Literal["publisher", "feed"]
    provider: str
    query_key: str
    observed_at: str
    parser_version: int
    artifact_id: str
    candidate_id: str
    observation_id: str
    value: str | tuple[str, ...] | AbstractValue | DateValue
    locator: str
    text_norm: Literal[1] = 1
    rule_version: Literal[1] = 1


class SelectionFact(ClosedModel):
    selection_id: str
    version_id: str
    reason: Literal["initial"]
    selected_at: str


class PaperView(ClosedModel):
    scope: Literal["仅覆盖论文事实；尚未计算完整任务资格"] = (
        "仅覆盖论文事实；尚未计算完整任务资格"
    )
    paper_id: str
    version_id: str
    revision_no: int
    version_kind: VersionKind
    doi: str | None
    fields: dict[str, FieldFact]
    selection: SelectionFact


class ObservationFact(ClosedModel):
    observation_id: str
    version_id: str
    source_kind: Literal["publisher", "feed"]
    provider: str
    query_key: str
    observed_at: str
    parser_version: int
    artifact_id: str
    payload_sha256: str
    fields: dict[str, FieldFact]


class AcquisitionFact(ClosedModel):
    source_kind: Literal["publisher", "feed"]
    raw_doi: str | None

    parsed_sha256: str
    interpretation: Literal["complete"]
    acquisition_id: str
    event_no: int | None
    version_id: str | None
    doi: str | None
    provider: str
    query_key: str
    observed_at: str
    parser_version: int
    payload_sha256: str
    source_observation_id: str | None
    response_bytes_retained: bool
    result_status: Literal["retained", "not_retained"]
    result_revision_no: int | None


class RevisionFact(ClosedModel):
    version_id: str
    revision_no: int
    revised_at: str
    fields: dict[str, FieldFact]


class PaperTrace(ClosedModel):
    scope: Literal["仅覆盖论文事实；尚未计算完整任务资格"] = (
        "仅覆盖论文事实；尚未计算完整任务资格"
    )
    current: PaperView
    versions: tuple[PaperView, ...]
    revisions: tuple[RevisionFact, ...]
    selections: tuple[SelectionFact, ...]
    observations: tuple[ObservationFact, ...]
    acquisitions: tuple[AcquisitionFact, ...]
    discoveries: tuple["DiscoveryFact", ...] = ()


class FeedFact(ClosedModel):
    feed_id: str
    url: str


class FeedInterpretationFact(ClosedModel):
    parser_version: int
    submitted_at: str
    acquisition_id: str
    observation_id: str | None


class DiscoveryFact(ClosedModel):
    discovery_id: str
    version_id: str
    feed_id: str
    feed_url: str
    entry_id: str
    item_fingerprint: str
    artifact_id: str
    first_seen: str
    last_seen: str
    observation_ids: tuple[str, ...]
    interpretations: tuple[FeedInterpretationFact, ...]
