"""显式类别闭集和固定成员选择;无网络、数据库或摘要判断。"""

from __future__ import annotations

import hashlib
import json
from html.parser import HTMLParser

from paper_radar.fixture_audit.acquisition_models import Route
from paper_radar.fixture_audit.models import Journal
from paper_radar.fixture_audit.sampling_models import (
    CategoryBasis,
    CategoryDecision,
    CategoryResult,
    FeedCandidate,
    SamplingOutcome,
)


class _PublisherType(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.values: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if (
            tag == "meta"
            and (values.get("name") or "").lower() == "dc.type"
            and values.get("content") is not None
        ):
            self.values.append(values["content"] or "")


def _mapped_value(value: object, *path: str) -> object:
    for field in path:
        if not isinstance(value, dict):
            return None
        value = value.get(field)
    return value


def category_bases(
    journal: Journal,
    route: Route,
    candidate: FeedCandidate,
    *,
    raw: bytes | None = None,
    acquisition_id: str | None = None,
    decoding: str = "utf-8",
) -> tuple[CategoryBasis, ...]:
    values: list[tuple[str, str, str, bool]] = []
    if route == "feed" and journal == "dqkx":
        values = [
            ("item/dc:type", value.value, "article", False)
            for value in candidate.raw_categories
            if value.field == "dc:type"
        ]
    elif route == "publisher" and journal == "dqkx" and raw is not None:
        parser = _PublisherType()
        parser.feed(raw.decode(decoding))
        values = [
            ("meta[name=dc.type]", value, "论文", False) for value in parser.values
        ]
    elif route in ("registry_crossref", "registry_datacite") and raw is not None:
        value = json.loads(raw)
        if route == "registry_crossref":
            label = _mapped_value(value, "message", "type")
            locator, accepted = "message.type", "journal-article"
        else:
            label = _mapped_value(
                value, "data", "attributes", "types", "resourceTypeGeneral"
            )
            locator, accepted = (
                "data.attributes.types.resourceTypeGeneral",
                "JournalArticle",
            )
        if isinstance(label, str):
            values = [(locator, label, accepted, True)]
    result: list[CategoryBasis] = []
    for locator, value, accepted, rejects_other in values:
        decision: CategoryDecision = "unknown"
        if value.strip() == accepted:
            decision = "journal_article"
        elif value.strip() and rejects_other:
            decision = "non_journal_article"
        result.append(
            CategoryBasis(
                route=route,
                locator=locator,
                value=value,
                decision=decision,
                acquisition_id=acquisition_id,
            )
        )
    return tuple(result)


def category_result(
    bases: tuple[CategoryBasis, ...],
) -> CategoryResult:
    decisions = {value.decision for value in bases} - {"unknown"}
    if len(decisions) > 1:
        return "conflict"
    return next(iter(decisions)) if decisions else "unknown"


def member_identity(
    plan_id: str, journal: Journal, position: int, doi: str | None, entry_id: str | None
) -> str:
    return hashlib.sha256(
        json.dumps(
            [plan_id, journal, position, doi, entry_id],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def duplicate_identity(
    doi: str | None, entry_id: str | None, previous: tuple[SamplingOutcome, ...]
) -> bool:
    if doi is not None:
        return any(
            item.doi == doi for item in previous if item.result != "blocked_pending"
        )
    return entry_id is not None and any(
        item.doi is None and item.entry_id == entry_id
        for item in previous
        if item.result != "blocked_pending"
    )
