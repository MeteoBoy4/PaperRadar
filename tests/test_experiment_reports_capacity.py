"""B-E14 独立 D1:真实合成多成员的五项/三篇、FIFO 与独立发布键。"""

import json
from pathlib import Path

import pytest

from tests.experiment_report_support import multi_report_fixture
from tests.test_experiment_candidates_cli import FeedFixture
from tests.test_experiment_candidates_cli import feed as feed
from tests.test_experiment_reports_cli import report


def test_daily_caps_fifo_nonanalysis_slots_and_independent_paper_revision(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture, analyses, pending, blocked = multi_report_fixture(
        feed, tmp_path, monkeypatch
    )
    root = fixture.layout.extraction.root.root
    options = ("--timezone", "Asia/Shanghai", "--snapshot", fixture.snapshot)
    first = report(root, "render", "--date", "2026-11-14", *options)
    assert first.exit_code == 0, first.output
    receipt = json.loads(first.stdout)
    members = receipt["members"]
    assert len(members) == 5
    assert [m["primary_ref"] for m in members] == [*analyses[:3], pending, blocked]
    assert [m["display_number"] for m in members] == ["N1", "N2", "N3", "N4", "N5"]
    assert [m["primary_kind"] for m in members] == [
        "analysis",
        "analysis",
        "analysis",
        "pending",
        "blocked",
    ]
    frozen = (root / "views" / receipt["relative_path"]).read_bytes()
    again = report(root, "render", "--date", "2026-11-14", *options)
    assert json.loads(again.stdout) == receipt
    assert (root / "views" / receipt["relative_path"]).read_bytes() == frozen
    second = report(root, "render", "--date", "2026-11-15", *options)
    assert second.exit_code == 0, second.output
    assert [m["primary_ref"] for m in json.loads(second.stdout)["members"]] == analyses[
        3:
    ]
    single = report(
        root, "render", "--date", "2026-11-15", *options, "--analysis-id", analyses[0]
    )
    assert single.exit_code == 0, single.output
    assert json.loads(single.stdout)["members"] == members[:1]
    revised = report(
        root, "render", "--date", "2026-11-15", *options, "--analysis-id", analyses[1]
    )
    assert (
        revised.exit_code == 0
        and json.loads(revised.stdout)["report_id"]
        != json.loads(single.stdout)["report_id"]
    )
