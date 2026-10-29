"""首发Feed端点唯一声明;数据库URL/UUID仍是实际发现身份。"""

from dataclasses import dataclass
from typing import Literal

Journal = Literal["aies", "jgr", "qjrms", "dqkx"]


@dataclass(frozen=True)
class FeedSubscription:
    journal: Journal
    url: str


FEED_SUBSCRIPTIONS = (
    FeedSubscription(
        "aies",
        "https://journals.ametsoc.org/journalissuetocrss/journals/aies/aies-overview.xml",
    ),
    FeedSubscription(
        "jgr",
        "https://agupubs.onlinelibrary.wiley.com/action/showFeed?jc=21698996&type=etoc&feed=rss",
    ),
    FeedSubscription(
        "qjrms", "https://rmets.onlinelibrary.wiley.com/feed/1477870x/most-recent"
    ),
    FeedSubscription("dqkx", "https://www.iapjournals.ac.cn/dqkx/rss/current.xml"),
)


def endpoint(journal: Journal) -> str:
    """已裁决首发端点;不创建数据库身份或批准订阅。"""
    return next(value.url for value in FEED_SUBSCRIPTIONS if value.journal == journal)
