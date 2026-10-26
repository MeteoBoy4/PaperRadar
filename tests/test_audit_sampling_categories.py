"""封闭来源类别表与非依据字段的公共行为向量。"""

from pathlib import Path

import httpx
import pytest

from tests.audit_sampling_support import CODE, SamplingSources, sampling_service


class CategorySources(SamplingSources):
    def __init__(self, mode: str) -> None:
        super().__init__()
        self.mode = mode
        if mode == "platform_unknown":
            self.feeds = {
                url: body.replace(b">article</dc:type>", b">unregistered</dc:type>")
                for url, body in self.feeds.items()
            }
        if mode == "no_stable_identifier":
            self.feeds = {
                url: body.replace(
                    b"<link>https://journals.ametsoc.org/view/journals/aies/5/1/synthetic.xml</link>",
                    b"",
                ).replace(
                    b"synthetic identity only",
                    b"10.1175/not-an-identity journal-article",
                )
                for url, body in self.feeds.items()
            }

    def __call__(self, request: httpx.Request) -> httpx.Response:
        response = super().__call__(request)
        path = request.url.path
        if path == "/works/10.1029/jgr.synthetic":
            if self.mode == "non_article":
                return httpx.Response(
                    200,
                    json={
                        "message": {
                            "DOI": "10.1029/jgr.synthetic",
                            "type": "peer-review",
                        }
                    },
                )
            if self.mode == "missing_type":
                return httpx.Response(
                    200, json={"message": {"DOI": "10.1029/jgr.synthetic"}}
                )
        if (
            path == "/doiRA/10.1175/aies.synthetic"
            and self.mode == "og_and_citation_not_type"
        ):
            return httpx.Response(
                200, json=[{"DOI": "10.1175/aies.synthetic", "RA": "ISTIC"}]
            )
        if path == "/doiRA/10.3878/dqkx.synthetic" and self.mode == "category_conflict":
            return httpx.Response(
                200, json=[{"DOI": "10.3878/dqkx.synthetic", "RA": "Crossref"}]
            )
        if path == "/works/10.3878/dqkx.synthetic" and self.mode == "category_conflict":
            return httpx.Response(
                200,
                json={
                    "message": {"DOI": "10.3878/dqkx.synthetic", "type": "component"}
                },
            )
        if path == "/dois/10.1002/qj.synthetic" and self.mode == "datacite_non_article":
            return httpx.Response(
                200,
                json={
                    "data": {
                        "id": "10.1002/qj.synthetic",
                        "attributes": {
                            "doi": "10.1002/qj.synthetic",
                            "types": {"resourceTypeGeneral": "Text"},
                        },
                    }
                },
            )
        if (
            request.url.host == "www.iapjournals.ac.cn"
            and path.startswith("/dqkx/article/")
            and self.mode == "platform_unknown"
        ):
            return httpx.Response(200, text=response.text.replace("论文", "未登记值"))
        if (
            request.url.host == "www.iapjournals.ac.cn"
            and path.startswith("/dqkx/article/")
            and self.mode == "publisher_type_missing"
        ):
            return httpx.Response(
                200,
                text=response.text.replace('<meta name="dc.type" content="论文">', ""),
            )
        if request.url.host == "journals.ametsoc.org" and path.startswith("/view/"):
            if self.mode == "identity_blocked":
                return httpx.Response(403)
            if self.mode == "identity_absent":
                return httpx.Response(404)
        return response


@pytest.mark.parametrize(
    "mode,journal,result,reason",
    [
        ("non_article", "jgr", "excluded_deterministic", "not_journal_article"),
        ("missing_type", "jgr", "excluded_deterministic", "category_unknown"),
        (
            "og_and_citation_not_type",
            "aies",
            "excluded_deterministic",
            "category_unknown",
        ),
        ("category_conflict", "dqkx", "excluded_deterministic", "category_conflict"),
        (
            "datacite_non_article",
            "qjrms",
            "excluded_deterministic",
            "not_journal_article",
        ),
        ("platform_unknown", "dqkx", "excluded_deterministic", "category_unknown"),
        ("publisher_type_missing", "dqkx", "selected", "selected"),
        (
            "no_stable_identifier",
            "aies",
            "excluded_deterministic",
            "no_stable_identifier",
        ),
        ("identity_blocked", "aies", "blocked_pending", "source_blocked"),
        ("identity_absent", "aies", "excluded_deterministic", "identity_unavailable"),
    ],
)
def test_only_closed_explicit_fields_supply_category_evidence(
    tmp_path: Path, mode: str, journal: str, result: str, reason: str
) -> None:
    sources = CategorySources(mode)
    service = sampling_service(tmp_path, sources)
    plan = service.create_audit_plan(
        contact_email="audit@example.org", code_identity=CODE
    )
    view = service.select_audit_samples(
        plan.plan_id, contact_email="audit@example.org", code_identity=CODE
    )
    outcome = next(item for item in view.sampling if item.journal == journal).entries[0]
    assert outcome.result == result
    assert outcome.reason == reason
    if mode == "identity_blocked":
        assert [item.status for item in view.sampling[1:]] == ["complete"] * 3
        assert outcome.routes[0].reason == "access_blocked_403"
    if mode == "publisher_type_missing":
        assert [basis.locator for basis in outcome.category_bases] == ["item/dc:type"]
    service.validate_all()
