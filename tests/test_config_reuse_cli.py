"""A2-04 真实安装 CLI 的就绪、脱敏和只读行为。"""

from __future__ import annotations

from pathlib import Path

import pytest

from paper_radar.config import load_config_snapshot
from paper_radar.config.compile import StageName
from tests.config_reuse_support import reuse_inputs
from tests.config_test_support import run_cli


def test_config_help_documents_reuse_and_suggestion_without_io(tmp_path: Path) -> None:
    result = run_cli(tmp_path, "config", "--help", help_only=True)
    assert result.returncode == 0, result.stderr
    assert "复用升级" in result.stdout
    assert "建议规则" in result.stdout
    assert "配置就绪" in result.stdout
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("values", ["[3]", "[2, 3]", "[3, 2]"])
def test_cli_checks_and_compiles_legal_sets_with_same_output(
    tmp_path: Path, values: str
) -> None:
    settings, db = reuse_inputs(tmp_path)
    path = tmp_path / "config/screening/reuse-escalation-v1.yaml"
    path.write_text(path.read_text().replace("[3]", values))
    args = ("--settings", str(settings), "--database", str(db))
    checked = run_cli(tmp_path, "config", "check", *args)
    assert checked.returncode == 0, checked.stderr
    assert "reuse：ready" in checked.stdout
    assert "suggestion：ready" in checked.stdout
    assert "value：not_ready" in checked.stdout
    saved = run_cli(tmp_path, "config", "compile", *args)
    assert saved.returncode == 0, saved.stderr
    assert saved.stdout == checked.stdout
    snapshot_id = saved.stdout.splitlines()[0].split("：")[1]
    assert (
        load_config_snapshot(db, snapshot_id).stages[StageName.REUSE].status == "ready"
    )


def test_cli_reports_missing_parameters_prompt_and_reason_contract(
    tmp_path: Path,
) -> None:
    settings, db = reuse_inputs(tmp_path)
    settings.write_text(
        settings.read_text()
        .replace("escalation: reuse-escalation-v1\n", "")
        .replace("  reuse: v1\n", "")
        .replace("  decision_reasons: v1\n", "")
    )
    result = run_cli(
        tmp_path, "config", "check", "--settings", str(settings), "--database", str(db)
    )
    assert result.returncode == 0, result.stderr
    assert "reuse：not_ready；缺项：reuse_prompt, excerpt_selector" in result.stdout
    assert (
        "suggestion：not_ready；缺项：suggestion_rule, escalation_parameters, "
        "decision_reasons_contract" in result.stdout
    )


@pytest.mark.parametrize(
    ("old", "new", "field"),
    [
        ("[3]", "[3, 3]", "reuse_escalation_research_values"),
        ("[3]", "[6]", "reuse_escalation_research_values"),
        ("[3]", "[true]", "reuse_escalation_research_values"),
        ("[3]", "[]", "reuse_escalation_research_values"),
        ("[availability, methods]", "[methods, availability]", "excerpt_priority"),
        (
            "excerpt_selector_version: v1",
            "excerpt_selector_version: secret-marker",
            "excerpt_selector_version",
        ),
        (
            "suggestion_rule_version: v1",
            "suggestion_rule_version: secret-marker",
            "suggestion_rule_version",
        ),
    ],
)
def test_cli_parameter_errors_expose_only_sanitized_field_paths(
    tmp_path: Path, old: str, new: str, field: str
) -> None:
    settings, db = reuse_inputs(tmp_path)
    path = tmp_path / "config/screening/reuse-escalation-v1.yaml"
    path.write_text(path.read_text().replace(old, new))
    (tmp_path / "prompts/screening/reuse-v1.md").write_text("PROMPT_PRIVATE_MARKER")
    for command in ("check", "compile"):
        result = run_cli(
            tmp_path,
            "config",
            command,
            "--settings",
            str(settings),
            "--database",
            str(db),
        )
        assert result.returncode == 2
        assert f"escalation.{field}" in result.stderr
        assert "secret-marker" not in result.stdout + result.stderr
        assert "PROMPT_PRIVATE_MARKER" not in result.stdout + result.stderr
        assert "Traceback" not in result.stderr


@pytest.mark.parametrize("selector", ["reuse_assessment", "decision_reasons"])
def test_cli_selected_contract_drift_is_controlled_and_does_not_repair(
    tmp_path: Path, selector: str
) -> None:
    settings, db = reuse_inputs(tmp_path)
    path = (
        tmp_path / "contracts/screening" / selector.replace("_", "-") / "v1/schema.json"
    )
    path.write_text("{}")
    result = run_cli(
        tmp_path,
        "config",
        "compile",
        "--settings",
        str(settings),
        "--database",
        str(db),
    )
    assert result.returncode == 2
    assert f"contracts.{selector}" in result.stderr
    assert path.read_text() == "{}"


@pytest.mark.parametrize("command", ["check", "compile"])
def test_reuse_command_help_works_without_config_database_or_network(
    tmp_path: Path, command: str
) -> None:
    result = run_cli(tmp_path, "config", command, "--help", help_only=True)
    assert result.returncode == 0, result.stderr
    assert "示例" in result.stdout
    assert not list(tmp_path.iterdir())
