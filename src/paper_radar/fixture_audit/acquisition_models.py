"""审计计划与安全取得事实;不包含联系人、认证值或响应正文。"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from paper_radar.fixture_audit.models import ConditionalHeaders, FrozenModel, Journal

ACQUISITION_STRATEGY_VERSION = "audit-acquisition-v1"
CHANNELS_VERSION = "audit-channels-v1"
HTTP_RULES_VERSION = "audit-http-v1"
PARSER_VERSION = "audit-parser-v1"
UA_TEMPLATE_VERSION = "identified-public-v1"
SAMPLING_RULES_VERSION = "audit-sampling-v1"
CATEGORY_RULES_VERSION = "audit-category-v1"
Channel = Literal["http", "browser_render", "official_api", "repository"]
Route = Literal["feed", "doi_ra", "registry_crossref", "registry_datacite", "publisher"]
SourceReason = Literal[
    "acquired",
    "not_found",
    "rate_limited",
    "transient_error",
    "invalid_response",
    "provider_incomplete",
    "access_blocked_403",
    "not_applicable_no_doi",
    "agency_unknown",
    "agency_unsupported",
    "identity_mismatch",
    "unrecognized_page_shape",
    "record_without_abstract",
    "outcome_unknown",
    "deferred_retry_after",
    "not_attempted",
    "disallowed_destination",
    "disallowed_scheme",
    "channel_not_installed",
]


def require_utc_timestamp(value: str) -> str:
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() != timedelta(0) or parsed.isoformat() != value:
        raise ValueError("canonical_utc_timestamp_required")
    return value


class CodeIdentity(FrozenModel):
    package_version: str = Field(
        default="0.1.0", pattern=r"^[0-9]+\.[0-9]+\.[0-9]+(?:[A-Za-z0-9.+-]*)$"
    )
    commit: str | None = Field(default=None, pattern=r"^[0-9a-f]{40,64}$")
    dirty: bool | None = None
    basis: Literal["installed", "synthetic"] = "installed"


class FeedEndpoint(FrozenModel):
    journal: Journal
    url: str


class AuditPlan(FrozenModel):
    plan_id: str
    plan_key: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$")
    target_count: int = Field(ge=5, le=10)
    endpoints: tuple[FeedEndpoint, ...]
    code_identity: CodeIdentity
    acquisition_strategy_version: str = ACQUISITION_STRATEGY_VERSION
    channels_version: str = CHANNELS_VERSION
    http_rules_version: str = HTTP_RULES_VERSION
    parser_version: str = PARSER_VERSION
    sampling_rules_version: str = SAMPLING_RULES_VERSION
    category_rules_version: str = CATEGORY_RULES_VERSION
    ua_template_version: str = UA_TEMPLATE_VERSION
    abstract_rules_version: str = "audit-abstract-v1"
    truncation_rules_version: str = "audit-truncation-v1"
    matrix_rules_version: str = "audit-matrix-v1"
    created_at: str

    @field_validator("created_at")
    @classmethod
    def valid_timestamp(cls, value: str) -> str:
        return require_utc_timestamp(value)


class SourceRequest(FrozenModel):
    journal: Journal
    route: Route
    doi: str | None = None
    publisher_url: str | None = None
    channel: Channel = "http"
    acquisition_strategy_version: str = ACQUISITION_STRATEGY_VERSION
    conditional_headers: ConditionalHeaders = Field(default_factory=ConditionalHeaders)
    access_basis: Literal["open"] = "open"
    credential_class: None = None
    request_header_class: Literal["identified-public-v1"] = "identified-public-v1"


class HTTPRequestFact(FrozenModel):
    url: str
    round_no: int = Field(ge=1, le=2)
    redirect_no: int = Field(ge=0, le=5)
    status_code: int | None = Field(default=None, ge=100, le=599)
    reason: SourceReason
    wait_seconds: float = Field(default=0.0, ge=0.0)


class HTTPFacts(FrozenModel):
    reason: SourceReason
    requests: tuple[HTTPRequestFact, ...] = ()
    round_count: int = Field(default=0, ge=0, le=2)
    retry_count: int = Field(default=0, ge=0, le=1)
    redirect_count: int = Field(default=0, ge=0, le=10)
    wait_seconds: float = Field(default=0.0, ge=0.0)
    content_type: str | None = None
    charset: str | None = None
    decoding: str | None = None
    status_code: int | None = None
    minimum_host_interval_seconds: Literal[1] = 1

    @model_validator(mode="after")
    def coherent_counts(self) -> Self:
        rounds = max((item.round_no for item in self.requests), default=0)
        redirects = 0
        previous: HTTPRequestFact | None = None
        for item in self.requests:
            if previous is None or previous.round_no != item.round_no:
                if item.redirect_no != 0 or (
                    previous is not None and item.round_no != previous.round_no + 1
                ):
                    raise ValueError("http_rounds")
            elif (
                item.redirect_no != previous.redirect_no + 1
                or previous.status_code not in (301, 302, 303, 307, 308)
            ):
                raise ValueError("http_redirects")
            else:
                redirects += 1
            previous = item
        if (
            self.round_count != rounds
            or self.retry_count != max(0, rounds - 1)
            or self.redirect_count != redirects
        ):
            raise ValueError("http_counts")
        if self.requests and (
            self.status_code != self.requests[-1].status_code
            or self.reason != self.requests[-1].reason
        ):
            raise ValueError("http_terminal")
        return self

    @property
    def physical_requests(self) -> int:
        return len(self.requests)


class SourceSettlement(FrozenModel):
    reason: SourceReason
    http: HTTPFacts | None = None
    artifact_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    payload_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    size_bytes: int | None = Field(default=None, ge=0)
    identity_doi: str | None = None
    agency: str | None = Field(default=None, pattern=r"^[A-Za-z][A-Za-z0-9 ._-]{0,63}$")
    reused_prior: bool = False
    content_decoding: str | None = Field(default=None, pattern=r"^[a-z0-9._-]{1,40}$")
    settled_at: str

    @field_validator("settled_at")
    @classmethod
    def valid_settlement_time(cls, value: str) -> str:
        return require_utc_timestamp(value)


class RouteExecution(FrozenModel):
    execution_id: str
    plan_id: str
    request_key: str
    request: SourceRequest
    started_at: str
    previous_execution_id: str | None = None
    settlement: SourceSettlement | None = None

    @field_validator("started_at")
    @classmethod
    def valid_start_time(cls, value: str) -> str:
        return require_utc_timestamp(value)

    @property
    def reason(self) -> SourceReason | None:
        return self.settlement.reason if self.settlement else None

    @property
    def physical_requests(self) -> int | None:
        if self.settlement is None or (
            self.settlement.reason == "outcome_unknown" and self.settlement.http is None
        ):
            return None
        return self.settlement.http.physical_requests if self.settlement.http else 0

    @property
    def is_failure(self) -> bool:
        return self.reason in {
            "not_found",
            "rate_limited",
            "transient_error",
            "invalid_response",
            "provider_incomplete",
            "access_blocked_403",
            "identity_mismatch",
            "unrecognized_page_shape",
            "disallowed_destination",
            "disallowed_scheme",
        }


class AuditView(FrozenModel):
    plan: AuditPlan
    executions: tuple[RouteExecution, ...] = ()


def identity_json(value: FrozenModel) -> str:
    return value.model_dump_json()


def identity_sha256(value: FrozenModel) -> str:
    return hashlib.sha256(identity_json(value).encode()).hexdigest()


def _check_model_shape(value: object, seen: set[int]) -> None:
    if isinstance(value, FrozenModel):
        if id(value) in seen or set(value.__dict__) != set(type(value).model_fields):
            raise ValueError("model_shape")
        seen.add(id(value))
        for item in value.__dict__.values():
            _check_model_shape(item, seen)
        seen.remove(id(value))
    elif isinstance(value, (tuple, list)):
        if id(value) in seen:
            raise ValueError("model_shape")
        seen.add(id(value))
        for item in value:
            _check_model_shape(item, seen)
        seen.remove(id(value))


def revalidate_model[Model: FrozenModel](value: Model, expected: type[Model]) -> Model:
    """model_copy 不是输入准入;warnings=error 保证不先输出原值。"""
    if type(value) is not expected:
        raise ValueError("model_type")
    _check_model_shape(value, set())
    return expected.model_validate_json(value.model_dump_json(warnings="error"))
