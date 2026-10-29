"""按 XML 字节范围保留原 item;文本解释复用审计权威。"""

from dataclasses import dataclass, field
from xml.etree import ElementTree as ET
from xml.parsers import expat

from paper_radar.fixture_audit.abstract_models import (
    ABSTRACT_RULES_VERSION,
    TRUNCATION_RULES_VERSION,
)
from paper_radar.fixture_audit.abstract_parser import parse_material
from paper_radar.fixture_audit.acquisition_models import SourceRequest
from paper_radar.fixture_audit.acquisition_policy import checked_source_url
from paper_radar.fixture_audit.sampling_models import FeedCandidate
from paper_radar.fixture_audit.sampling_parser import production_candidates
from paper_radar.papers.doi import normalize_doi
from paper_radar.papers.errors import PaperError
from paper_radar.papers.models import AbstractValue, CandidateInput


@dataclass(frozen=True)
class ParsedItem:
    candidate: FeedCandidate
    start: int
    end: int
    fields: dict[str, CandidateInput] = field(repr=False)
    reason: str | None = None


def spans(raw: bytes, decoding: str = "utf-8") -> tuple[tuple[int, int], ...]:
    parser = expat.ParserCreate(encoding=decoding, namespace_separator="}")
    depth = 0
    root_name = ""
    start = None
    output = []
    empty = False

    def opened(name: str, attrs: dict[str, str]) -> None:
        nonlocal depth, root_name, start, empty
        depth += 1
        name = name.rsplit("}", 1)[-1]
        if depth == 1:
            root_name = name
        if name in {"item", "entry"} and depth == (3 if root_name == "rss" else 2):
            start = parser.CurrentByteIndex
            quote = None
            index = start
            while index < len(raw):
                char = raw[index]
                if quote is not None:
                    if char == quote:
                        quote = None
                elif char in (34, 39):
                    quote = char
                elif char == 62:
                    break
                index += 1
            empty = raw[start:index].rstrip().endswith(b"/")

    def closed(name: str) -> None:
        nonlocal depth, start
        if start is not None and depth == (3 if root_name == "rss" else 2):
            index = parser.CurrentByteIndex
            # Expat points after an empty-element tag, before ordinary end tags.
            end = index if empty else raw.index(b">", index) + 1
            output.append((start, end))
            start = None
        depth -= 1

    parser.StartElementHandler = opened
    parser.EndElementHandler = closed
    parser.Parse(raw, True)
    return tuple(output)


def landing_doi(url: str) -> str | None:
    """只认受控 Wiley path;query 永不成为 DOI。"""
    from urllib.parse import unquote, urlsplit

    try:
        parts = urlsplit(url)
        if parts.username or parts.password or parts.port not in (None, 443):
            return None
    except ValueError:
        return None
    if (
        parts.query
        or parts.fragment
        or parts.scheme != "https"
        or parts.hostname != "agupubs.onlinelibrary.wiley.com"
    ):
        return None
    for prefix in ("/doi/", "/doi/abs/", "/doi/full/", "/doi/epdf/"):
        if parts.path.startswith(prefix):
            try:
                doi = normalize_doi(unquote(parts.path[len(prefix) :]))
                if (
                    checked_source_url(
                        f"https://{parts.hostname}/doi/{doi}",
                        SourceRequest(journal="jgr", route="publisher", doi=doi),
                    )
                    is None
                ):
                    return doi
            except PaperError:
                pass
    return None


def parse_items(raw: bytes, decoding: str = "utf-8") -> tuple[ParsedItem, ...]:
    candidates = production_candidates(raw, decoding)
    try:
        ranges = spans(raw, decoding)
    except (expat.ExpatError, ValueError):
        from paper_radar.fixture_audit.errors import FixtureError, FixtureReason

        raise FixtureError(FixtureReason.INVALID_FEED, path="feed") from None
    output = []
    tree = ET.fromstring(raw.decode(decoding))
    physical_items = [
        node for node in tree.iter() if node.tag.rsplit("}", 1)[-1] in {"item", "entry"}
    ]
    request = SourceRequest(journal="jgr", route="feed")
    for candidate in candidates:
        physical = int(candidate.entry_locator.split("[")[1].rstrip("]")) - 1
        start, end = ranges[physical]
        reason: str | None = (
            "missing_entry_id"
            if candidate.entry_id is None
            else candidate.identity_issue
        )
        fields: dict[str, CandidateInput] = {}
        node = physical_items[physical]
        links = [
            child.get("href") or "".join(child.itertext()).strip()
            for child in node
            if child.tag.rsplit("}", 1)[-1] == "link"
        ]
        for link in links:
            doi = landing_doi(link)
            if doi is not None:
                if candidate.doi is None and candidate.identity_issue is None:
                    candidate = candidate.model_copy(update={"doi": doi})
                elif candidate.doi != doi:
                    reason = "conflicting_dois"
                fields["source_url"] = CandidateInput(value=link, locator="item/link")
                break
        try:
            parsed, _excluded, texts, _recognized = parse_material(
                request,
                raw,
                decoding=decoding,
                acquisition_id="production-feed-v1",
                entry_locator=candidate.entry_locator,
            )
            for value in parsed:
                text = texts[value.candidate_id]
                fields[value.field] = CandidateInput(
                    value=AbstractValue(
                        text=text,
                        is_truncated=value.suspected_truncated,
                        rule=f"{ABSTRACT_RULES_VERSION}/{TRUNCATION_RULES_VERSION}",
                    )
                    if value.field == "abstract"
                    else text,
                    locator=value.locator.replace(candidate.entry_locator, "item"),
                )
        except (ValueError, IndexError, KeyError, PaperError):
            reason = "invalid_item"
        output.append(ParsedItem(candidate, start, end, fields, reason))
    return tuple(output)
