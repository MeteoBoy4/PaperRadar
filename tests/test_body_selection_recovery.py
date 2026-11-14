"""D1: 新正文选择与旧报告/暴露清单的冷备份、移动恢复。"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from paper_radar.body.selection import BodySelections
from paper_radar.experiment.reports import Reports
from tests.body_selection_support import choose, second_body
from tests.experiment_read_support import read_fixture
from tests.exposure_support import backup, payload
from tests.test_experiment_candidates_cli import FeedFixture
from tests.test_experiment_candidates_cli import feed as feed
from tests.test_experiment_reports_cli import report


def test_cold_backup_restore_and_move_keep_selection_old_report_and_export(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = read_fixture(feed, tmp_path, monkeypatch)
    assert fixture.read().exit_code == 0
    layout = fixture.layout
    root = layout.extraction.root
    rendered = report(root.root, "render", "--date", "2026-11-14", "--timezone", "UTC")
    assert rendered.exit_code == 0, rendered.output
    report_id = json.loads(rendered.stdout)["report_id"]
    report_before = Reports(root.database, root.data_root, root.views).receipt(
        report_id
    )
    export, _, original = payload(root)
    layout.identity = second_body(layout)
    assert choose(layout).exit_code == 0
    layout.review(request="new-owner-review")
    expected = dict(
        paper=layout.extraction.prepared.paper_id,
        selections=[
            r.model_dump(mode="json")
            for r in BodySelections(root.database, root.data_root).history()
        ],
        report_id=report_id,
        report=report_before,
        export_id=export["export_id"],
        export=original.decode(),
    )
    expected_file = tmp_path / "expected.json"
    expected_file.write_text(json.dumps(expected))
    saved = backup(root, tmp_path / "backups")
    assert saved.exit_code == 0, saved.output
    (batch,) = (tmp_path / "backups").iterdir()
    forbidden = [
        root.root,
        layout.extraction.models,
        layout.extraction.prepared.credentials,
    ]
    for path in forbidden:
        path.rename(path.with_name(path.name + "-unavailable"))
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.body_selection_recovery_worker",
            str(batch),
            str(tmp_path / "restored"),
            str(tmp_path / "moved"),
            str(expected_file),
            *(str(p) for p in forbidden),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "body selection recovered" in result.stdout
