"""公共摘要审计的截断、仲裁、真实分母与失败隔离。"""

from pathlib import Path

import httpx
import pytest

from tests.audit_matrix_support import MAIN, MatrixSources
from tests.audit_sampling_support import CODE, sampling_service


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("α" * 98 + ".", {"short_under_100"}),
        ("😀" * 99 + ".", set()),
        ("研究结果" * 30 + "。”）", set()),
        ("x" * 100 + "...", {"trailing_ellipsis", "missing_terminal_punctuation"}),
        ("x" * 100 + "…", {"trailing_ellipsis", "missing_terminal_punctuation"}),
        ("x" * 100 + " Read more", {"read_more", "missing_terminal_punctuation"}),
        ("x" * 100 + "阅读更多。", {"read_more"}),
        ("&lt;broken&gt;" + "x" * 100 + ".", {"markup_residue"}),
        ("x" * 100, {"missing_terminal_punctuation"}),
    ],
)
def test_truncation_signals_are_replayable_and_100_counts_unicode_codepoints(
    tmp_path: Path, value: str, expected: set[str]
) -> None:
    class TruncatedSources(MatrixSources):
        def __call__(self, request: httpx.Request) -> httpx.Response:
            response = super().__call__(request)
            if "/doi/" in request.url.path or request.url.path.startswith("/view/"):
                return httpx.Response(200, text=response.text.replace(MAIN, value))
            return response

    service = sampling_service(tmp_path, TruncatedSources())
    view = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    candidate = next(
        candidate
        for row in view.matrix
        if row.request.journal == "aies"
        and row.request.route == "publisher"
        and row.request.channel == "http"
        for candidate in row.candidates
        if candidate.field == "abstract"
    )
    assert set(candidate.signals) == expected
    assert candidate.suspected_truncated == bool(expected)
    assert view.members[0].final_abstract_candidate_id == candidate.candidate_id
    assert candidate.codepoints == len(
        service.read_audit_text(view.plan.plan_id, candidate.candidate_id)
    )
    service.validate_all()


def test_member_routes_use_original_acquisition_time_and_separate_field_arbitration(
    tmp_path: Path,
) -> None:
    class FieldSources(MatrixSources):
        def __call__(self, request: httpx.Request) -> httpx.Response:
            response = super().__call__(request)
            if "/doi/" in request.url.path or request.url.path.startswith("/view/"):
                return httpx.Response(
                    200,
                    text=response.text.replace(
                        '<meta name="citation_title" content="Publisher title">', ""
                    ).replace(MAIN, "short."),
                )
            return response

    sources = FieldSources()
    service = sampling_service(tmp_path, sources)
    plan = service.create_audit_plan(
        contact_email="audit@example.org", code_identity=CODE, plan_key="fixed"
    )
    selected = service.select_audit_samples(
        plan.plan_id, contact_email="audit@example.org", code_identity=CODE
    )
    original = {execution.execution_id: execution for execution in selected.executions}
    view = service.run_audit(
        contact_email="audit@example.org", code_identity=CODE, plan_key="fixed"
    )
    assert len(sources.calls) == 15
    assert view.members[0].final_title_source == "registry"
    assert view.members[0].final_abstract_source == "publisher"
    assert view.journal_summaries[0].priority_truncation_conflicts == 1
    assert {decision.reason for decision in view.members[0].decisions} >= {
        "selected",
        "lower_source_priority",
    }
    for row in view.matrix:
        if row.acquisition_id in original:
            old = original[row.acquisition_id]
            assert old.settlement
            assert row.observed_at == old.settlement.settled_at
    ra = next(
        value
        for value in view.route_summaries
        if value.journal == "aies" and value.route == "doi_ra"
    )
    assert (ra.applicable, ra.attempted, ra.abstract_coverage.denominator) == (1, 1, 0)
    render = next(
        value
        for value in view.route_summaries
        if value.journal == "jgr" and value.channel == "browser_render"
    )
    assert (
        render.applicable,
        render.attempted,
        render.channel_not_installed,
        render.not_attempted,
        render.errors,
    ) == (1, 0, 1, 0, 0)
    assert render.abstract_coverage.ratio is None
    assert all(
        value.applicable == 0 and value.abstract_coverage.ratio is None
        for value in view.route_summaries
        if value.channel in {"official_api", "repository"}
    )


