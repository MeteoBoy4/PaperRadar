"""查询共同使用的受控损坏与时钟/身份校验。"""

from datetime import UTC, datetime
from uuid import UUID

from paper_radar.papers.errors import PaperError, PaperReason


def corrupt() -> PaperError:
    return PaperError(PaperReason.CORRUPT_REFERENCE)


def _utc(value: str) -> None:
    instant = datetime.fromisoformat(value)
    if (
        instant.tzinfo is None
        or instant.astimezone(UTC).isoformat(timespec="microseconds") != value
    ):
        raise corrupt()


def _uuid(value: str) -> None:
    if str(UUID(value)) != value:
        raise corrupt()
