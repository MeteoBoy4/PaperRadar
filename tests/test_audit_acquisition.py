"""通过公共审计服务验证计划、来源取得及只读历史。"""

from pathlib import Path

import pytest

from paper_radar.fixture_audit import FixtureAudit, FixtureError
from paper_radar.fixture_audit.acquisition_models import CodeIdentity, SourceRequest
from paper_radar.storage.database import upgrade_database


def test_uninstalled_channel_is_a_frozen_zero_request_result(tmp_path: Path) -> None:
    database = tmp_path / "facts.sqlite3"
    upgrade_database(database)
    service = FixtureAudit(database, tmp_path / "data")
    plan = service.create_audit_plan(
        contact_email="audit@example.org",
        plan_key="first-plan",
        code_identity=CodeIdentity(commit="a" * 40, dirty=False, basis="synthetic"),
    )
    result = service.acquire_source(
        plan.plan_id,
        request_key="feed-aies-render",
        request=SourceRequest(journal="aies", route="feed", channel="browser_render"),
        contact_email="audit@example.org",
    )
    assert plan.target_count == 5
    assert [endpoint.journal for endpoint in plan.endpoints] == [
        "aies",
        "jgr",
        "qjrms",
        "dqkx",
    ]
    assert result.reason == "channel_not_installed"
    assert result.physical_requests == 0
    assert result.is_failure is False
    assert service.show_audit(plan.plan_id).executions == (result,)
    assert service.list_audits()[0].plan == plan
    assert "audit@example.org" not in repr((plan, result))


def test_valid_feed_acquisition_retains_bytes_and_replays_without_transport(
    tmp_path: Path,
) -> None:
    import httpx

    from paper_radar.fixture_audit.source_http import SourceHTTPExecutor
    from paper_radar.storage.artifacts import ArtifactStore

    raw = b"<rss><channel><title>fixed feed</title></channel></rss>"
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, stream=httpx.ByteStream(raw))

    database = tmp_path / "facts.sqlite3"
    upgrade_database(database)
    service = FixtureAudit(
        database,
        tmp_path / "data",
        source_executors={
            "http": SourceHTTPExecutor(transport=httpx.MockTransport(handler))
        },
    )
    plan = service.create_audit_plan(
        contact_email="audit@example.org", code_identity=CodeIdentity(basis="synthetic")
    )
    request = SourceRequest(journal="aies", route="feed")
    result = service.acquire_source(
        plan.plan_id,
        request_key="feed",
        request=request,
        contact_email="audit@example.org",
    )
    assert result.reason == "acquired"
    assert result.physical_requests == 1
    assert result.settlement is not None and result.settlement.artifact_id is not None
    assert (
        ArtifactStore(database, tmp_path / "data").read_artifact(
            result.settlement.artifact_id
        )["payload"]
        == raw
    )
    assert (
        service.acquire_source(
            plan.plan_id,
            request_key="feed",
            request=request,
            contact_email="audit@example.org",
        )
        == result
    )
    assert len(calls) == 1
    service.validate_all()


def test_conditional_hit_reuses_only_previously_verified_matching_material(
    tmp_path: Path,
) -> None:
    import httpx

    from paper_radar.fixture_audit.models import ConditionalHeaders
    from paper_radar.fixture_audit.source_http import SourceHTTPExecutor
    from paper_radar.storage.artifacts import ArtifactStore

    count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal count
        count += 1
        if count == 1:
            return httpx.Response(
                200, stream=httpx.ByteStream(b"<rss><channel/></rss>")
            )
        assert request.headers["if-none-match"] == '"revision-one"'
        return httpx.Response(304)

    database = tmp_path / "facts.sqlite3"
    upgrade_database(database)
    service = FixtureAudit(
        database,
        tmp_path / "data",
        source_executors={
            "http": SourceHTTPExecutor(transport=httpx.MockTransport(handler))
        },
    )
    plan = service.create_audit_plan(
        contact_email="audit@example.org", code_identity=CodeIdentity(basis="synthetic")
    )
    first = service.acquire_source(
        plan.plan_id,
        request_key="original",
        request=SourceRequest(journal="aies", route="feed"),
        contact_email="audit@example.org",
    )
    assert first.settlement is not None
    second = service.acquire_source(
        plan.plan_id,
        request_key="conditional",
        request=SourceRequest(
            journal="aies",
            route="feed",
            conditional_headers=ConditionalHeaders(
                if_none_match='"revision-one"',
                prior_artifact_id=first.settlement.artifact_id,
            ),
        ),
        contact_email="audit@example.org",
    )
    assert second.reason == "acquired"
    assert second.settlement is not None
    assert second.settlement.reused_prior is True
    assert second.settlement.artifact_id == first.settlement.artifact_id
    assert len(ArtifactStore(database, tmp_path / "data").list_artifacts()) == 1
    service.validate_all()