def test_unrecognized_shape_never_adopts_page_fields_and_http_failure_is_isolated(
    tmp_path: Path,
) -> None:
    class MissingSources(MatrixSources):
        def __call__(self, request: httpx.Request) -> httpx.Response:
            response = super().__call__(request)
            if (
                request.url.host == "agupubs.onlinelibrary.wiley.com"
                and "/doi/" in request.url.path
            ):
                return httpx.Response(404)
            if (
                request.url.host == "rmets.onlinelibrary.wiley.com"
                and "/doi/" in request.url.path
            ):
                return httpx.Response(
                    200,
                    text=(
                        '<meta name="citation_doi" content="10.1002/qj.synthetic">'
                        '<meta name="citation_title" content="Unrecognized title">'
                        "<article>"
                    )
                    + MAIN
                    + "</article>",
                )
            return response

    service = sampling_service(tmp_path, MissingSources())
    view = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    assert view.status == "complete"
    reasons = {
        (row.request.journal, row.reason)
        for row in view.matrix
        if row.request.route == "publisher" and row.request.channel == "http"
    }
    assert ("jgr", "not_found") in reasons and (
        "qjrms",
        "unrecognized_page_shape",
    ) in reasons
    assert view.members[1].final_abstract_source == "registry"
    assert view.members[2].final_title_source == "registry"
    assert view.members[3].final_abstract_source == "publisher"
    jgr = next(
        value
        for value in view.route_summaries
        if value.journal == "jgr"
        and value.route == "publisher"
        and value.channel == "http"
    )
    assert (jgr.applicable, jgr.attempted, jgr.nonempty_abstracts, jgr.errors) == (
        1,
        1,
        0,
        1,
    )
    assert jgr.abstract_coverage.denominator == 1
    service.validate_all()


def test_all_feeds_fail_without_manufacturing_members_or_coverage(
    tmp_path: Path,
) -> None:
    class FailedSources(MatrixSources):
        def __call__(self, request: httpx.Request) -> httpx.Response:
            self.calls.append(str(request.url))
            return httpx.Response(404)

    sources = FailedSources()
    service = sampling_service(tmp_path, sources)
    view = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    assert view.status == "partial" and not view.members and not view.matrix
    assert view.physical_http_requests == 4
    assert [journal.sampling_status for journal in view.journal_summaries] == [
        "blocked_pending"
    ] * 4
    assert all(
        summary.abstract_coverage.ratio is None for summary in view.route_summaries
    )
    service.validate_all()


def test_primary_paragraphs_join_once_and_title_and_abstract_remain_independent(
    tmp_path: Path,
) -> None:
    class ParagraphSources(MatrixSources):
        def __call__(self, request: httpx.Request) -> httpx.Response:
            response = super().__call__(request)
            if "/doi/" in request.url.path or request.url.path.startswith("/view/"):
                return httpx.Response(
                    200,
                    text=response.text.replace(
                        MAIN, "First  paragraph.</p><p>Second paragraph."
                    ),
                )
            return response

    service = sampling_service(tmp_path, ParagraphSources())
    view = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    identity = view.members[0].final_abstract_candidate_id
    assert identity
    assert (
        service.read_audit_text(view.plan.plan_id, identity)
        == "First  paragraph.\nSecond paragraph."
    )


def test_interrupted_matrix_keeps_unknown_execution_distinct_from_not_attempted(
    tmp_path: Path,
) -> None:
    class InterruptedSources(MatrixSources):
        def __call__(self, request: httpx.Request) -> httpx.Response:
            if (
                request.url.host == "agupubs.onlinelibrary.wiley.com"
                and "/doi/" in request.url.path
            ):
                raise KeyboardInterrupt
            return super().__call__(request)

    service = sampling_service(tmp_path, InterruptedSources())
    with pytest.raises(KeyboardInterrupt):
        service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    view = service.list_audits()[0]
    assert view.status == "partial"
    unknown = next(
        row
        for row in view.matrix
        if row.request.journal == "jgr"
        and row.request.route == "publisher"
        and row.request.channel == "http"
    )
    assert unknown.reason == "outcome_unknown" and unknown.acquisition_id
    assert view.physical_http_unknown_executions == 1
    assert view.members[1].final_abstract_candidate_id is None
    assert any(row.reason == "not_attempted" for row in view.matrix)
    assert all(
        row.reason != "not_attempted"
        for row in view.matrix
        if row.request.channel != "http"
    )
    service.validate_all()


