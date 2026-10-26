"""resume 明示联网写入，replay 只读并披露证明等级。"""

import json
from pathlib import Path

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
