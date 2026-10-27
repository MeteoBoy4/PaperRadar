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


@pytest.mark.parametrize("continuing", [False, True], ids=["select", "continue"])
@pytest.mark.parametrize(
    "identity_slot",
    [
        "code_identity",
        "ACQUISITION_STRATEGY_VERSION",
        "CHANNELS_VERSION",
        "HTTP_RULES_VERSION",
        "PARSER_VERSION",
        "SAMPLING_RULES_VERSION",
        "CATEGORY_RULES_VERSION",
        "UA_TEMPLATE_VERSION",
        "ABSTRACT_RULES_VERSION",
        "TRUNCATION_RULES_VERSION",
        "MATRIX_RULES_VERSION",
    ],
)
def test_sampling_checks_full_execution_identity_before_mutation_or_http(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    identity_slot: str,
    continuing: bool,
) -> None:
    import httpx

    from paper_radar.fixture_audit import (
        FixtureError,
        abstract_models,
        acquisition_models,
    )

    class PausedSources(SamplingSources):
        def __call__(self, request: httpx.Request) -> httpx.Response:
            if request.url.host == "journals.ametsoc.org":
                self.calls.append(str(request.url))
                return httpx.Response(503)
            return super().__call__(request)

    sources = PausedSources()
    service = sampling_service(tmp_path, sources)
    plan = service.create_audit_plan(
        contact_email="audit@example.org", code_identity=CODE
    )
    if continuing:
        blocked = service.select_audit_samples(
            plan.plan_id, contact_email="audit@example.org", code_identity=CODE
        )
        assert blocked.sampling[0].status == "blocked_pending"
        assert blocked.sampling[0].history[-1].reason == "feed_unavailable"
    before = service.show_audit(plan.plan_id)
    calls = tuple(sources.calls)
    code = CODE
    if identity_slot == "code_identity":
        code = CODE.model_copy(update={"commit": "9" * 40})
    else:
        module = (
            abstract_models
            if identity_slot
            in {
                "ABSTRACT_RULES_VERSION",
                "TRUNCATION_RULES_VERSION",
                "MATRIX_RULES_VERSION",
            }
            else acquisition_models
        )
        monkeypatch.setattr(module, identity_slot, "changed-version")
    advance = (
        service.continue_audit_sampling if continuing else service.select_audit_samples
    )
    with pytest.raises(FixtureError) as caught:
        advance(plan.plan_id, contact_email="audit@example.org", code_identity=code)
    assert caught.value.reason == "plan_identity_mismatch"
    assert caught.value.path == "code_identity"
    assert tuple(sources.calls) == calls
    assert service.show_audit(plan.plan_id) == before