def test_no_doi_has_explicit_inapplicability_without_channel_cartesian_product(
    tmp_path: Path,
) -> None:
    sources = MatrixSources()
    for url, raw in list(sources.feeds.items()):
        if "iapjournals" in url:
            sources.feeds[url] = raw.replace(
                b"<prism:doi>10.3878/dqkx.synthetic</prism:doi>", b""
            )
    service = sampling_service(tmp_path, sources)
    view = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    member = view.members[3]
    assert member.registry_applicability == "not_applicable_no_doi"
    assert member.publisher_applicability == "not_applicable_no_doi"
    assert [
        (row.request.route, row.request.channel)
        for row in view.matrix
        if row.member_id == member.member_id
    ] == [("feed", "http")]
    assert view.status == "complete"
    service.validate_all()


@pytest.mark.parametrize("count", [4, 11])
def test_run_rejects_out_of_range_n_before_plan_or_network(
    tmp_path: Path, count: int
) -> None:
    from paper_radar.fixture_audit import FixtureError

    sources = MatrixSources()
    service = sampling_service(tmp_path, sources)
    with pytest.raises(FixtureError) as caught:
        service.run_audit(
            contact_email="audit@example.org", code_identity=CODE, target_count=count
        )
    assert caught.value.reason == "invalid_plan"
    assert sources.calls == [] and service.list_audits() == ()


def test_valid_empty_primary_record_is_distinct_from_unrecognized_shape(
    tmp_path: Path,
) -> None:
    class EmptySources(MatrixSources):
        def __call__(self, request: httpx.Request) -> httpx.Response:
            response = super().__call__(request)
            if "/doi/" in request.url.path or request.url.path.startswith("/view/"):
                return httpx.Response(200, text=response.text.replace(MAIN, ""))
            return response

    service = sampling_service(tmp_path, EmptySources())
    view = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    assert view.status == "complete"
    publishers = [
        row
        for row in view.matrix
        if row.request.route == "publisher" and row.request.channel == "http"
    ]
    assert all(
        row.reason == "record_without_abstract" and row.valid_record
        for row in publishers
    )
    assert view.members[0].final_abstract_source == "registry"
    assert view.members[3].final_abstract_source == "feed"
    assert view.members[3].final_title_source == "publisher"
    assert all(
        summary.valid_records == 1
        and summary.nonempty_abstracts == 0
        and summary.errors == 0
        for summary in view.route_summaries
        if summary.route == "publisher" and summary.channel == "http"
    )
    service.validate_all()


def test_feed_physical_item_locator_and_registry_jats_heading_use_primary_block(
    tmp_path: Path,
) -> None:
    class JatsSources(MatrixSources):
        def __call__(self, request: httpx.Request) -> httpx.Response:
            response = super().__call__(request)
            if request.url.path.startswith("/works/"):
                value = response.json()
                value["message"]["abstract"] = (
                    "<jats:sec><jats:title>Abstract</jats:title><jats:p>"
                    + MAIN
                    + (
                        "</jats:p></jats:sec><jats:sec><jats:title>"
                        "Plain Language Summary"
                        "</jats:title><jats:p>EXTRA PLS.</jats:p></jats:sec>"
                    )
                )
                return httpx.Response(200, json=value)
            return response

    sources = JatsSources()
    for url, raw in list(sources.feeds.items()):
        if "21698996" in url:
            sources.feeds[url] = raw.replace(
                b"<channel>",
                (
                    b"<channel><image><item><description>EXTRA NESTED ITEM."
                    b"</description></item></image>"
                ),
            )
    service = sampling_service(tmp_path, sources)
    view = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    feed = next(
        row
        for row in view.matrix
        if row.request.journal == "jgr" and row.request.route == "feed"
    )
    assert not any(candidate.field == "abstract" for candidate in feed.candidates)
    registry = next(
        row
        for row in view.matrix
        if row.request.journal == "jgr" and row.request.route == "registry_crossref"
    )
    candidate = next(
        candidate for candidate in registry.candidates if candidate.field == "abstract"
    )
    assert service.read_audit_text(view.plan.plan_id, candidate.candidate_id) == MAIN


def test_feed_reports_citation_tail_only_when_outside_paragraph_text_exists(
    tmp_path: Path,
) -> None:
    sources = MatrixSources()
    for url, raw in list(sources.feeds.items()):
        if "iapjournals" in url:
            sources.feeds[url] = raw.replace("引文尾行".encode(), b"")
    service = sampling_service(tmp_path, sources)
    view = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    feed = next(
        row
        for row in view.matrix
        if row.request.journal == "dqkx" and row.request.route == "feed"
    )
    assert not any(block.kind == "citation_tail" for block in feed.excluded_blocks)
