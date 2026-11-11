"""认证进程唯一可公开投影;不接受凭据、自由文本或秘密摘要。"""

from datetime import datetime, timedelta
from typing import Annotated, Literal, Self

from pydantic import Field, StrictBool, model_validator

from paper_radar.live_evidence.receipt import WireModel

AuthFact = StrictBool | Literal["unknown"]
AUTH_SOURCE_ID = "pi-auth-refresh-1.4.0-v1"
AUTH_HELPER_NAME = "auth_helper.mjs"


class AuthRefreshMetadata(WireModel):
    format_version: Literal[1]
    source_id: Literal["pi-auth-refresh-1.4.0-v1"]
    pid: Annotated[int, Field(gt=0, strict=True)]
    started_at: datetime
    completed_at: datetime
    refresh_at: datetime | None = None
    need_refresh: AuthFact = "unknown"
    was_expired_by_pi: AuthFact = "unknown"
    refresh_called: AuthFact = "unknown"
    refresh_succeeded: AuthFact = "unknown"
    store_committed: AuthFact = "unknown"

    @model_validator(mode="after")
    def valid(self) -> Self:
        dates = (self.started_at, self.completed_at, self.refresh_at)
        if any(
            value is not None and value.utcoffset() != timedelta(0) for value in dates
        ):
            raise ValueError("auth_metadata_invalid")
        if self.completed_at < self.started_at or (
            self.refresh_at is not None
            and not self.started_at <= self.refresh_at <= self.completed_at
        ):
            raise ValueError("auth_metadata_invalid")
        if self.refresh_called is True:
            if self.need_refresh is not True or self.refresh_at is None:
                raise ValueError("auth_metadata_invalid")
        elif any(
            (
                self.refresh_at is not None,
                self.need_refresh != "unknown",
                self.was_expired_by_pi != "unknown",
                self.refresh_succeeded != "unknown",
                self.store_committed != "unknown",
            )
        ):
            raise ValueError("auth_metadata_invalid")
        if self.store_committed is True and self.refresh_succeeded is not True:
            raise ValueError("auth_metadata_invalid")
        return self


def parse_auth_metadata(raw: bytes, *, pid: int) -> AuthRefreshMetadata:
    try:
        if not raw or len(raw) > 2048:
            raise ValueError("auth_metadata_invalid")
        result = AuthRefreshMetadata.model_validate_json(raw)
        if result.pid != pid:
            raise ValueError("auth_metadata_invalid")
        return result
    except ValueError:
        raise ValueError("auth_metadata_invalid") from None
