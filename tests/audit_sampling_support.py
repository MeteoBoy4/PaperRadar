"""独立合成四刊来源;只替换外部 HTTP 与等待。"""

from pathlib import Path
from urllib.parse import unquote

import httpx

from paper_radar.fixture_audit import FixtureAudit
from paper_radar.fixture_audit.acquisition_models import CodeIdentity
from paper_radar.fixture_audit.acquisition_policy import FEED_ENDPOINTS
from paper_radar.fixture_audit.source_http import SourceHTTPExecutor
from paper_radar.storage.database import upgrade_database

CODE = CodeIdentity(commit="a" * 40, dirty=False, basis="synthetic")
FIXTURES = Path(__file__).parent / "fixtures" / "a10"


class SamplingClock:
    def __init__(self) -> None:
        self.value = 0.0

    def monotonic(self) -> float:
        return self.value

    async def sleep(self, seconds: float) -> None:
        self.value += seconds


class SamplingSources:
    def __init__(self) -> None:
        self.feeds = {
            endpoint.url: (FIXTURES / f"sampling-{endpoint.journal}.xml").read_bytes()
            for endpoint in FEED_ENDPOINTS
        }
        self.calls: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        self.calls.append(url)
        if url in self.feeds:
            return httpx.Response(200, stream=httpx.ByteStream(self.feeds[url]))
        path = unquote(request.url.path)
        if path.startswith("/doiRA/"):
            doi = path.removeprefix("/doiRA/")
            agency = (
                "ISTIC"
                if doi.startswith("10.3878/")
                else "DataCite"
                if doi.startswith("10.1002/")
                else "Crossref"
            )
            return httpx.Response(200, json=[{"DOI": doi, "RA": agency}])
        if path.startswith("/works/"):
            return httpx.Response(
                200,
                json={
                    "message": {
                        "DOI": path.removeprefix("/works/"),
                        "type": "journal-article",
                    }
                },
            )
        if path.startswith("/dois/"):
            doi = path.removeprefix("/dois/")
            return httpx.Response(
                200,
                json={
                    "data": {
                        "id": doi,
                        "attributes": {
                            "doi": doi,
                            "types": {"resourceTypeGeneral": "JournalArticle"},
                        },
                    }
                },
            )
        if request.url.host == "journals.ametsoc.org":
            return httpx.Response(
                200,
                text=(
                    '<html><meta name="citation_doi" '
                    'content="10.1175/aies.synthetic">'
                    '<meta property="og:type" content="article"></html>'
                ),
            )
        if request.url.host == "www.iapjournals.ac.cn":
            doi = path.split("/doi/", 1)[1]
            return httpx.Response(
                200,
                text=(
                    f'<html><meta name="citation_doi" content="{doi}">'
                    '<meta name="dc.type" content="论文"></html>'
                ),
            )
        raise AssertionError("unexpected synthetic route")


def sampling_service(tmp_path: Path, sources: SamplingSources) -> FixtureAudit:
    database = tmp_path / "facts.sqlite3"
    upgrade_database(database)
    clock = SamplingClock()
    executor = SourceHTTPExecutor(
        transport=httpx.MockTransport(sources),
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )
    return FixtureAudit(
        database, tmp_path / "data", source_executors={"http": executor}
    )
