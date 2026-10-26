"""冻结前的 Feed 安全边界、原始顺序与计划 N 边界。"""

from pathlib import Path

import pytest

from paper_radar.fixture_audit.acquisition_policy import FEED_ENDPOINTS
from tests.audit_sampling_support import CODE, SamplingSources, sampling_service


@pytest.mark.parametrize(
    "raw",
    [
        b"<!DOCTYPE rss [<!ENTITY x 'expanded'>]><rss><channel/></rss>",
        '<!DOCTYPE rss [<!ENTITY x "expanded">]><rss><channel/></rss>'.encode("utf-16"),
        '<!DOCTYPE rss SYSTEM "https://must-not-read.invalid/"><rss><channel/></rss>'.encode(
            "utf-32"
        ),
        b"<rss><channel>",
        b"<html><form id='challenge-form'></form></html>",
    ],
)
def test_invalid_or_unsafe_feed_never_becomes_frozen_and_can_be_explicitly_retried(
    tmp_path: Path, raw: bytes
) -> None:
    sources = SamplingSources()
    original = sources.feeds[FEED_ENDPOINTS[1].url]
    sources.feeds[FEED_ENDPOINTS[1].url] = raw
    service = sampling_service(tmp_path, sources)
    plan = service.create_audit_plan(
        contact_email="audit@example.org", code_identity=CODE
    )
    blocked = service.select_audit_samples(
        plan.plan_id, contact_email="audit@example.org", code_identity=CODE
    )
    assert blocked.sampling[1].feed is None
    assert blocked.sampling[1].status == "blocked_pending"
    assert [item.status for item in (blocked.sampling[0], *blocked.sampling[2:])] == [
        "complete"
    ] * 3
    failed = next(item for item in blocked.executions if item.request.journal == "jgr")
    assert failed.settlement is not None and failed.settlement.artifact_id is None
    sources.feeds[FEED_ENDPOINTS[1].url] = original
    complete = service.continue_audit_sampling(
        plan.plan_id, contact_email="audit@example.org", code_identity=CODE
    )
    assert complete.sampling[1].members[0].doi == "10.1029/jgr.synthetic"
    assert sum(call == FEED_ENDPOINTS[1].url for call in sources.calls) == 2
    service.validate_all()


def test_rdf_sequence_and_one_plan_n_control_selection_instead_of_dates(
    tmp_path: Path,
) -> None:
    sources = SamplingSources()
    sequence = "".join(
        f'<rdf:li rdf:resource="urn:item:{position}"/>' for position in range(12, 0, -1)
    )
    items = "".join(
        f'<item rdf:about="urn:item:{position}"><dc:type>article</dc:type>'
        f"<dc:date>{(2000, 2030, 2010)[position % 3]}</dc:date></item>"
        for position in range(1, 13)
    )
    sources.feeds[FEED_ENDPOINTS[3].url] = (
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:dc="http://purl.org/dc/elements/1.1/"><channel><items><rdf:Seq>'
        + sequence
        + "</rdf:Seq></items></channel>"
        + items
        + "</rdf:RDF>"
    ).encode()
    service = sampling_service(tmp_path, sources)
    for target in (5, 10):
        plan = service.create_audit_plan(
            contact_email="audit@example.org", target_count=target, code_identity=CODE
        )
        view = service.select_audit_samples(
            plan.plan_id, contact_email="audit@example.org", code_identity=CODE
        )
        state = view.sampling[3]
        assert len(state.members) == target and state.shortfall == 0
        assert [item.entry_id for item in state.members] == [
            f"urn:item:{position}" for position in range(12, 12 - target, -1)
        ]
        assert state.entries[0].candidate is not None
        assert state.entries[0].candidate.entry_locator == "item[12]"
        assert state.entries[0].candidate.published_precision == "year"
        assert state.considered == target
        assert all(item.target_count == target for item in view.sampling)
    service.validate_all()


def test_decoded_xml_declarations_are_rejected_for_non_utf_charsets(
    tmp_path: Path,
) -> None:
    import httpx

    class EncodedSources(SamplingSources):
        def __call__(self, request: httpx.Request) -> httpx.Response:
            if str(request.url) == FEED_ENDPOINTS[1].url:
                self.calls.append(str(request.url))
                body = (
                    '<!DOCTYPE rss [<!ENTITY x "expanded">]>'
                    "<rss><channel><title>&x;</title></channel></rss>"
                ).encode("cp037")
                return httpx.Response(
                    200,
                    headers={"Content-Type": "application/rss+xml; charset=cp037"},
                    stream=httpx.ByteStream(body),
                )
            return super().__call__(request)

    sources = EncodedSources()
    service = sampling_service(tmp_path, sources)
    plan = service.create_audit_plan(
        contact_email="audit@example.org", code_identity=CODE
    )
    view = service.select_audit_samples(
        plan.plan_id, contact_email="audit@example.org", code_identity=CODE
    )
    assert view.sampling[1].feed is None
    assert view.sampling[1].status == "blocked_pending"
