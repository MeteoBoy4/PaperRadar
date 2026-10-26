"""独立合成摘要来源,仅替换 HTTP 边界。"""

from urllib.parse import unquote

import httpx

from tests.audit_sampling_support import SamplingSources

MAIN = (
    "This is a synthetic primary abstract that preserves mathematical x < y "
    "and Unicode α while describing a sufficiently long result."
)


class MatrixSources(SamplingSources):
    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = unquote(request.url.path)
        if str(request.url) in self.feeds or path.startswith("/doiRA/"):
            return super().__call__(request)
        self.calls.append(str(request.url))
        if path.startswith("/works/"):
            return httpx.Response(
                200,
                json={
                    "message": {
                        "DOI": path.removeprefix("/works/"),
                        "type": "journal-article",
                        "title": ["Registry title"],
                        "abstract": "<jats:p>" + MAIN + "</jats:p>",
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
                            "titles": [{"title": "Registry title"}],
                            "descriptions": [
                                {"descriptionType": "Abstract", "description": MAIN}
                            ],
                        },
                    }
                },
            )
        doi = (
            "10.1175/aies.synthetic"
            if request.url.host == "journals.ametsoc.org"
            else path.split("/doi/", 1)[1]
        )
        block = (
            '<div class="abstract-cn"><p>' + MAIN + "</p></div>"
            if request.url.host == "www.iapjournals.ac.cn"
            else '<section class="article-section__abstract"><h2>Abstract</h2><p>'
            + MAIN
            + "</p></section>"
        )
        return httpx.Response(
            200,
            text='<html><meta name="citation_doi" content="'
            + doi
            + '"><meta name="dc.type" content="论文">'
            + '<meta name="citation_title" content="Publisher title">'
            + block
            + "</html>",
        )