@pytest.mark.parametrize(
    "contact", [None, "", "not-an-email", "user@example.org\r\nCookie: secret"]
)
def test_invalid_contact_cannot_create_even_a_plan(
    tmp_path: Path, contact: str | None
) -> None:
    service = FixtureAudit(tmp_path / "absent.sqlite3", tmp_path / "absent-data")
    with pytest.raises(FixtureError) as caught:
        service.create_audit_plan(contact_email=contact)
    assert caught.value.reason == "invalid_contact"
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("target", [4, 11, True])
def test_target_count_is_one_strict_plan_value(tmp_path: Path, target: int) -> None:
    database = tmp_path / "facts.sqlite3"
    upgrade_database(database)
    service = FixtureAudit(database, tmp_path / "data")
    with pytest.raises(FixtureError) as caught:
        service.create_audit_plan(
            contact_email="audit@example.org",
            target_count=target,
            code_identity=CodeIdentity(basis="synthetic"),
        )
    assert caught.value.reason == "invalid_plan"
    assert service.list_audits() == ()


def test_request_and_plan_keys_reject_changed_strategy_channel_and_contents(
    tmp_path: Path,
) -> None:
    database = tmp_path / "facts.sqlite3"
    upgrade_database(database)
    service = FixtureAudit(database, tmp_path / "data")
    plan = service.create_audit_plan(
        contact_email="audit@example.org",
        plan_key="frozen",
        code_identity=CodeIdentity(basis="synthetic"),
    )
    assert (
        service.create_audit_plan(
            contact_email="audit@example.org",
            plan_key="frozen",
            code_identity=CodeIdentity(basis="synthetic"),
        )
        == plan
    )
    with pytest.raises(FixtureError) as caught:
        service.create_audit_plan(
            contact_email="audit@example.org",
            plan_key="frozen",
            target_count=10,
            code_identity=CodeIdentity(basis="synthetic"),
        )
    assert caught.value.reason == "plan_conflict"
    service.acquire_source(
        plan.plan_id,
        request_key="same",
        request=SourceRequest(journal="jgr", route="feed", channel="browser_render"),
        contact_email="audit@example.org",
    )
    for request in (
        SourceRequest(journal="jgr", route="feed", channel="repository"),
        SourceRequest(journal="qjrms", route="feed", channel="browser_render"),
        SourceRequest(
            journal="jgr",
            route="feed",
            channel="browser_render",
            acquisition_strategy_version="different-v2",
        ),
    ):
        with pytest.raises(FixtureError) as caught:
            service.acquire_source(
                plan.plan_id,
                request_key="same",
                request=request,
                contact_email="audit@example.org",
            )
        assert caught.value.reason == "request_conflict"
    assert len(service.show_audit(plan.plan_id).executions) == 1


def test_plan_lock_is_outside_data_root_and_reading_never_waits(tmp_path: Path) -> None:
    database = tmp_path / "data" / "facts.sqlite3"
    database.parent.mkdir()
    upgrade_database(database)
    service = FixtureAudit(database, database.parent)
    plan = service.create_audit_plan(
        contact_email="audit@example.org", code_identity=CodeIdentity(basis="synthetic")
    )
    with service.audit_execution(plan.plan_id) as guard:
        assert service.show_audit(plan.plan_id).plan == plan
        with (
            pytest.raises(FixtureError) as caught,
            FixtureAudit(database.resolve(), database.parent).audit_execution(
                plan.plan_id
            ),
        ):
            pass
        assert caught.value.reason == "execution_busy"
        result = service.acquire_source(
            plan.plan_id,
            request_key="render",
            request=SourceRequest(
                journal="jgr", route="feed", channel="browser_render"
            ),
            contact_email="audit@example.org",
            protection=guard,
        )
        assert result.reason == "channel_not_installed"
    assert not (database.parent / ".paper-radar-audit-locks").exists()
    assert list((tmp_path / ".paper-radar-audit-locks").rglob("*.lock"))
    with service.audit_execution(plan.plan_id):
        pass


