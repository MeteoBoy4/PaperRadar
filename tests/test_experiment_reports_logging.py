"""B-E14 独立 D1:报告执行FileSink守卫与每次visibility消费。"""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from paper_radar.calibration import visibility
from paper_radar.cli import app
from tests.test_experiment_reports_cli import report

DELIVERED_EXECUTION_ENTRIES = ("render",)


@pytest.mark.parametrize("entry", DELIVERED_EXECUTION_ENTRIES)
def test_report_execution_uses_selected_root_sink_and_queries_are_readonly(
    tmp_path: Path, entry: str
) -> None:
    root = tmp_path / "experiment"
    assert (
        CliRunner().invoke(app, ["experiment", "init", "--root", str(root)]).exit_code
        == 0
    )
    result = report(root, entry, "--date", "2026-11-14", "--timezone", "UTC")
    assert result.exit_code == 0, result.output
    receipt = json.loads(result.stdout)
    log = root / "logs/runtime.jsonl"
    lines = [json.loads(line) for line in log.read_text().splitlines()]
    assert [line["event"] for line in lines] == ["run_started", "run_finished"]
    assert all(line["component"] == "experiment" for line in lines)
    assert lines[0]["run_id"] == lines[1]["run_id"]
    assert lines[1]["category"] == "completed"
    stable = log.read_bytes()
    for command in ("rebuild", "verify"):
        queried = report(root, command, receipt["report_id"])
        assert queried.exit_code == 0, queried.output
    assert log.read_bytes() == stable


def test_each_render_checks_shared_visibility_and_denial_leaves_database_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "experiment"
    assert (
        CliRunner().invoke(app, ["experiment", "init", "--root", str(root)]).exit_code
        == 0
    )
    original = visibility.evaluate_visibility
    calls: list[frozenset[visibility.HiddenCondition]] = []

    def observed(
        hidden: frozenset[visibility.HiddenCondition],
    ) -> visibility.Visibility:
        calls.append(hidden)
        return original(hidden)

    monkeypatch.setattr(visibility, "evaluate_visibility", observed)
    first = report(root, "render", "--date", "2026-11-14", "--timezone", "UTC")
    assert first.exit_code == 0, first.output
    assert calls and all(hidden == frozenset() for hidden in calls)
    report_id = json.loads(first.stdout)["report_id"]
    for action in ("rebuild", "verify"):
        calls.clear()
        assert report(root, action, report_id).exit_code == 0
        assert calls == [frozenset()]
    before = (root / "paper-radar.sqlite3").read_bytes()
    monkeypatch.setattr(
        visibility,
        "evaluate_visibility",
        lambda _: visibility.Visibility(
            frozenset({visibility.HiddenCondition.UNREVEALED})
        ),
    )
    denied = report(root, "render", "--date", "2026-11-15", "--timezone", "UTC")
    assert denied.exit_code == 2 and "visibility_denied" in denied.output
    assert (root / "paper-radar.sqlite3").read_bytes() == before
