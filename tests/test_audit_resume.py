"""显式恢复保持冻结成员和已结算历史,只补未结算或暂时路线。"""

from pathlib import Path

import httpx
import pytest

from tests.audit_matrix_support import MatrixSources
from tests.audit_sampling_support import CODE, sampling_service


def test_resume_retries_only_transient_matrix_route_and_keeps_old_result(
    tmp_path: Path,
) -> None:
    class RecoveringSources(MatrixSources):
        recovered = False

        def __call__(self, request: httpx.Request) -> httpx.Response:
            if (
                request.url.host == "agupubs.onlinelibrary.wiley.com"
                and "/doi/" in request.url.path
                and not self.recovered
            ):
                self.calls.append(str(request.url))
                return httpx.Response(503)
            return super().__call__(request)

    sources = RecoveringSources()
    service = sampling_service(tmp_path, sources)
    original = service.run_audit(contact_email="first@example.org", code_identity=CODE)
    old = next(
        row
        for row in original.matrix
        if row.request.journal == "jgr"
        and row.request.route == "publisher"
        and row.request.channel == "http"
    )
    assert old.reason == "transient_error"
    before = tuple(sources.calls)
    sources.recovered = True
    resumed = service.resume_audit(
        original.plan.plan_id, contact_email="second@example.org", code_identity=CODE
    )
    assert resumed.status == "complete"
    assert len(sources.calls) == len(before) + 1
    assert [state.members for state in resumed.sampling] == [
        state.members for state in original.sampling
    ]
    assert len(resumed.matrix) == 19 and len(resumed.matrix_history) == 20
    current = next(
        row
        for row in resumed.matrix
        if row.member_id == old.member_id and row.request == old.request
    )
    assert current.reason == "acquired" and current.previous_row_id == old.row_id
    assert old in resumed.matrix_history
    execution = next(
        value
        for value in resumed.executions
        if value.execution_id == current.acquisition_id
    )
    assert execution.previous_execution_id == old.acquisition_id
    assert (
        service.acquire_source(
            original.plan.plan_id,
            request_key=execution.request_key,
            request=execution.request,
            contact_email="replay@example.org",
            previous_execution_id=execution.previous_execution_id,
        )
        == execution
    )
    count = len(sources.calls)
    assert (
        service.resume_audit(
            original.plan.plan_id, contact_email="third@example.org", code_identity=CODE
        )
        == resumed
    )
    assert len(sources.calls) == count
    service.validate_all()


def test_resume_settles_started_unknown_before_new_execution_without_replacing_members(
    tmp_path: Path,
) -> None:

    class InterruptedSources(MatrixSources):
        armed = True

        def __call__(self, request: httpx.Request) -> httpx.Response:
            if (
                self.armed
                and request.url.host == "agupubs.onlinelibrary.wiley.com"
                and "/doi/" in request.url.path
            ):
                self.armed = False
                raise KeyboardInterrupt
            return super().__call__(request)

    sources = InterruptedSources()
    service = sampling_service(tmp_path, sources)
    with pytest.raises(KeyboardInterrupt):
        service.run_audit(contact_email="first@example.org", code_identity=CODE)
    before = service.list_audits()[0]
    started = next(value for value in before.executions if value.settlement is None)
    resumed = service.resume_audit(
        before.plan.plan_id, contact_email="second@example.org", code_identity=CODE
    )
    previous = next(
        value
        for value in resumed.executions
        if value.execution_id == started.execution_id
    )
    assert previous.reason == "outcome_unknown" and previous.physical_requests is None
    assert any(
        value.previous_execution_id == previous.execution_id
        and value.reason == "acquired"
        for value in resumed.executions
    )
    assert resumed.status == "complete" and len(resumed.matrix) == 19
    assert [state.members for state in resumed.sampling] == [
        state.members for state in before.sampling
    ]
    assert any(
        row.acquisition_id == started.execution_id and row.reason == "outcome_unknown"
        for row in resumed.matrix_history
    )
    service.validate_all()