def test_cancelled_executor_leaves_started_with_unknown_request_count(
    tmp_path: Path,
) -> None:
    from paper_radar.fixture_audit.source_http import SourceResponse

    class CancelledExecutor:
        def fetch(
            self, request: SourceRequest, *, contact_email: str
        ) -> SourceResponse:
            raise KeyboardInterrupt

    database = tmp_path / "facts.sqlite3"
    upgrade_database(database)
    service = FixtureAudit(
        database, tmp_path / "data", source_executors={"http": CancelledExecutor()}
    )
    plan = service.create_audit_plan(
        contact_email="audit@example.org", code_identity=CodeIdentity(basis="synthetic")
    )
    with pytest.raises(KeyboardInterrupt):
        service.acquire_source(
            plan.plan_id,
            request_key="interrupted",
            request=SourceRequest(journal="jgr", route="feed"),
            contact_email="audit@example.org",
        )
    execution = service.show_audit(plan.plan_id).executions[0]
    assert execution.settlement is None
    assert execution.physical_requests is None
    with pytest.raises(FixtureError) as caught:
        service.acquire_source(
            plan.plan_id,
            request_key="interrupted",
            request=SourceRequest(journal="jgr", route="feed"),
            contact_email="audit@example.org",
        )
    assert caught.value.reason == "execution_incomplete"


@pytest.mark.parametrize(
    "source_request,body,reason,retained",
    [
        (
            SourceRequest(journal="aies", route="feed"),
            b"<html><form id='challenge-form'></form></html>",
            "invalid_response",
            False,
        ),
        (
            SourceRequest(journal="aies", route="feed"),
            b"<!DOCTYPE rss [<!ENTITY secret 'value'>]><rss><channel/></rss>",
            "invalid_response",
            False,
        ),
        (
            SourceRequest(journal="jgr", route="publisher", doi="10.1029/example"),
            b'<html><meta name="citation_doi" content="10.1029/other"></html>',
            "identity_mismatch",
            False,
        ),
        (
            SourceRequest(journal="jgr", route="publisher", doi="10.1029/example"),
            b'<html><meta name="citation_doi" content="10.1029/example"></html>',
            "acquired",
            True,
        ),
        (
            SourceRequest(
                journal="jgr", route="registry_crossref", doi="10.1029/example"
            ),
            b'{"message":{"DOI":"10.1029/example"}}',
            "acquired",
            True,
        ),
        (
            SourceRequest(
                journal="jgr", route="registry_crossref", doi="10.1029/example"
            ),
            b'{"message":{"DOI":"10.1029/other"}}',
            "identity_mismatch",
            False,
        ),
        (
            SourceRequest(journal="dqkx", route="doi_ra", doi="10.3878/example"),
            b'[{"DOI":"10.3878/example","RA":"ISTIC"}]',
            "agency_unsupported",
            False,
        ),
    ],
)
def test_only_valid_feed_or_verified_contributing_identity_is_retained(
    tmp_path: Path,
    source_request: SourceRequest,
    body: bytes,
    reason: str,
    retained: bool,
) -> None:
    import httpx

    from paper_radar.fixture_audit.source_http import SourceHTTPExecutor
    from paper_radar.storage.artifacts import ArtifactStore

    database = tmp_path / "facts.sqlite3"
    upgrade_database(database)
    service = FixtureAudit(
        database,
        tmp_path / "data",
        source_executors={
            "http": SourceHTTPExecutor(
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(200, stream=httpx.ByteStream(body))
                )
            )
        },
    )
    plan = service.create_audit_plan(
        contact_email="audit@example.org", code_identity=CodeIdentity(basis="synthetic")
    )
    result = service.acquire_source(
        plan.plan_id,
        request_key="source",
        request=source_request,
        contact_email="audit@example.org",
    )
    assert result.reason == reason
    assert bool(ArtifactStore(database, tmp_path / "data").list_artifacts()) is retained
    if reason == "agency_unsupported":
        assert result.is_failure is False
        assert result.settlement is not None and result.settlement.agency == "ISTIC"
    service.validate_all()


