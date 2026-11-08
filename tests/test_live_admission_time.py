"""跨格聚合的原验证时间只可收紧,不得借格或重新计时。"""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from paper_radar.live_evidence.evidence import CapabilityClaim
from paper_radar.live_evidence.time_policy import earliest_verified_at
from paper_radar.live_evidence.types import EvidenceStatus


def claim(
    at: datetime | None, status: EvidenceStatus = EvidenceStatus.VERIFIED
) -> CapabilityClaim:
    return CapabilityClaim(status, "synthetic aggregation basis", "explicit cells", at)


def test_aggregation_uses_earliest_utc_cell_time_with_microseconds() -> None:
    claims = (
        claim(datetime(2026, 1, 2, 10, 0, 0, 8, tzinfo=UTC)),
        claim(datetime(2026, 1, 1, 20, 0, 0, 7, tzinfo=timezone(timedelta(hours=8)))),
        claim(datetime(2026, 1, 1, 12, 0, 0, 9, tzinfo=UTC)),
    )
    assert earliest_verified_at(
        claims, now=datetime(2026, 1, 3, tzinfo=UTC)
    ) == datetime(2026, 1, 1, 12, 0, 0, 7, tzinfo=UTC)
    assert claims[1].verified_at == datetime(
        2026, 1, 1, 20, 0, 0, 7, tzinfo=timezone(timedelta(hours=8))
    )


@pytest.mark.parametrize("case", ["empty", "unknown", "naive", "future", "naive_now"])
def test_aggregation_rejects_missing_or_invalid_original_verification(
    case: str,
) -> None:
    now = datetime(2026, 1, 3, tzinfo=UTC)
    claims: tuple[CapabilityClaim, ...] = (claim(datetime(2026, 1, 1, tzinfo=UTC)),)
    reason = "aggregate_unverified"
    if case == "empty":
        claims = ()
    elif case == "unknown":
        claims = (claim(None, EvidenceStatus.UNKNOWN),)
    elif case == "naive":
        claims = (claim(datetime(2026, 1, 1)),)
        reason = "evidence_time_invalid"
    elif case == "future":
        claims = (claim(now + timedelta(microseconds=1)),)
        reason = "evidence_time_future"
    else:
        now = now.replace(tzinfo=None)
        reason = "evidence_time_invalid"
    with pytest.raises(ValueError, match=reason):
        earliest_verified_at(claims, now=now)
