"""摘要矩阵公共服务:固定成员、同一取得复用、主区块和安全投影。"""

from pathlib import Path

import httpx

from tests.audit_matrix_support import MAIN, MatrixSources
from tests.audit_sampling_support import CODE, sampling_service


def test_run_four_journals_reuses_sampling_material_and_exposes_safe_matrix(
    tmp_path: Path,
) -> None:
    sources = MatrixSources()
    service = sampling_service(tmp_path, sources)
    result = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    assert result.status == "complete"
    assert len(result.matrix) == 19
    assert len(sources.calls) == 15
    assert sum(row.reason == "channel_not_installed" for row in result.matrix) == 4
    assert sum(row.reason == "not_attempted" for row in result.matrix) == 0
    assert [member.final_abstract_source for member in result.members] == [
        "publisher"
    ] * 4
    assert MAIN not in repr(result) and MAIN not in result.model_dump_json()
    assert "audit@example.org" not in result.model_dump_json()
    for member in result.members:
        assert member.final_abstract_candidate_id is not None
        assert (
            service.read_audit_text(
                result.plan.plan_id, member.final_abstract_candidate_id
            )
            == MAIN
        )
    assert service.show_audit(result.plan.plan_id) == result
    service.validate_all()


def test_four_journal_main_blocks_exclude_supplementary_sections_and_feed_tails(
    tmp_path: Path,
) -> None:
    from html import escape

    from paper_radar.fixture_audit.acquisition_policy import FEED_ENDPOINTS

    class BlockSources(MatrixSources):
        def __call__(self, request: httpx.Request) -> httpx.Response:
            response = super().__call__(request)
            if "/doi/" in request.url.path or request.url.path.startswith("/view/"):
                body = response.text
                if request.url.host == "www.iapjournals.ac.cn":
                    body = body.replace(
                        "</html>",
                        '<div class="abstract-en"><p>EXTRA ENGLISH.</p></div></html>',
                    )
                else:
                    body = body.replace(
                        "</section>",
                        (
                            "<h2>Plain Language Summary</h2><p>EXTRA PLS.</p>"
                            "<h2>Key Points</h2><p>EXTRA KEY POINTS.</p></section>"
                        ),
                    )
                return httpx.Response(200, text=body)
            return response

    sources = BlockSources()
    for endpoint in FEED_ENDPOINTS:
        doi = {
            "aies": "10.1175/aies.synthetic",
            "jgr": "10.1029/jgr.synthetic",
            "qjrms": "10.1002/qj.synthetic",
            "dqkx": "10.3878/dqkx.synthetic",
        }[endpoint.journal]
        fragment = (
            "<p>" + MAIN + "</p>EXTRA CITATION 2026-10-26"
            if endpoint.journal == "dqkx"
            else "<p>EXTRA PREFACE.</p><h2>Abstract</h2><p>"
            + escape(MAIN)
            + "</p><h2>Significance Statement</h2><p>EXTRA SIGNIFICANCE.</p>"
        )
        sources.feeds[endpoint.url] = (
            '<rss xmlns:dc="http://purl.org/dc/elements/1.1/"><channel><item><guid>'
            + doi
            + "</guid><link>https://journals.ametsoc.org/view/journals/aies/5/1/synthetic.xml</link><dc:type>article</dc:type><description>"
            + escape(fragment)
            + "</description></item></channel></rss>"
        ).encode()
    service = sampling_service(tmp_path, sources)
    result = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    for row in result.matrix:
        for candidate in row.candidates:
            if candidate.field == "abstract":
                assert (
                    service.read_audit_text(result.plan.plan_id, candidate.candidate_id)
                    == MAIN
                )
    assert {(block.kind) for row in result.matrix for block in row.excluded_blocks} >= {
        "preface",
        "citation_tail",
        "abstract_en",
        "significance",
        "plain_language_summary",
        "key_points",
    }
    service.validate_all()


def test_inline_math_and_unlabeled_supplementary_blocks_stay_separate(
    tmp_path: Path,
) -> None:
    class InlineSources(MatrixSources):
        def __call__(self, request: httpx.Request) -> httpx.Response:
            response = super().__call__(request)
            if "/doi/" in request.url.path or request.url.path.startswith("/view/"):
                body = response.text.replace(MAIN, "A<i>  α  </i>B &lt; C.").replace(
                    "</section>",
                    (
                        '<div class="plain-language-summary">'
                        "EXTRA MUST NOT JOIN.</div></section>"
                    ),
                )
                return httpx.Response(200, text=body)
            return response

    service = sampling_service(tmp_path, InlineSources())
    result = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    member = result.members[0]
    assert member.final_abstract_candidate_id
    assert (
        service.read_audit_text(result.plan.plan_id, member.final_abstract_candidate_id)
        == "A  α  B < C."
    )
    assert result.journal_summaries[0].priority_truncation_conflicts == 1


def test_known_login_shape_with_identity_is_blocked_and_not_retained(
    tmp_path: Path,
) -> None:
    class LoginSources(MatrixSources):
        def __call__(self, request: httpx.Request) -> httpx.Response:
            response = super().__call__(request)
            if (
                request.url.host == "rmets.onlinelibrary.wiley.com"
                and "/doi/" in request.url.path
            ):
                return httpx.Response(
                    200,
                    text=response.text.replace(
                        "</html>",
                        '<form id="login-form"><input type="password"></form></html>',
                    ),
                )
            return response

    service = sampling_service(tmp_path, LoginSources())
    result = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    row = next(
        row
        for row in result.matrix
        if row.request.journal == "qjrms"
        and row.request.route == "publisher"
        and row.request.channel == "http"
    )
    assert row.reason == "access_blocked_403"
    execution = next(
        value for value in result.executions if value.execution_id == row.acquisition_id
    )
    assert execution.settlement and execution.settlement.artifact_id is None
    assert result.status == "complete"