def test_registered_stub_channel_is_dispatched_and_not_attempted_stays_distinct(
    tmp_path: Path,
) -> None:
    from paper_radar.fixture_audit.acquisition_models import HTTPFacts
    from paper_radar.fixture_audit.source_http import SourceResponse

    class StubExecutor:
        def __init__(self) -> None:
            self.calls = 0

        def fetch(
            self, request: SourceRequest, *, contact_email: str
        ) -> SourceResponse:
            self.calls += 1
            return SourceResponse(HTTPFacts(reason="not_attempted"))

    database = tmp_path / "facts.sqlite3"
    upgrade_database(database)
    stub = StubExecutor()
    service = FixtureAudit(
        database, tmp_path / "data", source_executors={"browser_render": stub}
    )
    plan = service.create_audit_plan(
        contact_email="audit@example.org", code_identity=CodeIdentity(basis="synthetic")
    )
    result = service.acquire_source(
        plan.plan_id,
        request_key="available",
        request=SourceRequest(journal="jgr", route="feed", channel="browser_render"),
        contact_email="audit@example.org",
    )
    unavailable = service.acquire_source(
        plan.plan_id,
        request_key="absent",
        request=SourceRequest(journal="jgr", route="feed", channel="repository"),
        contact_email="audit@example.org",
    )
    assert stub.calls == 1
    assert result.reason == "not_attempted" and result.is_failure is False
    assert (
        unavailable.reason == "channel_not_installed"
        and unavailable.is_failure is False
    )
    assert result.physical_requests == unavailable.physical_requests == 0


def test_conditional_header_without_matching_material_is_rejected_before_http(
    tmp_path: Path,
) -> None:
    import httpx

    from paper_radar.fixture_audit.models import ConditionalHeaders
    from paper_radar.fixture_audit.source_http import SourceHTTPExecutor

    def forbidden(request: httpx.Request) -> httpx.Response:
        pytest.fail("invalid cache reference must not issue HTTP")

    database = tmp_path / "facts.sqlite3"
    upgrade_database(database)
    service = FixtureAudit(
        database,
        tmp_path / "data",
        source_executors={
            "http": SourceHTTPExecutor(transport=httpx.MockTransport(forbidden))
        },
    )
    plan = service.create_audit_plan(
        contact_email="audit@example.org", code_identity=CodeIdentity(basis="synthetic")
    )
    for prior in (None, "a" * 64):
        with pytest.raises(FixtureError) as caught:
            service.acquire_source(
                plan.plan_id,
                request_key="invalid",
                request=SourceRequest(
                    journal="aies",
                    route="feed",
                    conditional_headers=ConditionalHeaders(
                        if_none_match='"unknown"', prior_artifact_id=prior
                    ),
                ),
                contact_email="audit@example.org",
            )
        assert caught.value.reason == "invalid_reference"
    assert service.show_audit(plan.plan_id).executions == ()


@pytest.mark.parametrize("boundary", ["request", "code_identity"])
def test_model_copy_cannot_bypass_validation_or_emit_secret_warnings(
    tmp_path: Path, boundary: str
) -> None:
    import warnings

    database = tmp_path / "facts.sqlite3"
    upgrade_database(database)
    service = FixtureAudit(database, tmp_path / "data")
    with warnings.catch_warnings(record=True) as emitted:
        warnings.simplefilter("always")
        with pytest.raises(FixtureError) as caught:
            if boundary == "code_identity":
                service.create_audit_plan(
                    contact_email="audit@example.org",
                    code_identity=CodeIdentity(basis="synthetic").model_copy(
                        update={"package_version": ["secret-identity"]}
                    ),
                )
            else:
                plan = service.create_audit_plan(
                    contact_email="audit@example.org",
                    code_identity=CodeIdentity(basis="synthetic"),
                )
                service.acquire_source(
                    plan.plan_id,
                    request_key="invalid",
                    request=SourceRequest(journal="jgr", route="feed").model_copy(
                        update={"channel": ["secret-channel"]}
                    ),
                    contact_email="audit@example.org",
                )
        assert caught.value.reason == (
            "invalid_plan" if boundary == "code_identity" else "invalid_request"
        )
        assert "secret" not in str(caught.value)
        assert emitted == []
