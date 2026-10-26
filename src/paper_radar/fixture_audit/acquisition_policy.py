"""A10 固定路由与计划身份;不读取配置、凭据或验收脚本。"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from paper_radar.fixture_audit.acquisition_models import FeedEndpoint
from paper_radar.fixture_audit.errors import FixtureError, FixtureReason

FEED_ENDPOINTS = (
    FeedEndpoint(
        journal="aies",
        url="https://journals.ametsoc.org/journalissuetocrss/journals/aies/aies-overview.xml",
    ),
    FeedEndpoint(
        journal="jgr",
        url="https://agupubs.onlinelibrary.wiley.com/action/showFeed?jc=21698996&type=etoc&feed=rss",
    ),
    FeedEndpoint(
        journal="qjrms",
        url="https://rmets.onlinelibrary.wiley.com/feed/1477870x/most-recent",
    ),
    FeedEndpoint(
        journal="dqkx", url="https://www.iapjournals.ac.cn/dqkx/rss/current.xml"
    ),
)


def validate_contact(value: str | None) -> str:
    if (
        not isinstance(value, str)
        or len(value) > 254
        or re.fullmatch(
            r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,63}",
            value,
        )
        is None
    ):
        raise FixtureError(FixtureReason.INVALID_CONTACT, path="contact_email")
    return value


def request_url(request: SourceRequest) -> str:
    from urllib.parse import quote

    from paper_radar.papers.doi import normalize_doi
    from paper_radar.papers.errors import PaperError

    if request.route == "feed":
        return next(
            item.url for item in FEED_ENDPOINTS if item.journal == request.journal
        )
    if request.route == "publisher" and request.journal == "aies":
        if request.publisher_url is None:
            raise FixtureError(FixtureReason.INVALID_REQUEST, path="publisher_url")
        return request.publisher_url
    if request.doi is None:
        raise FixtureError(FixtureReason.INVALID_REQUEST, path="doi")
    try:
        doi = quote(normalize_doi(request.doi), safe="/")
    except PaperError:
        raise FixtureError(FixtureReason.INVALID_REQUEST, path="doi") from None
    if request.route == "doi_ra":
        return f"https://doi.org/doiRA/{doi}"
    if request.route == "registry_crossref":
        return f"https://api.crossref.org/works/{doi}"
    if request.route == "registry_datacite":
        return f"https://api.datacite.org/dois/{doi}"
    hosts = {
        "jgr": "agupubs.onlinelibrary.wiley.com/doi/",
        "qjrms": "rmets.onlinelibrary.wiley.com/doi/",
        "dqkx": "www.iapjournals.ac.cn/dqkx/article/doi/",
    }
    return f"https://{hosts[request.journal]}{doi}"


def checked_source_url(url: str, request: SourceRequest) -> SourceReason | None:
    from urllib.parse import unquote, urlsplit

    from paper_radar.papers.errors import PaperError
    from paper_radar.papers.feed import normalize_feed_url

    try:
        value = urlsplit(url)
        if value.scheme != "https":
            return "disallowed_scheme"
        if (
            value.username
            or value.password
            or value.port not in (None, 443)
            or value.fragment
        ):
            return "disallowed_destination"
        if (
            any(part in {".", ".."} for part in unquote(value.path).split("/"))
            or "%25" in value.path.lower()
        ):
            return "disallowed_destination"
        if request.route == "publisher" and request.journal == "aies":
            if (
                value.hostname != "journals.ametsoc.org"
                or value.query
                or not re.fullmatch(
                    r"/view/journals/aies/[A-Za-z0-9_./-]+\.xml", unquote(value.path)
                )
            ):
                return "disallowed_destination"
            return None
        if request.route == "feed":
            return (
                None
                if normalize_feed_url(url) == request_url(request)
                else "disallowed_destination"
            )
        if "?" in url:
            return "disallowed_destination"
        expected = urlsplit(request_url(request))
        if (value.hostname, unquote(value.path), value.query) != (
            expected.hostname,
            unquote(expected.path),
            expected.query,
        ):
            return "disallowed_destination"
        return None
    except (ValueError, FixtureError, PaperError):
        return "disallowed_destination"


if TYPE_CHECKING:
    from paper_radar.fixture_audit.acquisition_models import SourceReason, SourceRequest


def normalize_request(request: SourceRequest) -> SourceRequest:
    from urllib.parse import urlsplit, urlunsplit

    from paper_radar.papers.doi import normalize_doi
    from paper_radar.papers.errors import PaperError

    try:
        updates: dict[str, object] = {}
        if request.doi is not None:
            updates["doi"] = normalize_doi(request.doi)
        if request.publisher_url is not None:
            if request.route != "publisher" or request.journal != "aies":
                raise FixtureError(FixtureReason.INVALID_REQUEST, path="publisher_url")
            parsed = urlsplit(request.publisher_url)
            updates["publisher_url"] = urlunsplit(
                parsed._replace(query="", fragment="")
            )
        normalized = request.model_copy(update=updates)
        url = request_url(normalized)
        check_url = "https:" + url[len("http:") :] if url.startswith("http:") else url
        if checked_source_url(check_url, normalized) is not None:
            raise FixtureError(FixtureReason.INVALID_REQUEST, path="source_url")
        for header in (
            request.conditional_headers.if_none_match,
            request.conditional_headers.if_modified_since,
        ):
            if header is not None and (
                len(header) > 512 or re.search(r"[^\x20-\x7e]|@", header)
            ):
                raise FixtureError(
                    FixtureReason.INVALID_REQUEST, path="conditional_headers"
                )
        if (
            request.conditional_headers.prior_artifact_id is not None
            and request.conditional_headers.if_none_match is None
            and request.conditional_headers.if_modified_since is None
        ):
            raise FixtureError(
                FixtureReason.INVALID_REQUEST, path="conditional_headers"
            )
        return normalized
    except (ValueError, PaperError):
        raise FixtureError(
            FixtureReason.INVALID_REQUEST, path="source_request"
        ) from None
