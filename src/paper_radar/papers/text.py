"""规范文本与严格候选输入规则 v1。"""

import re
from datetime import date, timedelta
from urllib.parse import urlsplit

from pydantic import ValidationError

from paper_radar.papers.errors import PaperError, PaperReason
from paper_radar.papers.models import (
    AbstractValue,
    CandidateInput,
    DateValue,
    ObservationInput,
)

FIELDS = frozenset(
    {
        "title",
        "abstract",
        "authors",
        "journal",
        "volume",
        "issue",
        "pages",
        "online_date",
        "print_date",
        "source_url",
    }
)
_MARKUP = re.compile(
    r"<!--|<![A-Za-z]|<\?|</?[A-Za-z][A-Za-z0-9:_-]*(?:\s+[^<>]*|\s*/?)>"
)


def normalize_text(value: str) -> str:
    try:
        value.encode("utf-8")
    except UnicodeError:
        raise PaperError(PaperReason.INVALID_TEXT, path="fields") from None
    if _MARKUP.search(value):
        raise PaperError(PaperReason.INVALID_TEXT, path="fields")
    return value.replace("\r\n", "\n").replace("\r", "\n").strip()


def require_public_url(value: str, *, required: bool = False) -> None:
    try:
        url = urlsplit(value)
        if not required and url.scheme not in {"http", "https"}:
            return
        if (
            url.scheme not in {"http", "https"}
            or not url.hostname
            or url.username is not None
            or url.password is not None
            or "?" in value
            or "#" in value
            or any(c.isspace() or ord(c) < 32 for c in value)
        ):
            raise ValueError
        _ = url.port
    except ValueError:
        raise PaperError(PaperReason.INVALID_OBSERVATION, path="source_url") from None


def parse_observation(value: object) -> ObservationInput:
    if isinstance(value, dict):
        fields = value.get("fields")
        if isinstance(fields, dict) and set(fields) - FIELDS:
            raise PaperError(PaperReason.UNSUPPORTED_FIELD, path="fields")
    try:
        item = ObservationInput.model_validate(value)
    except ValidationError:
        raise PaperError(PaperReason.INVALID_OBSERVATION) from None
    if item.scheme != "doi":
        raise PaperError(PaperReason.UNSUPPORTED_SCHEME, path="scheme")
    if item.source_kind not in {"publisher", "feed"}:
        raise PaperError(PaperReason.UNSUPPORTED_SOURCE, path="source_kind")
    if item.relations:
        raise PaperError(PaperReason.UNSUPPORTED_RELATION, path="relations")
    if set(item.fields) - FIELDS:
        raise PaperError(PaperReason.UNSUPPORTED_FIELD, path="fields")
    if (
        not item.payload
        or len(item.payload) > 8 * 1024 * 1024
        or item.observed_at.utcoffset() != timedelta(0)
        or item.observed_at.tzinfo is None
        or item.parser_version < 1
        or bool(item.target_paper_id) != bool(item.target_version_id)
    ):
        raise PaperError(PaperReason.INVALID_OBSERVATION)
    if item.source_kind == "feed":
        from paper_radar.papers.feed import validate_feed_item

        validate_feed_item(item)
        return item
    if (
        item.doi is None
        or item.feed_id is not None
        or item.entry_id is not None
        or item.payload_scope is not None
    ):
        raise PaperError(PaperReason.INVALID_OBSERVATION)
    for key in (item.provider, item.query_key):
        require_public_url(key)
        if not normalize_text(key) or len(key.encode("utf-8")) > 2048:
            raise PaperError(PaperReason.INVALID_OBSERVATION)
    return item


def normalize_fields(fields: dict[str, CandidateInput]) -> dict[str, CandidateInput]:
    if set(fields) - FIELDS:
        raise PaperError(PaperReason.UNSUPPORTED_FIELD, path="fields")
    result = {}
    for name, candidate in fields.items():
        if (
            not normalize_text(candidate.locator)
            or len(candidate.locator.encode("utf-8")) > 2048
        ):
            raise PaperError(PaperReason.INVALID_OBSERVATION, path="fields.locator")
        require_public_url(candidate.locator)
        value = candidate.value
        if name == "abstract" and isinstance(value, AbstractValue):
            text = normalize_text(value.text)
            if not normalize_text(value.rule):
                raise PaperError(
                    PaperReason.INVALID_OBSERVATION, path="fields.abstract.rule"
                )
            if text:
                result[name] = candidate.model_copy(
                    update={"value": value.model_copy(update={"text": text})}
                )
        elif name == "authors" and isinstance(value, tuple):
            authors = tuple(normalize_text(author) for author in value)
            if any(not author for author in authors):
                raise PaperError(PaperReason.INVALID_OBSERVATION, path="fields.authors")
            if authors:
                result[name] = candidate.model_copy(update={"value": authors})
        elif name in {"online_date", "print_date"} and isinstance(value, DateValue):
            pattern, suffix = {
                "year": (r"[0-9]{4}", "-01-01"),
                "month": (r"[0-9]{4}-[0-9]{2}", "-01"),
                "day": (r"[0-9]{4}-[0-9]{2}-[0-9]{2}", ""),
            }[value.precision]
            try:
                if re.fullmatch(pattern, value.value) is None:
                    raise ValueError
                date.fromisoformat(value.value + suffix)
            except ValueError:
                raise PaperError(
                    PaperReason.INVALID_OBSERVATION, path="fields.date"
                ) from None
            result[name] = candidate
        elif name not in {
            "abstract",
            "authors",
            "online_date",
            "print_date",
        } and isinstance(value, str):
            text = normalize_text(value)
            if not text:
                continue
            if name == "source_url":
                require_public_url(text, required=True)
            if text:
                result[name] = candidate.model_copy(update={"value": text})
        else:
            raise PaperError(PaperReason.INVALID_OBSERVATION, path="fields." + name)
    return result
