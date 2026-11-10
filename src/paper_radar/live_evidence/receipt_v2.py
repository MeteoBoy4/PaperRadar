"""Live v2 线格式;v1 模型及规范字节保持冻结。"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import Field, TypeAdapter, model_validator

from paper_radar.live_evidence.receipt import (
    ApprovedPlan,
    CaseResult,
    Digest,
    EvidenceReceipt,
    Identifier,
    ReceiptClaim,
    WireModel,
    content_sha256,
)
from paper_radar.live_evidence.types import BindingComponent, Capability, EvidenceStatus

DOMAIN_ID = "live-177"


class ApprovedPlanV2(WireModel):
    plan_id: Identifier
    kind: Literal["site_beta", "model_six_cell"]
    collector_sha256: Digest
    cases: tuple[Identifier, ...] = Field(min_length=1, max_length=128)
    starts_at: datetime
    ends_at: datetime
    max_rounds: int = Field(ge=1, le=20, strict=True)
    stop_on_first_failure: Literal[True]
    format_version: Literal["v2"]
    domain_id: Literal["live-177"]
    max_auth_calls: int = Field(ge=0, le=40, strict=True)
    max_model_calls: int = Field(ge=0, le=40, strict=True)
    max_network_requests: int = Field(ge=0, le=40, strict=True)

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
        if self.max_auth_calls + self.max_network_requests > 40:
            raise ValueError("network_budget_exceeded")
        if self.kind == "site_beta" and (self.max_auth_calls or self.max_model_calls):
            raise ValueError("beta_budget_nonzero")
        return self


class FailureRecordV2(WireModel):
    case_id: Identifier
    reason: Literal[
        "isolation_failed",
        "identity_mismatch",
        "protocol_failed",
        "resource_unavailable",
        "collector_failed",
        "interrupted",
        "sensitive_output",
        "permission_failed",
        "ledger_untrusted",
        "source_untrusted",
    ]


SAFETY_REASONS = frozenset(
    {
        "isolation_failed",
        "identity_mismatch",
        "interrupted",
        "sensitive_output",
        "permission_failed",
        "ledger_untrusted",
        "source_untrusted",
    }
)


class EvidenceReceiptV2(WireModel):
    format_version: Literal["v2"]
    registry_version: Literal["live-admission-v1"]
    plan_id: Identifier
    plan_sha256: Digest
    collector_sha256: Digest
    round_number: int = Field(ge=1, le=20, strict=True)
    started_at: datetime
    completed_at: datetime
    binding: dict[BindingComponent, Digest]
    cases: tuple[CaseResult, ...] = Field(min_length=1, max_length=128)
    failure_history: tuple[FailureRecordV2, ...] = Field(max_length=1)
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

    domain_id: Literal["live-177"]
    round_id: Identifier
    history_sha256: Digest
    prior_receipts: tuple[Digest, ...] = Field(max_length=128)
    reservation_ids: tuple[Identifier, ...] = Field(max_length=120)

    @model_validator(mode="after")
    def valid_round(self) -> Self:
        if any(case.outcome == "failed" for case in self.cases[:-1]):
            raise ValueError("stop_condition_violated")
        if any(case.outcome == "not_assessed" for case in self.cases):
            raise ValueError("case_not_executed")
        if len(set(self.prior_receipts)) != len(self.prior_receipts):
            raise ValueError("history_duplicate")
        if len(set(self.reservation_ids)) != len(self.reservation_ids):
            raise ValueError("reservation_duplicate")
        return self


def validate_v2_plan(
    receipt: EvidenceReceiptV2, plan: ApprovedPlanV2, *, now: datetime
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
    for field, maximum in (
        ("auth_calls", plan.max_auth_calls),
        ("model_calls", plan.max_model_calls),
        ("network_requests", plan.max_network_requests),
    ):
        if sum(getattr(case, field) for case in receipt.cases) > maximum:
            raise ValueError("plan_budget_exceeded")
    if plan.kind == "site_beta":
        allowed = {
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
                claim.capability not in allowed
                or claim.basis != "site_probe"
                or claim.scope != "current_site"
            )
            for claim in receipt.claims
        ):
            raise ValueError("beta_claim_forbidden")


Plan = ApprovedPlan | ApprovedPlanV2
Receipt = EvidenceReceipt | EvidenceReceiptV2
_PLAN_READER: TypeAdapter[Plan] = TypeAdapter(
    Annotated[Plan, Field(discriminator="format_version")]
)
_RECEIPT_READER: TypeAdapter[Receipt] = TypeAdapter(
    Annotated[Receipt, Field(discriminator="format_version")]
)


def read_plan(data: bytes) -> Plan:
    return _PLAN_READER.validate_json(data)


def read_receipt(data: bytes) -> Receipt:
    return _RECEIPT_READER.validate_json(data)
