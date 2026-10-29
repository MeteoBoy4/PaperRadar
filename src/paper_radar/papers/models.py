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
SourceKind = Literal["manual", "publisher", "registry", "feed"]
RelationSourceKind = Literal["publisher", "registry"]
RelationKind = Literal["is-preprint-of", "has-preprint"]
RelationState = Literal["endpoint_missing", "requires_merge", "effective"]
ConflictKind = Literal[
    "doi_owner_conflict",
    "target_mismatch",
    "version_kind_conflict",
    "entry_doi_changed",
]


class ClosedModel(BaseModel):
    # __init__ 的脱敏 ValueError 遵循 Pydantic union 候选回退协议;应用入口
    # model_validate* 将最终失败转换为 PaperError,不能在候选尝试阶段提前中断。
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

    @classmethod
    def model_validate_json(
        cls,
        json_data: str | bytes | bytearray,
        *,
        strict: bool | None = None,
        extra: Literal["allow", "ignore", "forbid"] | None = None,
        context: Any | None = None,
        by_alias: bool | None = None,
        by_name: bool | None = None,
    ) -> Self:
        try:
            return super().model_validate_json(
                json_data,
                strict=strict,
                extra=extra,
                context=context,
                by_alias=by_alias,
                by_name=by_name,
            )
        except (ValidationError, ValueError):
            raise PaperError(PaperReason.INVALID_OBSERVATION) from None

    @classmethod
    def model_validate_strings(
        cls,
        obj: Any,
        *,
        strict: bool | None = None,
        extra: Literal["allow", "ignore", "forbid"] | None = None,
        context: Any | None = None,
        by_alias: bool | None = None,
        by_name: bool | None = None,
    ) -> Self:
        try:
            return super().model_validate_strings(
                obj,
                strict=strict,
                extra=extra,
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
    """原始输入保留开放 str/object,纯规则负责专用 unsupported_* 原因。

    relations 还需容纳带 raw_* 的 NormalizedRelation,不能由基类重校验。
    """

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
    conflict_id: str | None = None


class FieldFact(ClosedModel):
    acquisition_id: str | None = None
    source_observed_at: str
    source_kind: SourceKind
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
    reason: Literal["initial", "journal_upgrade"]
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
    selection: SelectionFact | None


class ObservationFact(ClosedModel):
    observation_id: str
    version_id: str
    source_kind: SourceKind
    provider: str
    query_key: str
    observed_at: str
    parser_version: int
    artifact_id: str
    payload_sha256: str
    fields: dict[str, FieldFact]


class AcquisitionFact(ClosedModel):
    source_kind: SourceKind
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
    corrections: tuple["ManualCorrectionFact", ...] = ()
    decisions: tuple["CandidateDecision", ...] = ()
    relations: tuple["RelationFact", ...] = ()
    selection_conflicts: tuple[str, ...] = ()
    manual_correction_scope: Literal[
        "人工修正绑定版本，不随 Paper 当前版本升级迁移"
    ] = "人工修正绑定版本，不随 Paper 当前版本升级迁移"


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


class RevisionView(ClosedModel):
    """同一读视图的完整版本修订与适用选择依据。"""

    paper_id: str
    version_id: str
    revision_no: int
    version_kind: VersionKind
    doi: str | None
    fields: dict[str, FieldFact]
    selection: SelectionFact | None


class ManualCorrectionInput(ClosedModel):
    version_id: str
    request_id: str
    actor: str
    reason: str
    fields: dict[str, CandidateInput]


class ManualCorrectionFact(ClosedModel):
    version_id: str
    request_id: str
    actor: str
    reason: str
    acquisition_id: str
    event_no: int


class CandidateDecision(ClosedModel):
    version_id: str
    field_name: str
    candidate_id: str
    acquisition_id: str
    reason: Literal[
        "selected",
        "superseded_interpretation",
        "lower_source_priority",
        "earlier_manual_event",
        "earlier_observation_or_stable_tiebreak",
    ]


class RelationInput(ClosedModel):
    # 原始 kind 由 normalize_relations 判断支持范围,保留 unsupported_relation。
    kind: str
    source_doi: str
    target_doi: str
    locator: str


class RelationFact(ClosedModel):
    relation_id: str
    preprint_doi: str
    journal_doi: str
    preprint_version_id: str | None
    journal_version_id: str | None
    preprint_paper_id: str | None
    journal_paper_id: str | None
    state: RelationState
    acquisition_id: str
    source_kind: RelationSourceKind
    provider: str
    query_key: str
    observed_at: str
    parser_version: int
    artifact_id: str
    locator: str
    assertions: tuple["RelationAssertion", ...] = ()


class NormalizedRelation(RelationInput):
    kind: Literal["is-preprint-of"]
    raw_source_doi: str
    raw_target_doi: str
    raw_kind: RelationKind


class RelationAssertion(ClosedModel):
    response_bytes_retained: bool
    source_kind: RelationSourceKind
    provider: str
    query_key: str
    observed_at: str
    parser_version: int
    payload_sha256: str
    artifact_id: str | None
    locator: str
    acquisition_id: str
    raw_source_doi: str
    raw_target_doi: str
    raw_kind: str


class ConflictView(ClosedModel):
    conflict_id: str
    conflict: ConflictKind
    explanation: str = "强身份冲突，已拒绝业务写入并保留证据"
    artifact_id: str
    payload_sha256: str
    source_kind: str
    feed_id: str | None
    entry_id: str | None
    parser_version: int
    observed_at: str
    raw_doi: str | None
    version_ids: tuple[str, ...]
