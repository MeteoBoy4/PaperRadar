"""显式 UTC 时间校验与原始证据时间;不读取墙钟。"""

from datetime import UTC, datetime

from paper_radar.live_evidence.evidence import CapabilityClaim
from paper_radar.live_evidence.reasons import ReasonCode
from paper_radar.live_evidence.types import EvidenceStatus


def aware_utc(value: datetime) -> datetime | None:
    if value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(UTC)


def clock_reason(now: datetime, watermark: datetime | None) -> ReasonCode | None:
    current = aware_utc(now)
    if current is None:
        return ReasonCode.TIME_INVALID
    if watermark is not None:
        lower_bound = aware_utc(watermark)
        if lower_bound is None:
            return ReasonCode.TIME_INVALID
        if current < lower_bound:
            return ReasonCode.CLOCK_ROLLBACK
    return None


def claim_time_reason(claim: CapabilityClaim, now: datetime) -> ReasonCode | None:
    if (claim.status is EvidenceStatus.VERIFIED) != (claim.verified_at is not None):
        return ReasonCode.TIME_INVALID
    for value in (claim.verified_at, claim.evidence_at):
        if value is not None:
            timestamp = aware_utc(value)
            if timestamp is None:
                return ReasonCode.TIME_INVALID
            if timestamp > now:
                return ReasonCode.TIME_FUTURE
    return None


def earliest_verified_at(
    claims: tuple[CapabilityClaim, ...], *, now: datetime
) -> datetime:
    """聚合主张取已明确给定各格中最早时点;不生成跨格执行资格。"""
    invalid_clock = clock_reason(now, None)
    if invalid_clock is not None:
        raise ValueError(invalid_clock.value)
    if not claims or any(
        claim.status is not EvidenceStatus.VERIFIED for claim in claims
    ):
        raise ValueError("aggregate_unverified")
    timestamps: list[datetime] = []
    for claim in claims:
        error = claim_time_reason(claim, now)
        if error is not None:
            raise ValueError(error.value)
        assert claim.verified_at is not None
        timestamp = aware_utc(claim.verified_at)
        assert timestamp is not None
        timestamps.append(timestamp)
    return min(timestamps)
