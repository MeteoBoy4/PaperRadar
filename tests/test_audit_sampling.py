"""公共选样服务:四刊原位次、显式类型、不可变成员和暂停继续。"""

from pathlib import Path

import pytest

from tests.audit_sampling_support import CODE, SamplingSources, sampling_service


def test_four_journals_freeze_explicit_members_without_abstract_filtering(
    tmp_path: Path,
) -> None:
    sources = SamplingSources()
    service = sampling_service(tmp_path, sources)
    plan = service.create_audit_plan(
        contact_email="audit@example.org", code_identity=CODE
    )
    result = service.select_audit_samples(
        plan.plan_id, contact_email="audit@example.org", code_identity=CODE
    )
    assert [
        (journal.journal, journal.status, len(journal.members), journal.shortfall)
        for journal in result.sampling
    ] == [
        ("aies", "complete", 1, 4),
        ("jgr", "complete", 1, 4),
        ("qjrms", "complete", 1, 4),
        ("dqkx", "complete", 1, 4),
    ]
    assert [journal.members[0].doi for journal in result.sampling] == [
        "10.1175/aies.synthetic",
        "10.1029/jgr.synthetic",
        "10.1002/qj.synthetic",
        "10.3878/dqkx.synthetic",
    ]
    assert result.sampling[0].members[0].entry_id is None
    assert result.sampling[1].entries[0].candidate is not None
    assert [
        category.value
        for category in result.sampling[1].entries[0].candidate.raw_categories
    ] == ["EDITORIAL", "ISSUE INFORMATION"]
    assert result.sampling[1].entries[0].result == "selected"
    assert result.sampling[3].entries[0].routes[0].reason == "agency_unsupported"
    before_calls = tuple(sources.calls)
    assert (
        service.select_audit_samples(
            plan.plan_id, contact_email="audit@example.org", code_identity=CODE
        )
        == result
    )
    assert tuple(sources.calls) == before_calls
    assert service.show_audit(plan.plan_id) == result
    service.validate_all()


def test_temporary_failure_pauses_position_and_continues_other_journals(
    tmp_path: Path,
) -> None:
    import httpx

    class FlakySources(SamplingSources):
        recovered = False

        def __call__(self, request: httpx.Request) -> httpx.Response:
            if (
                request.url.path == "/doiRA/10.1029/jgr.synthetic"
                and not self.recovered
            ):
                self.calls.append(str(request.url))
                return httpx.Response(429, headers={"Retry-After": "0"})
            return super().__call__(request)

    sources = FlakySources()
    service = sampling_service(tmp_path, sources)
    plan = service.create_audit_plan(
        contact_email="audit@example.org", code_identity=CODE
    )
    blocked = service.select_audit_samples(
        plan.plan_id, contact_email="audit@example.org", code_identity=CODE
    )
    assert [item.status for item in blocked.sampling] == [
        "complete",
        "blocked_pending",
        "complete",
        "complete",
    ]
    assert blocked.sampling[1].next_position == 1
    assert blocked.sampling[1].entries[0].result == "blocked_pending"
    assert blocked.sampling[1].entries[0].routes[0].reason == "agency_unknown"
    before = tuple(sources.calls)
    assert (
        service.select_audit_samples(
            plan.plan_id, contact_email="audit@example.org", code_identity=CODE
        )
        == blocked
    )
    assert tuple(sources.calls) == before
    sources.recovered = True
    sources.feeds = {
        url: body.replace(b"jgr.synthetic", b"replacement-not-selected")
        for url, body in sources.feeds.items()
    }
    complete = service.continue_audit_sampling(
        plan.plan_id, contact_email="audit@example.org", code_identity=CODE
    )
    assert [item.status for item in complete.sampling] == ["complete"] * 4
    assert complete.sampling[1].members[0].doi == "10.1029/jgr.synthetic"
    assert [item.feed for item in complete.sampling] == [
        item.feed for item in blocked.sampling
    ]
    assert [event.result for event in complete.sampling[1].history] == [
        "blocked_pending",
        "selected",
    ]
    assert sum(url in sources.feeds for url in sources.calls) == 4
    assert [item.members for item in complete.sampling if item.journal != "jgr"] == [
        item.members for item in blocked.sampling if item.journal != "jgr"
    ]
    service.validate_all()


def test_explicit_sampling_continue_settles_unknown_before_new_route(
    tmp_path: Path,
) -> None:
    import httpx
    import pytest

    class InterruptedSources(SamplingSources):
        armed = True

        def __call__(self, request: httpx.Request) -> httpx.Response:
            if request.url.path == "/doiRA/10.1029/jgr.synthetic" and self.armed:
                self.armed = False
                raise KeyboardInterrupt
            return super().__call__(request)

    sources = InterruptedSources()
    service = sampling_service(tmp_path, sources)
    plan = service.create_audit_plan(
        contact_email="audit@example.org", code_identity=CODE
    )
    with pytest.raises(KeyboardInterrupt):
        service.select_audit_samples(
            plan.plan_id, contact_email="audit@example.org", code_identity=CODE
        )
    blocked = service.select_audit_samples(
        plan.plan_id, contact_email="audit@example.org", code_identity=CODE
    )
    assert blocked.sampling[1].entries[0].routes[0].reason == "outcome_unknown"
    old_route = next(item for item in blocked.executions if item.settlement is None)
    assert old_route.physical_requests is None
    complete = service.continue_audit_sampling(
        plan.plan_id, contact_email="audit@example.org", code_identity=CODE
    )
    assert [item.status for item in complete.sampling] == ["complete"] * 4
    original = next(
        item
        for item in complete.executions
        if item.execution_id == old_route.execution_id
    )
    assert original.reason == "outcome_unknown" and original.physical_requests is None
    assert complete.sampling[1].members[0].doi == "10.1029/jgr.synthetic"
    service.validate_all()


def test_plan_freezes_sampling_rules_and_rejects_changed_execution_before_http(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import pytest

    from paper_radar.fixture_audit import FixtureError
    from paper_radar.fixture_audit import sampling_service as sampling_module

    sources = SamplingSources()
    service = sampling_service(tmp_path, sources)
    plan = service.create_audit_plan(
        contact_email="audit@example.org", code_identity=CODE
    )
    assert plan.sampling_rules_version == "audit-sampling-v1"
    assert plan.category_rules_version == "audit-category-v1"
    monkeypatch.setattr(sampling_module, "CATEGORY_RULES_VERSION", "audit-category-v2")
    with pytest.raises(FixtureError) as caught:
        service.select_audit_samples(
            plan.plan_id, contact_email="audit@example.org", code_identity=CODE
        )
    assert caught.value.reason == "plan_identity_mismatch"
    assert sources.calls == []
