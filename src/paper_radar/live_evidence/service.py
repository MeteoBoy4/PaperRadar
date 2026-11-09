"""消费者共用的只读账本加载/投影与只能收紧的特权请求。"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from paper_radar.live_evidence.evaluator import AdmissionDecision, evaluate_admission
from paper_radar.live_evidence.evidence import ExecutionBinding
from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerError
from paper_radar.live_evidence.lifecycle import EvidenceLifecycle, use_for_id
from paper_radar.live_evidence.reasons import AdmissionReason, ReasonCode
from paper_radar.live_evidence.receipt import UseId, WireModel
from paper_radar.live_evidence.registry import INITIAL_REGISTRY
from paper_radar.live_evidence.time_policy import clock_reason
from paper_radar.live_evidence.types import AdmissionUse, BindingComponent, Capability

TIGHTENING_HELPER = "/usr/libexec/paperradar/live-evidence-tighten"


@dataclass(frozen=True, slots=True)
class AdmissionRequest:
    use: AdmissionUse
    binding: ExecutionBinding
    checked_components: frozenset[BindingComponent] = frozenset()


@dataclass(frozen=True, slots=True)
class AdmissionProjection:
    decision: AdmissionDecision
    watermark: datetime | None
    pending_revocation: bool
    sources: tuple[tuple[Capability, str], ...] = ()


class PendingRevocation(WireModel):
    receipt_id: str
    use_id: UseId
    capabilities: tuple[Capability, ...]
    recorded_at: datetime


def _ledger() -> EvidenceLedger:
    return EvidenceLedger()


def _pending_path() -> Path:
    # 用户态只追加收紧意图;不读取凭据、配置通过声明或业务预算。
    return (
        Path.home() / ".local" / "state" / "paperradar" / "live-evidence-pending.jsonl"
    )


def _read_pending() -> tuple[PendingRevocation, ...]:
    path = _pending_path()
    try:
        if not os.path.lexists(path):
            return ()
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024 * 1024:
            raise LedgerError("pending_revocation_unavailable")
        return tuple(
            PendingRevocation.model_validate_json(line)
            for line in path.read_bytes().splitlines()
        )
    except (OSError, ValidationError, ValueError) as error:
        if isinstance(error, LedgerError):
            raise
        raise LedgerError("pending_revocation_unavailable") from error


def _append_pending(record: PendingRevocation) -> None:
    path = _pending_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(
            path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600
        )
        with os.fdopen(fd, "ab") as stream:
            stream.write(record.model_dump_json().encode() + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as error:
        raise LedgerError("pending_revocation_unavailable") from error


def load_admission_evidence(
    request: AdmissionRequest, *, now: datetime
) -> AdmissionProjection:
    """不接收外来证据/信任根;普通 request 只能描述本次身份与观察范围。"""
    pending: tuple[PendingRevocation, ...] = ()
    try:
        pending = _read_pending()
        snapshot = EvidenceLifecycle(_ledger()).snapshot(now=now)
        pending_keys = {
            (item.receipt_id, item.use_id, cap)
            for item in pending
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
        )
    except LedgerError as error:
        reason = (
            ReasonCode.CLOCK_ROLLBACK
            if error.category == "clock_rollback"
            else ReasonCode.TIME_INVALID
            if error.category == "evidence_time_invalid"
            else ReasonCode.LEDGER_UNTRUSTED
        )
        decision = AdmissionDecision(
            request.use, INITIAL_REGISTRY.version, (), (AdmissionReason(reason),)
        )
        return AdmissionProjection(
            decision,
            None,
            bool(pending) or error.category == "pending_revocation_unavailable",
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
    _append_pending(
        PendingRevocation(
            receipt_id=receipt_id, use_id=use_id, capabilities=affected, recorded_at=now
        )
    )
    return _run_helper(
        (
            "revoke",
            receipt_id,
            use_id,
            "unknown"
            if components is None
            else ",".join(sorted(component.value for component in components)),
            ",".join(sorted(cap.value for cap in failed_capabilities)),
        )
    )


def request_time_tick() -> bool:
    """请求固定 helper 用自身 UTC 墙钟推进水位线;调用者不得提供时间。"""
    return _run_helper(("tick",))
