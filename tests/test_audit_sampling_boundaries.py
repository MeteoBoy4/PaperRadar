"""固定选样分母、原位次与输入变体不改变成员的公共边界。"""

from pathlib import Path

from paper_radar.fixture_audit.acquisition_policy import FEED_ENDPOINTS
from tests.audit_sampling_support import CODE, SamplingSources, sampling_service


def test_fifty_raw_positions_include_duplicates_and_do_not_renumber(
    tmp_path: Path,
) -> None:
    sources = SamplingSources()
    items = []
    for position in range(1, 52):
        identity = "urn:first" if position in (48, 49) else f"urn:synthetic:{position}"
        kind = "article" if position >= 48 else "not-registered"
        items.append(
            f'<item rdf:about="{identity}"><dc:type>{kind}</dc:type>'
            "<dc:date>2026-10</dc:date></item>"
        )
    raw = (
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:dc="http://purl.org/dc/elements/1.1/"><channel/><items/>'
        + "".join(items)
        + "</rdf:RDF>"
    ).encode()
    sources.feeds[FEED_ENDPOINTS[3].url] = raw
    service = sampling_service(tmp_path, sources)
    plan = service.create_audit_plan(
        contact_email="audit@example.org", code_identity=CODE
    )
    view = service.select_audit_samples(
        plan.plan_id, contact_email="audit@example.org", code_identity=CODE
    )
    state = view.sampling[3]
    assert state.status == "complete" and state.total_candidates == 51
    assert state.considered == 50 and state.shortfall == 3
    assert [member.position for member in state.members] == [48, 50]
    assert state.entries[48].reason == "duplicate" and state.entries[48].position == 49
    assert sum(entry.reason == "category_unknown" for entry in state.entries) == 47
    assert state.entries[0].candidate is not None
    assert state.entries[0].candidate.published_precision == "month"
    assert not any("urn:" in call for call in sources.calls)
    service.validate_all()


def test_same_doi_across_journals_is_not_a_global_deduplication_key(
    tmp_path: Path,
) -> None:
    sources = SamplingSources()
    sources.feeds[FEED_ENDPOINTS[2].url] = sources.feeds[FEED_ENDPOINTS[2].url].replace(
        b"10.1002/qj.synthetic", b"10.1029/jgr.synthetic"
    )
    service = sampling_service(tmp_path, sources)
    plan = service.create_audit_plan(
        contact_email="audit@example.org", code_identity=CODE
    )
    view = service.select_audit_samples(
        plan.plan_id, contact_email="audit@example.org", code_identity=CODE
    )
    assert [state.members[0].doi for state in view.sampling[1:3]] == [
        "10.1029/jgr.synthetic",
        "10.1029/jgr.synthetic",
    ]
    assert (
        view.sampling[1].members[0].member_id != view.sampling[2].members[0].member_id
    )
    service.validate_all()


def test_doi_wrappers_deduplicate_but_opaque_entry_ids_are_preserved(
    tmp_path: Path,
) -> None:
    sources = SamplingSources()
    sources.feeds[FEED_ENDPOINTS[1].url] = (
        b"<rss><channel><item><guid>10.1029/jgr.synthetic</guid></item>"
        b"<item><guid>https://doi.org/10.1029/JGR.SYNTHETIC</guid></item>"
        b"<item><guid> urn:opaque-stable-id </guid>"
        b"<category>Research Article</category></item></channel></rss>"
    )
    service = sampling_service(tmp_path, sources)
    plan = service.create_audit_plan(
        contact_email="audit@example.org", code_identity=CODE
    )
    state = service.select_audit_samples(
        plan.plan_id, contact_email="audit@example.org", code_identity=CODE
    ).sampling[1]
    assert [entry.reason for entry in state.entries] == [
        "selected",
        "duplicate",
        "category_unknown",
    ]
    assert state.entries[2].candidate is not None
    assert state.entries[2].candidate.entry_id == " urn:opaque-stable-id "
    assert state.members[0].doi == "10.1029/jgr.synthetic"
    service.validate_all()


def test_abstract_presence_length_and_truncation_do_not_change_selected_identities(
    tmp_path: Path,
) -> None:
    selected = []
    for index, description in enumerate(
        (b"", b"...", b"A complete abstract sentence. " * 40)
    ):
        root = tmp_path / str(index)
        root.mkdir()
        sources = SamplingSources()
        sources.feeds = {
            url: raw.replace(b"short", description).replace(
                b"synthetic summary", description
            )
            for url, raw in sources.feeds.items()
        }
        service = sampling_service(root, sources)
        plan = service.create_audit_plan(
            contact_email="audit@example.org", code_identity=CODE
        )
        view = service.select_audit_samples(
            plan.plan_id, contact_email="audit@example.org", code_identity=CODE
        )
        selected.append(
            [
                (
                    state.journal,
                    [
                        (item.position, item.doi, item.entry_id)
                        for item in state.members
                    ],
                )
                for state in view.sampling
            ]
        )
    assert selected[0] == selected[1] == selected[2]


def test_empty_rdf_about_cannot_supply_a_stable_identifier(tmp_path: Path) -> None:
    sources = SamplingSources()
    sources.feeds[FEED_ENDPOINTS[3].url] = (
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" '
        b'xmlns:dc="http://purl.org/dc/elements/1.1/"><channel/>'
        b'<item rdf:about=" "><dc:type>article</dc:type></item></rdf:RDF>'
    )
    service = sampling_service(tmp_path, sources)
    plan = service.create_audit_plan(
        contact_email="audit@example.org", code_identity=CODE
    )
    state = service.select_audit_samples(
        plan.plan_id, contact_email="audit@example.org", code_identity=CODE
    ).sampling[3]
    assert state.members == ()
    assert state.entries[0].reason == "no_stable_identifier"
