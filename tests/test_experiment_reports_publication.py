"""B-E14 独立 D1:临时文件fsync/replace故障不破坏既有投影。"""

import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from paper_radar.cli import app
from tests.test_experiment_reports_cli import report


@pytest.mark.parametrize("boundary", ["fsync", "replace"])
def test_file_publication_failure_cleans_own_temporary_and_keeps_original(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, boundary: str
) -> None:
    root = tmp_path / "experiment"
    assert (
        CliRunner().invoke(app, ["experiment", "init", "--root", str(root)]).exit_code
        == 0
    )
    first = report(root, "render", "--date", "2026-11-14", "--timezone", "UTC")
    assert first.exit_code == 0, first.output
    receipt = json.loads(first.stdout)
    original = (root / "views" / receipt["relative_path"]).read_bytes()

    def fail(*args: object, **kwargs: object) -> None:
        raise OSError("PRIVATE_REPORT_DISK_FAILURE")

    with monkeypatch.context() as crash:
        crash.setattr(os, boundary, fail)
        failed = report(root, "render", "--date", "2026-11-15", "--timezone", "UTC")
    assert failed.exit_code == 2 and "execution_failed" in failed.output
    assert "PRIVATE_REPORT_DISK_FAILURE" not in failed.output
    assert (root / "views" / receipt["relative_path"]).read_bytes() == original
    assert list((root / "views" / "2026-11-15").iterdir()) == []
    resumed = report(root, "render", "--date", "2026-11-15", "--timezone", "UTC")
    assert resumed.exit_code == 0, resumed.output
    assert json.loads(resumed.stdout)["state"] == "published"
