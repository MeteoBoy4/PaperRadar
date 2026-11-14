"""B-E14 独立 D1:代码/工具的受控Read价值类型进入可转化成果栏。"""

import json
from pathlib import Path

import pytest

from tests.experiment_read_support import read_fixture
from tests.pi_execution_support import PeerRun
from tests.test_experiment_candidates_cli import FeedFixture
from tests.test_experiment_candidates_cli import feed as feed
from tests.test_experiment_reports_cli import report


def test_code_tool_analysis_is_in_transferable_section(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = PeerRun.__init__

    def initialize(self: PeerRun, peer: str) -> None:
        original(
            self,
            peer.replace('"value_types": ["method"]', '"value_types": ["code_tool"]'),
        )

    monkeypatch.setattr(PeerRun, "__init__", initialize)
    fixture = read_fixture(feed, tmp_path, monkeypatch)
    read = fixture.read()
    assert read.exit_code == 0, read.output
    root = fixture.layout.extraction.root.root
    rendered = report(
        root,
        "render",
        "--date",
        "2026-11-14",
        "--timezone",
        "UTC",
        "--snapshot",
        fixture.snapshot,
    )
    assert rendered.exit_code == 0, rendered.output
    receipt = json.loads(rendered.stdout)
    assert receipt["members"][0]["section"] == "transferable"
    content = (root / "views" / receipt["relative_path"]).read_text()
    assert '"code_tool"' in content and "可转化成果" in content
