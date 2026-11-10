"""封印采集器与所有者入口之间的短时现场观察,不赋予证据资格。"""

import hashlib
from datetime import datetime, timedelta
from typing import Literal, Self

from pydantic import model_validator

from paper_radar.live_evidence.evidence import ExecutionBinding
from paper_radar.live_evidence.ledger import EvidenceLedger, LedgerError
from paper_radar.live_evidence.receipt import Digest, WireModel, canonical_bytes
from paper_radar.live_evidence.time_policy import clock_reason
from paper_radar.live_evidence.types import BindingComponent

REFRESH_FILENAME = "observation-refresh.json"


class RefreshStatus(WireModel):
    format_version: Literal[1] = 1
    recorded_at: datetime
    result: Literal[
        "available", "observation_unavailable", "observation_drift", "source_untrusted"
    ]
    snapshot_sha256: Digest | None
    changed_components: tuple[BindingComponent, ...] = ()
    pending_revocation: bool = False
    placement_mismatch: bool = False

    @model_validator(mode="after")
    def valid_status(self) -> Self:
        if self.recorded_at.tzinfo is None:
            raise ValueError("evidence_time_invalid")
        if self.result == "available" and self.snapshot_sha256 is None:
            raise ValueError("source_integrity")
        return self


OBSERVATION_FILENAME = "current-observation.json"
OBSERVATION_MAX_AGE = timedelta(seconds=60)


class CurrentObservation(WireModel):
    observed_at: datetime
    binding: dict[BindingComponent, Digest]
    checked_components: tuple[BindingComponent, ...]

    @model_validator(mode="after")
    def complete_binding(self) -> Self:
        ExecutionBinding(tuple(self.binding.items()))
        if len(set(self.checked_components)) != len(self.checked_components):
            raise ValueError("observation_component_duplicate")
        if self.observed_at.tzinfo is None:
            raise ValueError("evidence_time_invalid")
        return self

    def validate_time(self, *, now: datetime) -> None:
        invalid = clock_reason(now, None)
        if invalid is not None:
            raise LedgerError.clock(invalid)
        if self.observed_at > now:
            raise LedgerError("evidence_time_future")
        if now - self.observed_at > OBSERVATION_MAX_AGE:
            raise LedgerError("observation_stale")

    def validate_current(self, status: RefreshStatus | None, *, now: datetime) -> None:
        """对同一已读快照核刷新绑定和租期,不混用第二次快照。"""
        if status is not None:
            if status.result != "available":
                raise LedgerError(status.result)
            if (
                status.snapshot_sha256
                != hashlib.sha256(canonical_bytes(self)).hexdigest()
            ):
                # 无锁读者可能跨过一次原子发布;配对未知只拒当次。
                raise LedgerError("observation_unavailable")
        self.validate_time(now=now)


class ObservationChanged(LedgerError):
    """保留已确认的影响组件,避免租期或通用拒绝扩大无关撤销。"""

    def __init__(self, components: frozenset[BindingComponent]) -> None:
        super().__init__("observation_changed")
        self.components = components


def read_observation_snapshot(
    ledger: EvidenceLedger, *, now: datetime
) -> CurrentObservation:
    from pydantic import ValidationError

    data = ledger._read_source(ledger.root / "inbox" / OBSERVATION_FILENAME)
    try:
        observation = CurrentObservation.model_validate_json(data)
    except ValidationError as error:
        raise LedgerError("observation_invalid") from error
    if canonical_bytes(observation) != data:
        raise LedgerError("source_integrity")
    return observation


def load_refresh_status(ledger: EvidenceLedger) -> RefreshStatus | None:
    """旧 v1 观察没有刷新记录;新记录一旦存在即校验受保护来源。"""
    source = ledger.root / "inbox" / REFRESH_FILENAME
    try:
        source.lstat()
    except FileNotFoundError:
        if (ledger.root / "observation-refresh-history.jsonl").exists():
            raise LedgerError("source_untrusted") from None
        return None
    data = ledger._read_source(source)
    try:
        status = RefreshStatus.model_validate_json(data)
    except ValueError as error:
        raise LedgerError("source_integrity") from error
    if canonical_bytes(status) != data or status.recorded_at.tzinfo is None:
        raise LedgerError("source_integrity")
    return status


def load_current_observation(
    ledger: EvidenceLedger, *, now: datetime
) -> CurrentObservation:
    observation = read_observation_snapshot(ledger, now=now)
    status = load_refresh_status(ledger)
    # 漂移/失信优先于租期,失败不能因上一份观察尚新而被忽略。
    observation.validate_current(status, now=now)
    return observation
