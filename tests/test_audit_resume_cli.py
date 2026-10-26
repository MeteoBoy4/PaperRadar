"""resume 明示联网写入,replay 只读并披露证明等级。"""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from paper_radar.cli import app
from paper_radar.fixture_audit import FixtureAudit
from tests.audit_matrix_support import MatrixSources
from tests.audit_sampling_support import CODE, sampling_service


def test_resume_and_replay_help_are_local_and_missing_contact_is_safe(
    tmp_path: Path,
) -> None:
    runner = CliRunner()
    for command, marker in [("resume", "联网"), ("replay", "只读")]:
        value = runner.invoke(app, ["audit", command, "--help"])
        assert value.exit_code == 0 and marker in value.output
    service = sampling_service(tmp_path, MatrixSources())
    plan = service.create_audit_plan(
        contact_email="audit@example.org", code_identity=CODE
    )
    value = runner.invoke(
        app,
        [
            "audit",
            "resume",
            plan.plan_id,
            "--database",
            str(service.database),
            "--data-root",
            str(service.data_root),
        ],
    )
    assert value.exit_code == 1 and "invalid_contact" in value.output
    assert FixtureAudit(service.database).show_audit(plan.plan_id).executions == ()


def test_replay_cli_uses_retained_material_and_safe_proof_projection(
    tmp_path: Path,
) -> None:
    service = sampling_service(tmp_path, MatrixSources())
    value = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    result = CliRunner().invoke(
        app,
        [
            "audit",
            "replay",
            value.plan.plan_id,
            "--database",
            str(service.database),
            "--data-root",
            str(service.data_root),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    projection = json.loads(result.stdout)
    assert projection["status"] == "verified"
    assert len(projection["proofs"]) == 19
    assert "audit@example.org" not in result.output


def test_cli_resume_retries_one_transient_route_with_new_explicit_contact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import httpx

    from paper_radar.fixture_audit import acquisition_service
    from paper_radar.fixture_audit.source_http import SourceHTTPExecutor
    from tests.audit_sampling_support import SamplingClock

    class Recovering(MatrixSources):
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

    sources = Recovering()
    clock = SamplingClock()
    executor = SourceHTTPExecutor(
        transport=httpx.MockTransport(sources),
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )
    monkeypatch.setattr(acquisition_service, "SourceHTTPExecutor", lambda: executor)
    service = sampling_service(tmp_path, sources)
    runner = CliRunner()
    original = runner.invoke(
        app,
        [
            "audit",
            "run",
            "--database",
            str(service.database),
            "--data-root",
            str(service.data_root),
            "--contact-email",
            "first@example.org",
            "--json",
        ],
    )
    assert original.exit_code == 0, original.output
    view = json.loads(original.stdout)
    before = len(sources.calls)
    sources.recovered = True
    resumed = runner.invoke(
        app,
        [
            "audit",
            "resume",
            view["plan"]["plan_id"],
            "--database",
            str(service.database),
            "--data-root",
            str(service.data_root),
            "--contact-email",
            "second@example.org",
            "--json",
        ],
    )
    assert resumed.exit_code == 0, resumed.output
    after = json.loads(resumed.stdout)
    assert after["status"] == "complete" and len(after["matrix_history"]) == 20
    assert len(sources.calls) == before + 1
    assert (
        "first@example.org" not in resumed.output
        and "second@example.org" not in resumed.output
    )
