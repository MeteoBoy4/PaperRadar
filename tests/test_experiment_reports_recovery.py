"""B-E14 独立 D1:报告发布故障、冻结输入与真正标准恢复子进程。"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from paper_radar.cli import app
from paper_radar.experiment.reports import Reports
from tests.experiment_read_support import read_fixture
from tests.test_experiment_candidates_cli import FeedFixture
from tests.test_experiment_candidates_cli import feed as feed
from tests.test_experiment_reports_cli import report
from tests.test_owner_live_waiver import command as waiver


def test_replace_done_before_publish_commit_survives_admission_change_and_cold_restore(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = read_fixture(feed, tmp_path, monkeypatch, mode="degrade")
    read = fixture.read()
    assert read.exit_code == 0, read.output
    analysis = json.loads(read.stdout)["task"]["analysis_id"]
    root = fixture.layout.extraction.root
    options = (
        "--date",
        "2026-11-14",
        "--timezone",
        "Asia/Shanghai",
        "--snapshot",
        fixture.snapshot,
    )
    original_replace = os.replace

    def interrupted(source: str | Path, target: str | Path) -> None:
        original_replace(source, target)
        if str(target).endswith(".md"):
            raise RuntimeError("PRIVATE_CRASH_TEXT")

    with monkeypatch.context() as crash:
        crash.setattr(os, "replace", interrupted)
        result = report(root.root, "render", *options)
    assert result.exit_code == 2 and "execution_failed" in result.output
    assert "PRIVATE_CRASH_TEXT" not in result.output
    (path,) = (root.views / "2026-11-14").glob("*.md")
    report_id = path.stem
    frozen = path.read_bytes()
    service = Reports(root.database, root.data_root, root.views)
    prepared = service.verify(report_id)
    assert prepared["state"] == "prepared"
    assert prepared["members"] == [
        {
            "paper_id": fixture.layout.extraction.prepared.paper_id,
            "primary_kind": "analysis",
            "primary_ref": analysis,
            "display_number": "N1",
            "section": "transferable",
            "first_publication_key": f"analysis:{analysis}",
        }
    ]
    assert (
        waiver(
            root.database, "--disable", "--reason", "PRIVATE_CURRENT_ADMISSION_CHANGED"
        ).exit_code
        == 0
    )
    backup = CliRunner().invoke(
        app,
        [
            "backup",
            "create",
            "--database",
            str(root.database),
            "--data-root",
            str(root.data_root),
            "--output",
            str(tmp_path / "backups"),
        ],
    )
    assert backup.exit_code == 0, backup.output
    (batch,) = (tmp_path / "backups").iterdir()
    resumed = report(root.root, "render", *options)
    assert resumed.exit_code == 0, resumed.output
    receipt = json.loads(resumed.stdout)
    assert receipt == {**prepared, "state": "published"}
    assert path.read_bytes() == frozen
    assert "PRIVATE_CURRENT_ADMISSION_CHANGED" not in frozen.decode()
    restored = tmp_path / "arbitrary-restored-name"
    restored_cli = subprocess.run(
        [
            str(Path(sys.executable).with_name("paper-radar")),
            "restore",
            "verify",
            str(batch),
            "--target",
            str(restored),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert restored_cli.returncode == 0, restored_cli.stdout + restored_cli.stderr
    forbidden = [
        root.root,
        fixture.layout.extraction.models,
        fixture.layout.extraction.prepared.credentials,
    ]
    for forbidden_path in forbidden:
        forbidden_path.rename(
            forbidden_path.with_name(forbidden_path.name + "-unavailable")
        )
    output = tmp_path / "independent-report-output"
    cold = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.experiment_report_recovery_worker",
            str(restored),
            str(output),
            report_id,
            *(str(p) for p in forbidden),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert cold.returncode == 0, cold.stdout + cold.stderr
    assert json.loads(cold.stdout) == prepared
    assert (output / str(prepared["relative_path"])).read_bytes() == frozen
