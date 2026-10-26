"""显式 run 的联系信息准入及安全只读输出。"""

import json
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from paper_radar.cli import app
from paper_radar.fixture_audit import FixtureAudit
from paper_radar.storage.database import upgrade_database
from tests.audit_matrix_support import MAIN, MatrixSources
from tests.audit_sampling_support import CODE, sampling_service


def test_cli_run_requires_contact_before_plan_and_has_local_help(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "facts.sqlite3"
    upgrade_database(database)
    monkeypatch.setattr(
        httpx.AsyncClient,
        "send",
        lambda *args, **kwargs: pytest.fail("unexpected HTTP"),
    )
    runner = CliRunner()
    for args in (["audit", "run", "--help"],):
        result = runner.invoke(app, args)
        assert result.exit_code == 0
        assert "--contact-email" in result.output
    for contact in (None, "private-invalid-contact"):
        args = [
            "audit",
            "run",
            "--database",
            str(database),
            "--data-root",
            str(tmp_path / "data"),
        ]
        if contact:
            args += ["--contact-email", contact]
        result = runner.invoke(app, args)
        assert result.exit_code == 1
        assert "invalid_contact" in result.output
        assert "private-invalid-contact" not in result.output
    assert FixtureAudit(database).list_audits() == ()
    assert not (tmp_path / "data").exists()


def test_cli_show_uses_service_matrix_projection_and_never_reads_text(
    tmp_path: Path,
) -> None:
    service = sampling_service(tmp_path, MatrixSources())
    view = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    result = CliRunner().invoke(
        app,
        [
            "audit",
            "show",
            view.plan.plan_id,
            "--database",
            str(service.database),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    value = json.loads(result.stdout)
    assert value["status"] == "complete"
    assert value["physical_http_requests"] == 15
    assert len(value["matrix"]) == 19
    assert MAIN not in result.output and "audit@example.org" not in result.output


def test_cli_run_executes_real_service_with_only_http_transport_replaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.fixture_audit import acquisition_service
    from paper_radar.fixture_audit.source_http import SourceHTTPExecutor
    from tests.audit_sampling_support import SamplingClock

    sources = MatrixSources()
    clock = SamplingClock()
    executor = SourceHTTPExecutor(
        transport=httpx.MockTransport(sources),
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )
    monkeypatch.setattr(acquisition_service, "SourceHTTPExecutor", lambda: executor)
    database = tmp_path / "facts.sqlite3"
    upgrade_database(database)
    result = CliRunner().invoke(
        app,
        [
            "audit",
            "run",
            "--database",
            str(database),
            "--data-root",
            str(tmp_path / "data"),
            "--contact-email",
            "audit@example.org",
            "--count",
            "10",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    view = json.loads(result.stdout)
    assert view["status"] == "complete"
    assert [journal["target"] for journal in view["journal_summaries"]] == [10] * 4
    assert [journal["shortfall"] for journal in view["journal_summaries"]] == [9] * 4
    assert view["physical_http_requests"] == 15
    assert MAIN not in result.output and "audit@example.org" not in result.output
