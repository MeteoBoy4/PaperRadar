"""JGR 元数据生产接线,只替换 HTTP transport。"""

from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from paper_radar.feed_metadata import JGRMetadata
from paper_radar.feed_metadata.models import MetadataResult
from paper_radar.fixture_audit.source_http import SourceHTTPExecutor
from paper_radar.papers import PaperFacts
from paper_radar.papers.models import AbstractValue
from tests.feed_support import facts, item

DOI = "10.1029/2025jd043927"
FULL = (
    "This synthetic complete abstract records atmospheric measurements and "
    "describes the methodology and results in sufficient detail for the shared parser."
)


def test_jgr_metadata_routes_and_source_priority_are_public(tmp_path: Path) -> None:
    from paper_radar.feed_metadata import JGRMetadata

    papers = facts(tmp_path)
    feed = papers.register_feed(
        "https://agupubs.onlinelibrary.wiley.com/action/showFeed?jc=21698996&type=etoc&feed=rss"
    )
    saved = papers.submit(item(feed.feed_id, doi=DOI, payload=b"new item with DOI"))
    assert saved.paper_id and papers.data_root
    seen = []

    def respond(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if "doiRA" in str(request.url):
            return httpx.Response(200, json=[{"DOI": DOI, "RA": "Crossref"}])
        if request.url.host == "api.crossref.org":
            return httpx.Response(
                200,
                json={
                    "message": {
                        "DOI": DOI,
                        "title": ["Registry title"],
                        "abstract": FULL,
                        "type": "journal-article",
                    }
                },
            )
        return httpx.Response(
            200,
            text=f'<meta name="citation_doi" content="{DOI}">'
            '<meta name="citation_title" content="Publisher title">'
            f'<div class="abstract">{FULL}'
            '<div class="key-points">SECRET EXTRA</div></div>',
        )

    service = JGRMetadata(
        papers.database,
        papers.data_root,
        http=SourceHTTPExecutor(transport=httpx.MockTransport(respond)),
    )
    result = service.enrich(
        saved.paper_id, request_id="one", contact_email="contact@example.org"
    )
    assert result.minimum_complete and result.nontruncated_complete
    assert result.title == "Publisher title"
    assert len(result.routes) == 3
    content = service.content(result.request_key)
    assert content.abstract == FULL
    assert "SECRET EXTRA" not in content.abstract
    selected_abstract = papers.show(saved.paper_id).fields["abstract"].value
    assert isinstance(selected_abstract, AbstractValue)
    assert selected_abstract.text == FULL
    assert (
        service.enrich(
            saved.paper_id, request_id="one", contact_email="contact@example.org"
        )
        == result
    )
    assert len(seen) == 3
    service.validate_all()


def setup_metadata(
    root: Path,
    responder: Callable[[httpx.Request], httpx.Response],
    *,
    fields: dict[str, object] | None = None,
    doi: str | None = DOI,
) -> tuple[PaperFacts, str, JGRMetadata]:
    from paper_radar.feed_metadata import JGRMetadata
    from paper_radar.fixture_audit.acquisition_policy import FEED_ENDPOINTS
    from tests.test_audit_http import FakeClock

    papers = facts(root)
    feed = papers.register_feed(
        next(value.url for value in FEED_ENDPOINTS if value.journal == "jgr")
    )
    request = item(feed.feed_id, doi=doi)
    if fields is not None:
        request["fields"] = fields
    saved = papers.submit(request)
    assert saved.paper_id and papers.data_root
    clock = FakeClock()
    service = JGRMetadata(
        papers.database,
        papers.data_root,
        http=SourceHTTPExecutor(
            transport=httpx.MockTransport(responder),
            monotonic=clock.monotonic,
            sleep=clock.sleep,
        ),
    )
    return papers, saved.paper_id, service


def enrich(service: JGRMetadata, paper_id: str, key: str = "one") -> MetadataResult:
    return service.enrich(paper_id, request_id=key, contact_email="contact@example.org")


def test_datacite_applicability_and_publisher_failure_keep_registry_fields(
    tmp_path: Path,
) -> None:
    def responder(request: httpx.Request) -> httpx.Response:
        if "doiRA" in str(request.url):
            return httpx.Response(200, json=[{"DOI": DOI, "RA": "DataCite"}])
        assert request.url.host != "api.crossref.org"
        if request.url.host == "api.datacite.org":
            return httpx.Response(
                200,
                json={
                    "data": {
                        "id": DOI,
                        "attributes": {
                            "doi": DOI,
                            "titles": [{"title": "DataCite title"}],
                            "descriptions": [
                                {"descriptionType": "Other", "description": "IGNORE"},
                                {"descriptionType": "Abstract", "description": FULL},
                            ],
                            "types": {"resourceTypeGeneral": "JournalArticle"},
                        },
                    }
                },
            )
        return httpx.Response(403, text="error page must not persist")

    _papers, paper_id, service = setup_metadata(tmp_path, responder)
    result = enrich(service, paper_id)
    assert result.minimum_complete and result.title == "DataCite title"
    assert service.content(result.request_key).abstract == FULL
    assert {value.route for value in result.routes} == {
        "doi_ra",
        "registry_datacite",
        "publisher",
    }
    assert result.routes[-1].categories[0].decision == "journal_article"
    assert (
        next(value for value in result.routes if value.route == "publisher").artifact_id
        is None
    )
    service.validate_all()


@pytest.mark.parametrize("agency", ["mEDRA", None, "404"])
def test_unknown_unsupported_or_404_routing_is_not_doi_absence(
    tmp_path: Path, agency: str | None
) -> None:
    def responder(request: httpx.Request) -> httpx.Response:
        if "doiRA" in str(request.url):
            if agency == "404":
                return httpx.Response(404)
            return httpx.Response(200, json=[{"DOI": DOI, "RA": agency}])
        assert request.url.host == "agupubs.onlinelibrary.wiley.com"
        return httpx.Response(404)

    papers, paper_id, service = setup_metadata(tmp_path, responder)
    result = enrich(service, paper_id)
    assert not result.minimum_complete
    assert result.registry_applicability in {"agency_unknown", "agency_unsupported"}
    assert "no_abstract" in result.missing
    assert papers.show(paper_id).doi == DOI
    assert len(result.routes) == 2
    service.validate_all()


def test_truncated_publisher_does_not_prevent_other_route_and_b_is_stricter(
    tmp_path: Path,
) -> None:
    seen = []

    def responder(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.host)
        if "doiRA" in str(request.url):
            return httpx.Response(200, json=[{"DOI": DOI, "RA": "Crossref"}])
        if request.url.host == "api.crossref.org":
            return httpx.Response(
                200,
                json={
                    "message": {
                        "DOI": DOI,
                        "abstract": FULL,
                        "title": ["Registry title"],
                    }
                },
            )
        return httpx.Response(
            200,
            text=f'<meta name="citation_doi" content="{DOI}">'
            '<meta name="citation_title" content="Pub">'
            '<div class="abstract">Short...</div>',
        )

    _papers, paper_id, service = setup_metadata(tmp_path, responder)
    result = enrich(service, paper_id)
    assert result.minimum_complete and not result.nontruncated_complete
    assert result.suspected_truncated is True
    assert "api.crossref.org" in seen
    assert service.content(result.request_key).abstract == "Short..."
    service.validate_all()


def test_invalid_registry_record_and_publisher_main_boundary_do_not_erase_feed(
    tmp_path: Path,
) -> None:
    fields = {
        "title": {"value": "Feed title", "locator": "item/title"},
        "abstract": {
            "value": {"text": FULL, "is_truncated": False, "rule": "fixture"},
            "locator": "item/description",
        },
    }

    def responder(request: httpx.Request) -> httpx.Response:
        if "doiRA" in str(request.url):
            return httpx.Response(200, json=[{"DOI": DOI, "RA": "Crossref"}])
        if request.url.host == "api.crossref.org":
            return httpx.Response(
                200,
                json={
                    "message": {
                        "DOI": "10.1000/wrong",
                        "title": ["Wrong"],
                        "abstract": "wrong",
                    }
                },
            )
        return httpx.Response(
            200,
            text=f'<meta name="citation_doi" content="{DOI}">'
            '<section class="key-points">Only extras.</section>',
        )

    _papers, paper_id, service = setup_metadata(tmp_path, responder, fields=fields)
    result = enrich(service, paper_id)
    assert result.title == "Feed title"
    assert service.content(result.request_key).abstract == FULL
    assert "no_source_url" in result.missing
    assert all(route.artifact_id is None for route in result.routes)
    assert (
        next(value for value in result.routes if value.route == "publisher")
        .excluded_blocks[0]
        .kind
        == "key_points"
    )
    service.validate_all()


def test_no_doi_missing_routes_are_explicit_and_later_doi_requires_new_request(
    tmp_path: Path,
) -> None:
    def deny(request: httpx.Request) -> httpx.Response:
        raise AssertionError("No DOI must not construct an external target")

    papers, paper_id, service = setup_metadata(tmp_path, deny, doi=None)
    result = enrich(service, paper_id)
    assert result.registry_applicability == "not_applicable_no_doi"
    assert result.routes_settled and "no_abstract" in result.missing
    assert service.requests(paper_id) == (result,)
    feed = papers.trace(paper_id).discoveries[0]
    papers.submit(item(feed.feed_id, doi=DOI, payload=b"new item with DOI"))
    after = service.replay(result.request_key)
    assert after.version_id == result.version_id
    assert "current_version_changed" in after.missing
    assert not after.minimum_complete


@pytest.mark.parametrize("status", [404, 429, 500])
def test_single_registry_failure_retains_publisher_success(
    tmp_path: Path, status: int
) -> None:
    counts = []

    def responder(request: httpx.Request) -> httpx.Response:
        counts.append(str(request.url))
        if "doiRA" in str(request.url):
            return httpx.Response(200, json=[{"DOI": DOI, "RA": "Crossref"}])
        if request.url.host == "api.crossref.org":
            return httpx.Response(status, text="error page")
        return httpx.Response(
            200,
            text=f'<meta name="citation_doi" content="{DOI}">'
            '<meta name="citation_title" content="Pub">'
            f'<div class="abstract">{FULL}</div>',
        )

    _papers, paper_id, service = setup_metadata(tmp_path, responder)
    result = enrich(service, paper_id)
    assert result.minimum_complete
    registry = next(
        value for value in result.routes if value.route == "registry_crossref"
    )
    assert registry.artifact_id is None
    assert registry.http is not None and registry.http.round_count == (
        1 if status == 404 else 2
    )
    service.validate_all()


def test_invalid_record_shape_is_local_and_empty_result_expresses_missing_input(
    tmp_path: Path,
) -> None:
    def responder(request: httpx.Request) -> httpx.Response:
        if "doiRA" in str(request.url):
            return httpx.Response(200, json=[{"DOI": DOI, "RA": "Crossref"}])
        if request.url.host == "api.crossref.org":
            return httpx.Response(
                200, json={"message": {"DOI": DOI, "title": [], "abstract": None}}
            )
        return httpx.Response(
            200,
            text=f'<meta name="citation_doi" content="{DOI}">'
            '<div class="abstract"></div>',
        )

    _papers, paper_id, service = setup_metadata(tmp_path, responder, fields={})
    result = enrich(service, paper_id)
    assert set(result.missing) == {"no_title", "no_abstract", "no_source_url"}
    assert result.routes_settled and not result.minimum_complete
    assert all(value.artifact_id is None for value in result.routes)
    service.validate_all()
