"""版本化、只含受控摘要的接收线格式;不赋予输入来源权威。"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from paper_radar.live_evidence.types import BindingComponent, Capability, EvidenceStatus

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Identifier = Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]{0,63}$")]
UseId = Literal[
    "boundary-low", "boundary-high", "value-low", "value-high", "read-low", "read-high"
]


class WireModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def canonical_bytes(value: BaseModel) -> bytes:
    return (
        json.dumps(
            value.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()


def content_sha256(value: BaseModel) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


class ApprovedPlan(WireModel):
    format_version: Literal["v1"]
    plan_id: Identifier
    kind: Literal["site_beta", "model_six_cell"]
    collector_sha256: Digest
    cases: tuple[Identifier, ...] = Field(min_length=1, max_length=128)
    starts_at: datetime
    ends_at: datetime
    max_auth_calls: int = Field(ge=0, le=120, strict=True)
    max_model_calls: int = Field(ge=0, le=120, strict=True)
    max_network_requests: int = Field(ge=0, le=120, strict=True)
    max_rounds: int = Field(ge=1, le=20, strict=True)
    stop_on_first_failure: Literal[True]

    @model_validator(mode="after")
    def valid_plan(self) -> Self:
        if (
            self.starts_at.tzinfo is None
            or self.ends_at.tzinfo is None
            or self.starts_at >= self.ends_at
        ):
            raise ValueError("plan_window_invalid")
        if len(self.cases) != len(set(self.cases)):
            raise ValueError("plan_case_duplicate")
        if self.kind == "site_beta" and any(
            (self.max_auth_calls, self.max_model_calls, self.max_network_requests)
        ):
            raise ValueError("beta_budget_nonzero")
        return self


class CaseResult(WireModel):
    case_id: Identifier
    outcome: Literal["passed", "failed", "not_assessed"]
    auth_calls: int = Field(ge=0, strict=True)
    model_calls: int = Field(ge=0, strict=True)
    network_requests: int = Field(ge=0, strict=True)


class FailureRecord(WireModel):
    case_id: Identifier
    reason: Literal[
        "isolation_failed",
        "identity_mismatch",
        "protocol_failed",
        "resource_unavailable",
        "collector_failed",
        "interrupted",
    ]


class ReceiptClaim(WireModel):
    capability: Capability
    use_id: UseId
    case_id: Identifier
    status: EvidenceStatus
    basis: Literal["site_probe", "rpc_probe", "engineering_test", "not_observed"]
    scope: Literal["current_site", "single_case", "not_observed"]
    verified_at: datetime | None
    evidence_at: datetime

    @model_validator(mode="after")
    def valid_claim(self) -> Self:
        if self.evidence_at.tzinfo is None or (
            self.verified_at is not None and self.verified_at.tzinfo is None
        ):
            raise ValueError("evidence_time_invalid")
        if (self.status is EvidenceStatus.VERIFIED) != (self.verified_at is not None):
            raise ValueError("evidence_time_invalid")
        if self.status is EvidenceStatus.VERIFIED and (
            self.basis == "not_observed" or self.scope == "not_observed"
        ):
            raise ValueError("claim_basis_conflict")
        return self


class EvidenceReceipt(WireModel):
    format_version: Literal["v1"]
    registry_version: Literal["live-admission-v1"]
    plan_id: Identifier
    plan_sha256: Digest
    collector_sha256: Digest
    round_number: int = Field(ge=1, le=20, strict=True)
    started_at: datetime
    completed_at: datetime
    binding: dict[BindingComponent, Digest]
    cases: tuple[CaseResult, ...] = Field(min_length=1, max_length=128)
    failure_history: tuple[FailureRecord, ...] = Field(max_length=128)
    claims: tuple[ReceiptClaim, ...] = Field(min_length=1, max_length=210)

    @model_validator(mode="after")
    def consistent_receipt(self) -> Self:
        if set(self.binding) != set(BindingComponent):
            raise ValueError("binding_incomplete")
        if (
            self.started_at.tzinfo is None
            or self.completed_at.tzinfo is None
            or self.started_at > self.completed_at
        ):
            raise ValueError("evidence_time_invalid")
        ids = [case.case_id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("case_duplicate")
        if [failure.case_id for failure in self.failure_history] != [
            case.case_id for case in self.cases if case.outcome == "failed"
        ]:
            raise ValueError("failure_history_inconsistent")
        seen: set[tuple[Capability, str]] = set()
        outcomes = {case.case_id: case.outcome for case in self.cases}
        for claim in self.claims:
            key = (claim.capability, claim.use_id)
            if key in seen:
                raise ValueError("claim_duplicate")
            seen.add(key)
            if claim.case_id not in outcomes or (
                claim.status is EvidenceStatus.VERIFIED
                and outcomes[claim.case_id] != "passed"
            ):
                raise ValueError("claim_case_conflict")
            if not self.started_at <= claim.evidence_at <= self.completed_at or (
                claim.verified_at is not None
                and not self.started_at <= claim.verified_at <= self.completed_at
            ):
                raise ValueError("evidence_time_outside_run")
        return self

    @property
    def receipt_id(self) -> str:
        """激活确认与接收幂等共用的 16 hex 规范内容摘要前缀。"""
        return content_sha256(self)[:16]


def validate_against_plan(
    receipt: EvidenceReceipt, plan: ApprovedPlan, *, now: datetime
) -> None:
    if now.tzinfo is None or receipt.completed_at > now:
        raise ValueError("evidence_time_future")
    if (
        receipt.plan_id != plan.plan_id
        or receipt.plan_sha256 != content_sha256(plan)
        or receipt.collector_sha256 != plan.collector_sha256
    ):
        raise ValueError("plan_mismatch")
    if not plan.starts_at <= receipt.started_at <= receipt.completed_at <= plan.ends_at:
        raise ValueError("plan_window_invalid")
    if receipt.round_number > plan.max_rounds:
        raise ValueError("plan_budget_exceeded")
    case_ids = tuple(case.case_id for case in receipt.cases)
    if case_ids != plan.cases[: len(case_ids)]:
        raise ValueError("plan_case_mismatch")
    if len(case_ids) < len(plan.cases) and receipt.cases[-1].outcome != "failed":
        raise ValueError("plan_case_missing")
    if any(case.outcome == "failed" for case in receipt.cases[:-1]):
        raise ValueError("stop_condition_violated")
    if plan.kind == "site_beta":
        site_capabilities = {
            Capability.AUTH_CACHE_CURRENT,
            Capability.AUTH_CACHE_BASELINE,
            Capability.CWD_ANCESTORS,
            Capability.FILE_ISOLATION,
            Capability.IPV4_EGRESS,
            Capability.ZERO_CORE,
            Capability.APPORT_IDENTITY,
            Capability.SUPPLY_TREE,
            Capability.INSTANCE_TREE,
            Capability.PI_VERSION,
            Capability.LAUNCH_POLICY,
            Capability.ISOLATION_POLICY,
            Capability.HOST_RUNTIME,
        }
        if any(
            claim.status is EvidenceStatus.VERIFIED
            and (
                claim.capability not in site_capabilities
                or claim.basis != "site_probe"
                or claim.scope != "current_site"
            )
            for claim in receipt.claims
        ):
            raise ValueError("beta_claim_forbidden")
    for field, maximum in (
        ("auth_calls", plan.max_auth_calls),
        ("model_calls", plan.max_model_calls),
        ("network_requests", plan.max_network_requests),
    ):
        if sum(getattr(case, field) for case in receipt.cases) > maximum:
            raise ValueError("plan_budget_exceeded")
