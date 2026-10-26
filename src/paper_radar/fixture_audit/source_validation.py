"""材料保留资格的最小确定性识别;摘要和类别解释由后续 parser 交付。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from xml.etree import ElementTree

from paper_radar.fixture_audit.acquisition_models import SourceReason, SourceRequest
from paper_radar.papers.doi import normalize_doi
from paper_radar.papers.errors import PaperError


@dataclass(frozen=True)
class SourceInspection:
    reason: SourceReason
    retain: bool = False
    identity_doi: str | None = None
    agency: str | None = None


class _IdentityMetadata(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.dois: list[str] = []
        self.challenge = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if (
            tag == "meta"
            and (values.get("name") or "").lower()
            in {"citation_doi", "dc.identifier.doi"}
            and values.get("content")
        ):
            self.dois.append(values["content"] or "")
        if tag == "form" and values.get("id") in {
            "challenge-form",
            "captcha-form",
            "login-form",
            "subscription-form",
        }:
            self.challenge = True


def inspect_source(
    request: SourceRequest, body: bytes, decoding: str = "utf-8"
) -> SourceInspection:
    try:
        if not body:
            return SourceInspection("provider_incomplete")
        if request.route == "feed":
            if b"\x00" in body or re.search(rb"<!\s*(?:DOCTYPE|ENTITY)\b", body, re.I):
                return SourceInspection("invalid_response")
            decoded = body.decode(decoding)
            if re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", decoded, re.I):
                return SourceInspection("invalid_response")
            root = ElementTree.fromstring(decoded)
            name = root.tag.rsplit("}", 1)[-1]
            child_names = {item.tag.rsplit("}", 1)[-1] for item in root}
            if not (
                (name == "rss" and "channel" in child_names)
                or name == "feed"
                or (name == "RDF" and "channel" in child_names)
            ):
                return SourceInspection("invalid_response")
            return SourceInspection("acquired", retain=True)
        if request.route == "publisher":
            parser = _IdentityMetadata()
            parser.feed(body.decode(decoding))
            if parser.challenge:
                return SourceInspection("access_blocked_403")
            if not parser.dois:
                return SourceInspection("unrecognized_page_shape")
            identities = {normalize_doi(value) for value in parser.dois}
            if len(identities) != 1 or (
                request.doi is not None and normalize_doi(request.doi) not in identities
            ):
                return SourceInspection("identity_mismatch")
            return SourceInspection(
                "acquired", retain=True, identity_doi=next(iter(identities))
            )
        value = json.loads(body)
        expected = normalize_doi(request.doi or "")
        if request.route == "doi_ra":
            if (
                not isinstance(value, list)
                or len(value) != 1
                or not isinstance(value[0], dict)
            ):
                return SourceInspection("agency_unknown")
            item = value[0]
            if normalize_doi(item.get("DOI", "")) != expected:
                return SourceInspection("identity_mismatch")
            agency = item.get("RA")
            if (
                not isinstance(agency, str)
                or re.fullmatch(r"[A-Za-z][A-Za-z0-9 ._-]{0,63}", agency) is None
            ):
                return SourceInspection("agency_unknown")
            return SourceInspection(
                "acquired"
                if agency in {"Crossref", "DataCite"}
                else "agency_unsupported",
                agency=agency,
            )
        if request.route == "registry_crossref":
            message = value.get("message", {})
            identity = normalize_doi(message.get("DOI", ""))
        else:
            data = value.get("data", {})
            attributes = data.get("attributes", {})
            identity = normalize_doi(attributes.get("doi") or data.get("id", ""))
            if data.get("id") and normalize_doi(data["id"]) != identity:
                return SourceInspection("identity_mismatch")
        if identity != expected:
            return SourceInspection("identity_mismatch")
        return SourceInspection("acquired", retain=True, identity_doi=identity)
    except (
        ValueError,
        TypeError,
        AttributeError,
        LookupError,
        UnicodeError,
        ElementTree.ParseError,
        PaperError,
    ):
        return SourceInspection("invalid_response")
