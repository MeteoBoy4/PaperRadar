"""通过真实审计公共边界观察有限诊断事件。"""

import json
from pathlib import Path

import pytest

from paper_radar.fixture_audit import FixtureAudit, FixtureError, FixtureReason
from paper_radar.fixture_audit.acquisition_models import SourceRequest
from paper_radar.runtime_logging import FileSink
from tests.audit_matrix_support import MatrixSources
from tests.audit_sampling_support import CODE, sampling_service


def test_audit_execution_emits_correlated_events_after_settlement(
    tmp_path: Path,
) -> None:
    original = sampling_service(tmp_path, MatrixSources())
    assert original.data_root is not None
    sink = FileSink(original.data_root)
    service = FixtureAudit(
        original.database,
        original.data_root,
        source_executors=original.acquisitions.executors,
        sink=sink,
    )
    assert not (original.data_root / "logs").exists()
    result = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    events = [
        json.loads(line)
        for line in (original.data_root / "logs/runtime.jsonl").read_text().splitlines()
    ]
    assert events[0]["event"] == "run_started"
    assert events[-1]["event"] == "run_finished"
    routes = [event for event in events if event["event"] == "route_settled"]
    assert len(routes) == len(result.executions) == 19
    assert {event["run_id"] for event in events} == {events[0]["run_id"]}
    assert {event["plan_id"] for event in routes} == {result.plan.plan_id}
    assert service.show_audit(result.plan.plan_id) == result


def test_audit_resume_has_its_own_execution_envelope(tmp_path: Path) -> None:
    original = sampling_service(tmp_path, MatrixSources())
    assert original.data_root is not None
    service = FixtureAudit(
        original.database,
        original.data_root,
        source_executors=original.acquisitions.executors,
        sink=FileSink(original.data_root),
    )
    result = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    resumed = service.resume_audit(
        result.plan.plan_id, contact_email="audit@example.org", code_identity=CODE
    )
    assert resumed == result
    events = [
        json.loads(line)
        for line in (original.data_root / "logs/runtime.jsonl").read_text().splitlines()
    ]
    assert [value["event"] for value in events[-2:]] == ["run_started", "run_finished"]
    assert events[-1]["run_id"] != events[0]["run_id"]
    assert events[-1]["plan_id"] == result.plan.plan_id


@pytest.mark.parametrize(
    "failure",
    [
        RuntimeError("SECRET_EXCEPTION"),
        KeyboardInterrupt("SECRET_INTERRUPT"),
        SystemExit(19),
    ],
)
def test_audit_source_failure_keeps_unsettled_route_and_safe_events(
    tmp_path: Path, failure: BaseException
) -> None:
    from paper_radar.fixture_audit.source_http import SourceResponse

    class BrokenSource:
        def fetch(
            self, request: SourceRequest, *, contact_email: str
        ) -> SourceResponse:
            raise failure

    original = sampling_service(tmp_path, MatrixSources())
    assert original.data_root is not None
    service = FixtureAudit(
        original.database,
        original.data_root,
        source_executors={"http": BrokenSource()},
        sink=FileSink(original.data_root),
    )
    plan = service.create_audit_plan(
        contact_email="audit@example.org", code_identity=CODE
    )
    if isinstance(failure, Exception):
        with pytest.raises(FixtureError) as error:
            service.acquire_source(
                plan.plan_id,
                request_key="one",
                request=SourceRequest(journal="jgr", route="feed"),
                contact_email="audit@example.org",
            )
        assert error.value.reason == FixtureReason.EXECUTION_INCOMPLETE
    else:
        with pytest.raises(type(failure)) as interruption:
            service.acquire_source(
                plan.plan_id,
                request_key="one",
                request=SourceRequest(journal="jgr", route="feed"),
                contact_email="audit@example.org",
            )
        assert interruption.value is failure
    assert service.show_audit(plan.plan_id).executions[0].settlement is None
    events = [
        json.loads(line)
        for line in (original.data_root / "logs/runtime.jsonl").read_text().splitlines()
    ]
    assert [value["event"] for value in events] == [
        "unexpected_error" if isinstance(failure, Exception) else "interrupted"
    ]
    assert "SECRET" not in (original.data_root / "logs/runtime.jsonl").read_text()


def test_resume_logs_unknown_settlement_before_replacement_route(
    tmp_path: Path,
) -> None:
    import httpx

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

    original = sampling_service(tmp_path, InterruptedSources())
    assert original.data_root is not None
    service = FixtureAudit(
        original.database,
        original.data_root,
        source_executors=original.acquisitions.executors,
        sink=FileSink(original.data_root),
    )
    with pytest.raises(KeyboardInterrupt):
        service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    before = service.list_audits()[0]
    started = next(value for value in before.executions if value.settlement is None)
    result = service.resume_audit(
        before.plan.plan_id, contact_email="audit@example.org", code_identity=CODE
    )
    events = [
        json.loads(line)
        for line in (original.data_root / "logs/runtime.jsonl").read_text().splitlines()
    ]
    routes = [value for value in events if value["event"] == "route_settled"]
    recovered = [
        value for value in routes if value["execution_id"] == started.execution_id
    ]
    assert len(recovered) == 1
    assert recovered[0]["category"] == "outcome_unknown"
    assert len(routes) == len(result.executions)
    assert events[-1]["event"] == "run_finished"
