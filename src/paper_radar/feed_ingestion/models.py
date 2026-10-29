"""生产 Feed 的取得和逐条目公开事实。"""

from typing import Literal

from pydantic import field_validator

from paper_radar.fixture_audit.acquisition_models import HTTPFacts, SourceRequest
from paper_radar.fixture_audit.models import FrozenModel
from paper_radar.fixture_audit.sampling_models import RawCategory
from paper_radar.papers.errors import PaperReason
from paper_radar.papers.models import WriteResult

FEED_PARSER_VERSION = 1
FEED_PARSER_IDENTITY = "jgr-feed-parser-v1"


class FeedItem(FrozenModel):
    position: int
    entry_id: str | None
    doi: str | None
    raw_categories: tuple[RawCategory, ...] = ()
    reason: str | None = None
    result: WriteResult | None = None

    @field_validator("result", mode="before")
    @classmethod
    def decode_result(cls, value: object) -> object:
        # WriteResult uses a strict, custom __init__; restore its enum at the JSON edge.
        if isinstance(value, dict) and value.get("reason") is not None:
            return {**value, "reason": PaperReason(value["reason"])}
        return value


class FeedCheck(FrozenModel):
    check_id: str
    feed_id: str
    request_id: str
    checked_at: str
    request: SourceRequest
    http: HTTPFacts | None = None
    etag: str | None = None
    last_modified: str | None = None
    reason: str = "outcome_unknown"
    status_code: int | None = None
    artifact_id: str | None = None
    prior_check_id: str | None = None
    content_decoding: str | None = None
    parser_version: Literal[1] = 1
    parser_identity: Literal["jgr-feed-parser-v1"] = "jgr-feed-parser-v1"
    items: tuple[FeedItem, ...] = ()
    complete: bool = False
    scope: str = "仅证明取得和论文事实工程路径；真实 JGR 来源假设未验证"


class FeedView(FrozenModel):
    feed_id: str
    url: str
    last_successful_check: str | None = None
    etag: str | None = None
    last_modified: str | None = None
    checks: tuple[FeedCheck, ...] = ()
