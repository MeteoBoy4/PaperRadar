"""审计只读 CLI 与帮助的公开边界。"""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from paper_radar.cli import app
from paper_radar.fixture_audit import FixtureAudit
from paper_radar.fixture_audit.acquisition_models import CodeIdentity, SourceRequest
from paper_radar.storage.database import upgrade_database


def test_audit_cli_shows_safe_execution_counts_without_creating_locks(
    tmp_path: Path,
) -> None:
    import json

    database = tmp_path / "data" / "facts.sqlite3"
    database.parent.mkdir()
    upgrade_database(database)
    service = FixtureAudit(database, database.parent)
    plan = service.create_audit_plan(
        contact_email="audit@example.org", code_identity=CodeIdentity(basis="synthetic")
    )
    service.acquire_source(
        plan.plan_id,
        request_key="render",
        request=SourceRequest(journal="jgr", route="feed", channel="browser_render"),
        contact_email="audit@example.org",
    )
    runner = CliRunner()
    result = runner.invoke(
        app, ["audit", "show", plan.plan_id, "--database", str(database), "--json"]
    )
    assert result.exit_code == 0, result.output
    value = json.loads(result.stdout)
    assert value["executions"][0]["reason"] == "channel_not_installed"
    assert value["executions"][0]["physical_requests"] == 0
    assert "audit@example.org" not in result.output
    assert not (database.parent / ".paper-radar-audit-locks").exists()
    listed = runner.invoke(
        app, ["audit", "list", "--database", str(database), "--json"]
    )
    assert listed.exit_code == 0
    assert json.loads(listed.stdout)[0]["plan"]["plan_id"] == plan.plan_id


def test_audit_help_and_missing_database_are_read_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    for args in (
        ["audit", "--help"],
        ["audit", "show", "--help"],
        ["audit", "list", "--help"],
    ):
        result = runner.invoke(app, args)
        assert result.exit_code == 0
        assert "只读" in result.output
    result = runner.invoke(
        app, ["audit", "list", "--database", str(tmp_path / "missing.sqlite3")]
    )
    assert result.exit_code == 1
    assert "数据库不存在" in result.output
    assert not list(tmp_path.iterdir())
