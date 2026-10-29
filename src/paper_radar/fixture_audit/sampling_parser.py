"""只读取 Feed 身份/类别/日期,不读取摘要成败的确定性 parser v1。"""

from __future__ import annotations

import contextlib
import re
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

from paper_radar.fixture_audit.acquisition_models import SourceRequest
from paper_radar.fixture_audit.acquisition_policy import normalize_request
from paper_radar.fixture_audit.errors import FixtureError, FixtureReason
from paper_radar.fixture_audit.models import Journal
from paper_radar.fixture_audit.sampling_models import (
    FeedCandidate,
    IdentityField,
    ProductionFeedCandidate,
    RawCategory,
)
from paper_radar.papers.doi import normalize_doi
from paper_radar.papers.errors import PaperError
from paper_radar.papers.feed import require_entry_id

DC = "http://purl.org/dc/elements/1.1/"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
ATOM = "http://www.w3.org/2005/Atom"
PRISM = {
    f"http://prismstandard.org/namespaces/basic/{version}/"
    for version in ("1.2", "2.0", "3.0")
}


def _name(tag: str) -> tuple[str, str]:
    if tag.startswith("{"):
        namespace, local = tag[1:].split("}", 1)
        return namespace, local
    return "", tag


def _text(element: ET.Element) -> str:
    return "".join(element.itertext())


def _date_fields(value: str | None) -> tuple[str | None, str]:
    if value is None:
        return None, "unknown"
    try:
        if re.fullmatch(r"\d{4}", value.strip()):
            date(int(value), 1, 1)
            return value.strip(), "year"
        if re.fullmatch(r"\d{4}-\d{2}", value.strip()):
            date.fromisoformat(value.strip() + "-01")
            return value.strip(), "month"
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()):
            return date.fromisoformat(value.strip()).isoformat(), "day"
        try:
            parsed = datetime.fromisoformat(value.strip())
        except ValueError:
            parsed = parsedate_to_datetime(value)
        return parsed.isoformat(), "second"
    except (ValueError, TypeError, OverflowError):
        return None, "unknown"


def _ordered_items(root: ET.Element) -> tuple[str, list[tuple[int, ET.Element]]]:
    namespace, name = _name(root.tag)
    if name == "rss":
        channels = [child for child in root if _name(child.tag)[1] == "channel"]
        if len(channels) != 1:
            raise ValueError("feed_shape")
        items = [child for child in channels[0] if _name(child.tag)[1] == "item"]
        return "channel/item", list(enumerate(items, 1))
    if name == "feed" and namespace in ("", ATOM):
        items = [child for child in root if _name(child.tag)[1] == "entry"]
        return "feed/entry", list(enumerate(items, 1))
    if name == "RDF" and namespace == RDF:
        items = [child for child in root if _name(child.tag)[1] == "item"]
        sequence = root.find(f".//{{{RDF}}}Seq")
        if sequence is None:
            return "RDF/item", list(enumerate(items, 1))
        indexed = {
            item.get(f"{{{RDF}}}about"): (index, item)
            for index, item in enumerate(items, 1)
        }
        resources = [
            child.get(f"{{{RDF}}}resource")
            for child in sequence
            if child.tag == f"{{{RDF}}}li"
        ]
        if (
            len(indexed) != len(items)
            or len(resources) != len(items)
            or set(resources) != set(indexed)
        ):
            raise ValueError("rdf_order")
        return "RDF/Seq/li", [indexed[resource] for resource in resources]
    raise ValueError("feed_shape")


