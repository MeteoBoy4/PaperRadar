"""同正文跨冻结样本的所有者来源,不以时钟顺序猜选。"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tests.experiment_layout_support import synthetic_pdf
from tests.experiment_read_support import read_fixture
from tests.test_experiment_candidates_cli import FeedFixture
from tests.test_experiment_candidates_cli import feed as feed
from tests.test_experiment_pdf_cli import attach


def test_claim_binds_current_sample_owner_even_when_review_clocks_move_backwards(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.body import extraction
    from paper_radar.experiment.validation import validate_all
    from paper_radar.read_tasks import ReadTasks

    fixture = read_fixture(feed, tmp_path, monkeypatch, reviewed=False)
    earlier = datetime.now(UTC) - timedelta(days=1)
    with monkeypatch.context() as clock:
        clock.setattr(extraction, "now", lambda: earlier.isoformat())
        first = fixture.layout.review(request="first-sample-owner")
    reattached = attach(
        fixture.layout.extraction.prepared,
        tmp_path,
        request="same-pdf-new-sample",
        raw=synthetic_pdf(),
    )
    assert reattached.exit_code == 0, reattached.output
    with monkeypatch.context() as clock:
        clock.setattr(
            extraction, "now", lambda: (earlier - timedelta(days=1)).isoformat()
        )
        current = fixture.layout.review(request="current-sample-owner")
    assert current["sample_id"] != first["sample_id"]
    result = fixture.read()
    assert result.exit_code == 0, result.output
    root = fixture.layout.extraction.root
    task_id = json.loads(result.stdout)["task"]["task_id"]
    task = ReadTasks(root.database, root.data_root).task(task_id)
    assert task.attempts[0].basis["review_id"] == current["review_id"]
    assert task.attempts[0].basis["sample_id"] == current["sample_id"]
    validate_all(root.database, root.data_root)
