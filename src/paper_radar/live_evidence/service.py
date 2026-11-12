"""消费者共用的只读账本加载/投影与只能收紧的特权请求。"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Literal

from pydantic import ValidationError, field_validator

from paper_radar.live_evidence.evaluator import AdmissionDecision, evaluate_admission
from paper_radar.live_evidence.evidence import ExecutionBinding
from paper_radar.live_evidence.intents import ProtectedIntentLog
from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerError
from paper_radar.live_evidence.lifecycle import (
    EvidenceLifecycle,
    LifecyclePayload,
    use_for_id,
    use_id_for,
)
from paper_radar.live_evidence.observation import CurrentObservation, RefreshStatus
from paper_radar.live_evidence.reasons import AdmissionReason, ReasonCode
from paper_radar.live_evidence.receipt import UseId, WireModel
from paper_radar.live_evidence.registry import INITIAL_REGISTRY
from paper_radar.live_evidence.time_policy import aware_utc, clock_reason
from paper_radar.live_evidence.types import (
    AdmissionUse,
    BindingComponent,
    Capability,
    Requirement,
)

TIGHTENING_HELPER = "/usr/libexec/paperradar/live-evidence-tighten"


@dataclass(frozen=True, slots=True)
class AdmissionRequest:
    use: AdmissionUse
    binding: ExecutionBinding
    checked_components: frozenset[BindingComponent] = frozenset()
    observation: CurrentObservation | None = None
    refresh: RefreshStatus | None = None
    evidence_after: datetime | None = None


@dataclass(frozen=True, slots=True)
class AdmissionProjection:
    decision: AdmissionDecision
    watermark: datetime | None
    pending_revocation: bool
    sources: tuple[tuple[Capability, str], ...] = ()
    observation: CurrentObservation | None = None
    refresh: RefreshStatus | None = None


class PendingRevocation(WireModel):
    format_version: Literal[1] = 1
    record_type: Literal["revocation"] = "revocation"
    receipt_id: str | None
    use_id: UseId
    capabilities: tuple[Capability, ...]
    recorded_at: datetime

    @field_validator("recorded_at")
    @classmethod
    def valid_time(cls, value: datetime) -> datetime:
        result = aware_utc(value)
        if result is None:
            raise ValueError("evidence_time_invalid")
        return result


def _ledger() -> EvidenceLedger:
    return EvidenceLedger()


def _intents() -> ProtectedIntentLog:
    return ProtectedIntentLog()


def _read_pending(
    ledger: EvidenceLedger | None = None, intents: ProtectedIntentLog | None = None
) -> tuple[PendingRevocation, ...]:
    try:
        return tuple(
            PendingRevocation.model_validate_json(line)
            for line in (intents or _intents()).read(ledger or _ledger())
        )
    except (ValidationError, ValueError) as error:
        if isinstance(error, LedgerError):
            raise
        raise LedgerError("pending_revocation_unavailable") from error


def _append_pending(record: PendingRevocation) -> None:
    _intents().append(record.model_dump_json().encode())


def _persist_or_revoke(record: PendingRevocation, arguments: tuple[str, ...]) -> bool:
    try:
        _append_pending(record)
    except LedgerError:
        if _run_helper(arguments):
            return True  # root事务确已成功;不声称日志已落盘。
        raise
    return _run_helper(arguments)


def unavailable_projection(
    use: AdmissionUse,
    error: LedgerError,
    *,
    pending_revocation: bool = False,
    previous: AdmissionProjection | None = None,
    observation: CurrentObservation | None = None,
    refresh: RefreshStatus | None = None,
) -> AdmissionProjection:
    """来源/观察失败的共享拒绝投影;不接收授予事实。"""
    reason = (
        ReasonCode.CLOCK_ROLLBACK
        if error.category == "clock_rollback"
        else ReasonCode.TIME_INVALID
        if error.category == "evidence_time_invalid"
        else ReasonCode.TIME_FUTURE
        if error.category == "evidence_time_future"
        else ReasonCode.OBSERVATION_UNAVAILABLE
        if error.category == "observation_unavailable"
        else ReasonCode.OBSERVATION_STALE
        if error.category == "observation_stale"
        else ReasonCode.OBSERVATION_DRIFT
        if error.category == "observation_drift"
        else ReasonCode.LEDGER_UNTRUSTED
    )
    extra = (AdmissionReason(reason),) + (
        (AdmissionReason(ReasonCode.PLACEMENT_MISMATCH),)
        if refresh is not None and refresh.placement_mismatch
        else ()
    )
    return AdmissionProjection(
        AdmissionDecision(
            use,
            INITIAL_REGISTRY.version,
            tuple(
                replace(
                    item,
                    reasons=tuple(dict.fromkeys((*item.reasons, *extra))),
                )
                for item in previous.decision.capabilities
            )
            if previous
            else (),
            tuple(
                dict.fromkeys(
                    (
                        *(previous.decision.reasons if previous else ()),
                        *extra,
                    )
                )
            ),
        ),
        previous.watermark if previous else None,
        pending_revocation
        or error.category == "pending_revocation_unavailable"
        or bool(previous and previous.pending_revocation)
        or bool(refresh and refresh.pending_revocation),
        previous.sources if previous else (),
        observation,
        refresh,
    )


def load_admission_evidence(
    request: AdmissionRequest, *, now: datetime
) -> AdmissionProjection:
    """产品只从固定OS来源读取;不接受外来信任根或授予。"""
    return _project_admission(request, now=now, ledger=_ledger(), intents=_intents())


def load_owner_admission_evidence(
    request: AdmissionRequest,
    *,
    now: datetime,
    ledger: EvidenceLedger,
    intents: ProtectedIntentLog,
) -> AdmissionProjection:
    """owner冻结流程复用同一权威;检查root身份但不写任何事实。"""
    ledger._writer()
    return _project_admission(request, now=now, ledger=ledger, intents=intents)


def _project_admission(
    request: AdmissionRequest,
    *,
    now: datetime,
    ledger: EvidenceLedger,
    intents: ProtectedIntentLog,
) -> AdmissionProjection:
    pending: tuple[PendingRevocation, ...] = ()
    try:
        pending = _read_pending(ledger, intents)
        snapshot = EvidenceLifecycle(ledger).snapshot(now=now)
        received_at = dict(snapshot.received_at)
        pending_keys = {
            (identifier, item.use_id, cap)
            for item in pending
            for _use, _cap, identifier in snapshot.sources
            if item.receipt_id == identifier
            or (item.receipt_id is None and received_at[identifier] <= item.recorded_at)
            for cap in item.capabilities
        }
        sources = {(use, cap): identifier for use, cap, identifier in snapshot.sources}
        evidence = tuple(
            replace(item, revoked=True)
            if (
                sources[(item.use, item.capability)],
                f"{item.use.consumer.value}-{item.use.thinking_level.value}",
                item.capability,
            )
            in pending_keys
            else item
            for item in snapshot.evidence
        )
        decision = evaluate_admission(
            INITIAL_REGISTRY,
            request.use,
            evidence,
            binding=request.binding,
            now=now,
            checked_components=request.checked_components,
            ledger_watermark=snapshot.watermark,
        )
        if request.evidence_after is not None:
            cutoff = request.evidence_after
            activated: set[tuple[str, Capability]] = set()
            for event in ledger.audit():
                if event.action == "evidence_activated" and event.recorded_at > cutoff:
                    payload = LifecyclePayload.model_validate_json(event.reason or "")
                    if (
                        payload.use_id == use_id_for(request.use)
                        and payload.registry_version == INITIAL_REGISTRY.version
                    ):
                        activated.update(
                            (event.subject_id, capability)
                            for capability in payload.capabilities
                        )
            stale: set[Capability] = set()
            for item in decision.capabilities:
                source = sources.get((request.use, item.capability))
                claim = item.claim
                if source is None or claim is None:
                    stale.add(item.capability)
                    continue
                record = ledger.show(source)
                if (
                    record.receipt.started_at <= cutoff
                    or record.received_at <= cutoff
                    or claim.evidence_at is None
                    or claim.evidence_at <= cutoff
                    or claim.verified_at is None
                    or claim.verified_at <= cutoff
                    or (source, item.capability) not in activated
                ):
                    stale.add(item.capability)
            reason = AdmissionReason(ReasonCode.OWNER_REVALIDATION)
            decision = replace(
                decision,
                capabilities=tuple(
                    replace(item, reasons=tuple(dict.fromkeys((*item.reasons, reason))))
                    if item.capability in stale
                    else item
                    for item in decision.capabilities
                ),
                reasons=tuple(dict.fromkeys((*decision.reasons, reason)))
                if any(
                    item.capability in stale
                    and item.requirement is Requirement.REQUIRED
                    for item in decision.capabilities
                )
                else decision.reasons,
            )
        selected = tuple(
            (cap, identifier)
            for use, cap, identifier in snapshot.sources
            if use == request.use
        )
        pending_selected = any(
            (
                identifier,
                f"{request.use.consumer.value}-{request.use.thinking_level.value}",
                cap,
            )
            in pending_keys
            for cap, identifier in selected
        )
        return AdmissionProjection(
            decision,
            snapshot.watermark,
            snapshot.pending_revocation or pending_selected,
            selected,
            request.observation,
            request.refresh,
        )
    except LedgerError as error:
        return unavailable_projection(
            request.use, error, pending_revocation=bool(pending)
        )


def _run_helper(arguments: tuple[str, ...]) -> bool:
    try:
        result = subprocess.run(
            ("/usr/bin/sudo", "-n", "--", TIGHTENING_HELPER, *arguments),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin"},
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def request_revocation(
    receipt_id: str,
    use_id: UseId,
    *,
    now: datetime,
    components: frozenset[BindingComponent] | None = None,
    failed_capabilities: frozenset[Capability] = frozenset(),
) -> bool:
    """先持久记录拒绝意图再调用固定 helper;失败不会清除意图。"""
    if not re.fullmatch(r"[0-9a-f]{16}", receipt_id):
        raise LedgerError("receipt_missing")
    use = use_for_id(use_id)
    invalid = clock_reason(now, None)
    if invalid is not None:
        raise LedgerError.clock(invalid)
    # 不依赖账本可读性记录收紧意图;helper 自行在受保护事务内复核时钟。
    affected = tuple(
        rule.capability
        for rule in INITIAL_REGISTRY.requirements_for(use)
        if (
            components is None
            or rule.capability in failed_capabilities
            or bool(rule.dependencies & components)
        )
    )
    return _persist_or_revoke(
        PendingRevocation(
            receipt_id=receipt_id, use_id=use_id, capabilities=affected, recorded_at=now
        ),
        (
            "revoke",
            receipt_id,
            use_id,
            "unknown"
            if components is None
            else ",".join(sorted(component.value for component in components)),
            ",".join(sorted(cap.value for cap in failed_capabilities)),
        ),
    )


def request_use_revocation(use_id: UseId, *, now: datetime) -> bool:
    """无法辨认来源时持久收紧本格当时已有事实;新接收仍须owner显式激活。"""
    use = use_for_id(use_id)
    invalid = clock_reason(now, None)
    if invalid is not None:
        raise LedgerError.clock(invalid)
    return _persist_or_revoke(
        PendingRevocation(
            receipt_id=None,
            use_id=use_id,
            capabilities=tuple(
                rule.capability for rule in INITIAL_REGISTRY.requirements_for(use)
            ),
            recorded_at=now,
        ),
        ("revoke-use", use_id),
    )


def request_time_tick() -> bool:
    """请求固定 helper 用自身 UTC 墙钟推进水位线;调用者不得提供时间。"""
    return _run_helper(("tick",))
