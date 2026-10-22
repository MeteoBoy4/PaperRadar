"""Feed 端点身份规则;与来源定位 URL 的无参数边界独立。"""

import hashlib
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from paper_radar.papers.models import ObservationInput

from paper_radar.papers.errors import PaperError, PaperReason
from paper_radar.papers.text_rules import normalize_text

# 格式 1: 原始单条 item 的 SHA-256, 无前缀或规范化。
FEED_ITEM_FINGERPRINT_VERSION = 1


def item_fingerprint(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def normalize_feed_url(value: str) -> str:
    try:
        if not isinstance(value, str) or len(value.encode("utf-8")) > 8192:
            raise ValueError
        if any(c.isspace() or ord(c) < 32 for c in value) or "#" in value:
            raise ValueError
        url = urlsplit(value)
        if (
            url.scheme not in {"http", "https"}
            or not url.hostname
            or url.username is not None
            or url.password is not None
        ):
            raise ValueError
        if url.netloc.endswith(":"):
            raise ValueError
        host = (
            url.netloc[: url.netloc.index("]") + 1]
            if url.netloc.startswith("[")
            else url.netloc.rsplit(":", 1)[0]
            if ":" in url.netloc
            else url.netloc
        )
        host = host.translate(
            str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")
        )
        port = url.port
        authority = (
            host
            if port is None or port == {"http": 80, "https": 443}[url.scheme]
            else f"{host}:{port}"
        )
        # urlunsplit drops a terminal empty '?'; preserve the submitted suffix verbatim.
        suffix = value[value.index("://") + 3 :]
        boundary = min(
            (suffix.find(c) for c in "/?" if c in suffix), default=len(suffix)
        )
        return url.scheme + "://" + authority + suffix[boundary:]
    except (ValueError, UnicodeError, AttributeError):
        raise PaperError(PaperReason.INVALID_FEED_URL, path="feed_url") from None


def require_entry_id(value: object) -> None:
    if value is None:
        raise PaperError(PaperReason.MISSING_ENTRY_ID, path="entry_id")
    if not isinstance(value, str):
        raise PaperError(PaperReason.INVALID_OBSERVATION, path="entry_id")
    if not normalize_text(value):
        raise PaperError(PaperReason.MISSING_ENTRY_ID, path="entry_id")
    if len(value.encode("utf-8")) > 2048:
        raise PaperError(PaperReason.INVALID_OBSERVATION, path="entry_id")


def validate_feed_item(item: "ObservationInput") -> None:
    import re
    from uuid import UUID

    require_entry_id(item.entry_id)
    try:
        if not item.feed_id or str(UUID(item.feed_id)) != item.feed_id:
            raise ValueError
        if item.payload_scope != "single_item" or item.provider or item.query_key:
            raise ValueError
        if (
            len(
                re.findall(
                    rb"<(?:(?:[A-Za-z_][\w.-]*):)?(?:item|entry)\b",
                    item.payload,
                    re.IGNORECASE,
                )
            )
            > 1
        ):
            raise ValueError
        if re.search(
            rb"<(?:(?:[A-Za-z_][\w.-]*):)?(?:rss|feed|rdf)\b",
            item.payload,
            re.IGNORECASE,
        ):
            raise ValueError
    except (ValueError, UnicodeError):
        raise PaperError(PaperReason.INVALID_OBSERVATION, path="feed_item") from None
