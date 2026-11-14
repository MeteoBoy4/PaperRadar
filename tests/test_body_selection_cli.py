"""D1: 显式正文选择公共 CLI 与真实 CurrentBody/Read 消费。"""

from pathlib import Path

import pytest

from paper_radar.body import BodyService
from paper_radar.read_queries import ReadQueries
from paper_radar.read_tasks import ReadTasks
from tests.body_selection_support import choose, second_body
from tests.experiment_read_support import read_fixture
from tests.test_experiment_candidates_cli import FeedFixture
from tests.test_experiment_candidates_cli import feed as feed


@pytest.mark.parametrize("command", ["body-select", "body-selections"])
def test_selection_help_is_cold_and_complete(tmp_path: Path, command: str) -> None:
    from tests.test_experiment_layout_cli import test_layout_help_is_cold_and_complete

    test_layout_help_is_cold_and_complete(tmp_path, command)


def test_selection_resolves_ambiguity_but_requires_owner_review_before_read(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepared = read_fixture(feed, tmp_path, monkeypatch, reviewed=False)
    layout = prepared.layout
    root = layout.extraction.root
    body = BodyService(root.database, root.data_root)
    identity = second_body(layout)
    assert (
        body.current_body(layout.extraction.prepared.paper_id).reason
        == "ambiguous_extractions"
    )
    layout.identity = identity
    result = choose(layout)
    assert result.exit_code == 0, result.output
    assert body.current_body(layout.extraction.prepared.paper_id).identity == identity
    rejected = prepared.read()
    assert rejected.exit_code == 2 and "document_gate_required" in rejected.output
    layout.review()
    accepted = prepared.read()
    assert accepted.exit_code == 0, accepted.output
    assert body.current_body(layout.extraction.prepared.paper_id).identity == identity
    (task,) = ReadTasks(root.database, root.data_root).history(
        layout.extraction.prepared.paper_id
    )
    assert task.identity == identity and len(task.attempts) == 1
    current = ReadQueries(root.database, root.data_root).current(
        layout.extraction.prepared.paper_id
    )
    assert current.state == "available" and current.identity == identity