def _candidate(
    journal: Journal,
    position: int,
    physical: int,
    item: ET.Element,
    order: str,
    candidate_type: type[FeedCandidate] = FeedCandidate,
) -> FeedCandidate:
    identities: list[IdentityField] = []
    entry_id = item.get(f"{{{RDF}}}about")
    id_locator = "item@rdf:about" if entry_id is not None else None
    raw_categories: list[RawCategory] = []
    link: str | None = None
    published: str | None = None
    invalid_doi = False
    for child in item:
        namespace, name = _name(child.tag)
        raw = _text(child)
        if name in ("guid", "id") and namespace in ("", ATOM):
            entry_id, id_locator = raw if raw.strip() else None, name
            with contextlib.suppress(PaperError):
                identities.append(
                    IdentityField(locator=name, value=raw, doi=normalize_doi(raw))
                )
        elif name == "doi" and (namespace in PRISM or namespace == ""):
            locator = "prism:doi" if namespace in PRISM else "doi"
            try:
                identities.append(
                    IdentityField(locator=locator, value=raw, doi=normalize_doi(raw))
                )
            except PaperError:
                invalid_doi = True
                identities.append(IdentityField(locator=locator, value=raw))
        elif name == "identifier" and namespace == DC:
            with contextlib.suppress(PaperError):
                identities.append(
                    IdentityField(
                        locator="dc:identifier", value=raw, doi=normalize_doi(raw)
                    )
                )
        if name == "category":
            value = child.get("term") if namespace == ATOM else raw
            raw_categories.append(RawCategory(field="category", value=value or ""))
        elif name == "section" and namespace in PRISM:
            raw_categories.append(RawCategory(field="prism:section", value=raw))
        elif name == "type":
            raw_categories.append(
                RawCategory(
                    field="dc:type" if namespace == DC else "other:type", value=raw
                )
            )
        if (
            name == "link"
            and namespace in ("", ATOM)
            and (namespace != ATOM or child.get("rel", "alternate") == "alternate")
        ):
            link = child.get("href") if namespace == ATOM else raw.strip()
        if published is None and (
            name in ("pubDate", "published", "updated")
            or (name == "date" and namespace == DC)
        ):
            published = raw
    if entry_id is not None:
        try:
            require_entry_id(entry_id)
        except PaperError:
            entry_id, id_locator = None, None
    dois = {item.doi for item in identities if item.doi is not None}
    doi = next(iter(dois)) if len(dois) == 1 else None
    publisher_url = None
    link_reason = None
    if journal == "aies" and link:
        try:
            publisher_url = normalize_request(
                SourceRequest(journal=journal, route="publisher", publisher_url=link)
            ).publisher_url
        except FixtureError:
            link_reason = (
                "disallowed_scheme"
                if link.startswith("http:")
                else "disallowed_destination"
            )
    date_value, precision = _date_fields(published)
    return candidate_type.model_validate(
        {
            "position": position,
            "entry_locator": f"item[{physical}]",
            "order_locator": f"{order}[{position}]",
            "entry_id": entry_id,
            "entry_id_locator": id_locator,
            "doi": doi,
            "identity_fields": tuple(identities),
            "identity_issue": "conflicting_dois"
            if len(dois) > 1
            else "invalid_doi"
            if invalid_doi
            else None,
            "publisher_url": publisher_url,
            "publisher_link_reason": link_reason,
            "raw_categories": tuple(raw_categories),
            "published_raw": published,
            "published_value": date_value,
            "published_precision": precision,
        }
    )


def parse_feed(
    journal: Journal, raw: bytes, decoding: str = "utf-8"
) -> tuple[int, tuple[FeedCandidate, ...]]:
    try:
        if b"\x00" in raw or re.search(rb"<!\s*(?:DOCTYPE|ENTITY)\b", raw, re.I):
            raise ValueError("unsafe_xml")
        text = raw.decode(decoding)
        if re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", text, re.I):
            raise ValueError("unsafe_xml")
        root = ET.fromstring(text)
        order, items = _ordered_items(root)
        return len(items), tuple(
            _candidate(journal, position, physical, item, order)
            for position, (physical, item) in enumerate(items[:50], 1)
        )
    except (ValueError, TypeError, UnicodeError, LookupError, ET.ParseError):
        raise FixtureError(FixtureReason.INVALID_FEED, path="feed") from None


def production_candidates(
    raw: bytes, decoding: str = "utf-8"
) -> tuple[FeedCandidate, ...]:
    """生产全条目解释;复用审计身份、类别、日期及物理定位规则。"""
    # The audit parser remains authoritative for safe XML and feed shape.
    parse_feed("jgr", raw, decoding)
    root = ET.fromstring(raw.decode(decoding))
    order, items = _ordered_items(root)
    return tuple(
        _candidate(
            "jgr",
            position,
            physical,
            item,
            order,
            candidate_type=ProductionFeedCandidate,
        )
        for position, (physical, item) in enumerate(items, 1)
    )