def test_resume_checks_full_execution_identity_before_any_mutation_or_http(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:

    from paper_radar.fixture_audit import FixtureError, abstract_models

    sources = MatrixSources()
    service = sampling_service(tmp_path, sources)
    original = service.run_audit(contact_email="first@example.org", code_identity=CODE)
    calls = tuple(sources.calls)
    monkeypatch.setattr(
        abstract_models, "TRUNCATION_RULES_VERSION", "audit-truncation-v2"
    )
    with pytest.raises(FixtureError) as caught:
        service.resume_audit(
            original.plan.plan_id,
            contact_email="second@example.org",
            code_identity=CODE,
        )
    assert caught.value.reason == "plan_identity_mismatch"
    assert tuple(sources.calls) == calls
    assert service.show_audit(original.plan.plan_id) == original


def test_resume_preserves_failed_sampling_source_chain_and_original_position(
    tmp_path: Path,
) -> None:
    class SamplingFailure(MatrixSources):
        recovered = False

        def __call__(self, request: httpx.Request) -> httpx.Response:
            if (
                request.url.path == "/doiRA/10.1029/jgr.synthetic"
                and not self.recovered
            ):
                self.calls.append(str(request.url))
                return httpx.Response(503)
            return super().__call__(request)

    sources = SamplingFailure()
    service = sampling_service(tmp_path, sources)
    before = service.run_audit(contact_email="first@example.org", code_identity=CODE)
    assert before.sampling[1].status == "blocked_pending"
    assert before.sampling[1].next_position == 1
    sources.recovered = True
    after = service.resume_audit(
        before.plan.plan_id, contact_email="second@example.org", code_identity=CODE
    )
    assert after.status == "complete"
    assert after.sampling[1].members[0].doi == "10.1029/jgr.synthetic"
    assert [event.result for event in after.sampling[1].history] == [
        "blocked_pending",
        "selected",
    ]
    roots = [
        value
        for value in after.executions
        if value.request.journal == "jgr" and value.request.route == "doi_ra"
    ]
    assert len(roots) == 2 and roots[1].previous_execution_id == roots[0].execution_id
    service.replay_audit(before.plan.plan_id)


def test_replay_rejects_removed_sampling_execution_predecessor(
    tmp_path: Path,
) -> None:
    import sqlite3
    from contextlib import closing

    from paper_radar.fixture_audit import FixtureError

    class Recovering(MatrixSources):
        recovered = False

        def __call__(self, request: httpx.Request) -> httpx.Response:
            if (
                request.url.path == "/doiRA/10.1029/jgr.synthetic"
                and not self.recovered
            ):
                return httpx.Response(503)
            return super().__call__(request)

    sources = Recovering()
    service = sampling_service(tmp_path, sources)
    original = service.run_audit(contact_email="first@example.org", code_identity=CODE)
    sources.recovered = True
    resumed = service.resume_audit(
        original.plan.plan_id, contact_email="second@example.org", code_identity=CODE
    )
    child = next(value for value in resumed.executions if value.previous_execution_id)
    with closing(sqlite3.connect(service.database)) as connection:
        connection.execute(
            "UPDATE audit_route_starts SET previous_execution_id=NULL "
            "WHERE execution_id=?",
            (child.execution_id,),
        )
        connection.commit()
    with pytest.raises(FixtureError) as caught:
        service.replay_audit(original.plan.plan_id)
    assert caught.value.reason == "corrupt_reference"
    assert caught.value.path == "audit.continuation"


def test_active_retry_is_partial_and_keeps_old_settlement_as_history(
    tmp_path: Path,
) -> None:
    class PhasedSources(MatrixSources):
        phase = "failed"

        def __call__(self, request: httpx.Request) -> httpx.Response:
            if (
                request.url.host == "agupubs.onlinelibrary.wiley.com"
                and "/doi/" in request.url.path
            ):
                if self.phase == "failed":
                    return httpx.Response(503)
                if self.phase == "interrupted":
                    raise KeyboardInterrupt
            return super().__call__(request)

    sources = PhasedSources()
    service = sampling_service(tmp_path, sources)
    original = service.run_audit(contact_email="first@example.org", code_identity=CODE)
    sources.phase = "interrupted"
    with pytest.raises(KeyboardInterrupt):
        service.resume_audit(
            original.plan.plan_id,
            contact_email="second@example.org",
            code_identity=CODE,
        )
    partial = service.show_audit(original.plan.plan_id)
    assert partial.status == "partial"
    current = next(
        row
        for row in partial.matrix
        if row.request.journal == "jgr"
        and row.request.route == "publisher"
        and row.request.channel == "http"
    )
    assert current.reason == "outcome_unknown"
    assert partial.matrix_history == original.matrix_history
    assert service.replay_audit(original.plan.plan_id).view == partial
    sources.phase = "recovered"
    finished = service.resume_audit(
        original.plan.plan_id, contact_email="third@example.org", code_identity=CODE
    )
    assert finished.status == "complete"
    assert len(finished.matrix_history) == 21


def test_complete_plan_rejects_fresh_acquisition_keys_but_replays_exact_execution(
    tmp_path: Path,
) -> None:
    from paper_radar.fixture_audit import FixtureError

    sources = MatrixSources()
    service = sampling_service(tmp_path, sources)
    original = service.run_audit(contact_email="first@example.org", code_identity=CODE)
    existing = next(
        value
        for value in original.executions
        if value.request.journal == "jgr"
        and value.request.route == "publisher"
        and value.request.channel == "http"
    )
    calls = tuple(sources.calls)
    assert (
        service.acquire_source(
            original.plan.plan_id,
            request_key=existing.request_key,
            request=existing.request,
            contact_email="second@example.org",
        )
        == existing
    )
    feed = next(
        value
        for value in original.executions
        if value.request.journal == "jgr" and value.request.route == "feed"
    )
    for value in (existing, feed):
        with pytest.raises(FixtureError) as settled:
            service.acquire_source(
                original.plan.plan_id,
                request_key=f"fresh-key-{value.request.route}",
                request=value.request,
                contact_email="second@example.org",
            )
        assert settled.value.reason == "route_already_settled"
    assert service.show_audit(original.plan.plan_id) == original
    assert tuple(sources.calls) == calls


def test_repeated_unidentified_candidate_reuses_verified_publisher_material(
    tmp_path: Path,
) -> None:
    sources = MatrixSources()
    for url, raw in list(sources.feeds.items()):
        if "journalissuetocrss" in url:
            item = raw.split(b"<item>")[1].split(b"</item>")[0]
            sources.feeds[url] = raw.replace(
                b"</channel>", b"<item>" + item + b"</item></channel>"
            )
    service = sampling_service(tmp_path, sources)
    view = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    assert [entry.result for entry in view.sampling[0].entries] == [
        "selected",
        "excluded_deterministic",
    ]
    assert view.sampling[0].entries[1].reason == "duplicate"
    assert sum("/view/journals/aies/" in url for url in sources.calls) == 1
    assert view.status == "complete"
