"""B 收口独立 D1:组合 trace 不丢旧事实,恢复保留完整工作流。"""

import json
from pathlib import Path

import pytest

from paper_radar.backup import create_backup
from paper_radar.backup.restore import restore_backup
from tests.config_test_support import run_cli
from tests.experiment_read_support import read_fixture
from tests.feed_support import facts, item
from tests.stage_b_trace_support import workflow_snapshot
from tests.test_experiment_candidates_cli import FeedFixture
from tests.test_experiment_candidates_cli import feed as feed


def test_unknown_root_workflow_keeps_old_trace_and_denies_production(
    tmp_path: Path,
) -> None:
    source = tmp_path / "synthetic-source"
    source.mkdir()
    service = facts(source)
    feed = service.register_feed("https://feeds.example/closure")
    result = service.submit(item(feed.feed_id, doi="10.1234/closure"))
    assert result.paper_id and service.data_root
    expected = service.trace(result.paper_id).model_dump(mode="json")
    workflow = workflow_snapshot(service.database, service.data_root, result.paper_id)
    assert workflow["root"] == {
        "purpose": "unknown",
        "root_id": None,
        "registered_at": None,
    }
    for name in (
        "selections",
        "screening",
        "agent_content",
        "delegated_acceptances",
        "pdfs",
        "pdf_confirmations",
        "frozen_samples",
        "extractions",
        "bounded_executions",
        "layout_reviews",
        "read_tasks",
        "read_analyses",
    ):
        assert workflow[name] == []
    auto = workflow["eligibility"]["eligible_for_auto_read"]
    assert auto["eligible"] is False
    assert "root_unknown" in auto["reasons"]
    assert "projection" not in workflow
    expected["workflow"] = workflow
    batch = create_backup(service.database, service.data_root, tmp_path / "backups")
    restored = restore_backup(batch.batch_dir, tmp_path / "restored")
    source.rename(tmp_path / "source-unavailable")
    query = run_cli(
        tmp_path,
        "paper",
        "trace",
        result.paper_id,
        "--database",
        str(restored.target_dir / "database.sqlite3"),
        "--data-root",
        str(restored.target_dir),
        "--verify-source-bytes",
        "--json",
        "--show-abstract",
    )
    assert query.returncode == 0, query.stderr
    assert json.loads(query.stdout) == expected


def test_nonempty_workflow_restores_body_read_and_selection_without_promotion(
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = read_fixture(feed, tmp_path, monkeypatch)
    read = fixture.read()
    assert read.exit_code == 0, read.output
    root = fixture.layout.extraction.root
    paper = fixture.layout.extraction.prepared.paper_id
    workflow = workflow_snapshot(root.database, root.data_root, paper)
    assert workflow["root"]["purpose"] == "experiment"
    # layout_fixture 显式替换一次 PDF,两个附件及各自冻结历史都必须保留。
    expected_counts = {
        "selections": 1,
        "delegated_acceptances": 1,
        "pdfs": 2,
        "pdf_confirmations": 2,
        "frozen_samples": 2,
        "extractions": 1,
        "bounded_executions": 1,
        "layout_reviews": 1,
        "read_tasks": 1,
        "read_analyses": 1,
    }
    for name, count in expected_counts.items():
        assert len(workflow[name]) == count, name
    auto = workflow["eligibility"]["eligible_for_auto_read"]
    assert auto["eligible"] is False
    assert "experiment_no_auto_queue" in auto["reasons"]
    assert workflow["agent_content"] == []
    assert workflow["screening"] == []
    original = run_cli(
        tmp_path,
        "paper",
        "trace",
        paper,
        "--database",
        str(root.database),
        "--data-root",
        str(root.data_root),
        "--verify-source-bytes",
        "--json",
        "--show-abstract",
    )
    assert original.returncode == 0, original.stderr
    expected = json.loads(original.stdout)
    assert expected["workflow"] == workflow
    batch = create_backup(root.database, root.data_root, tmp_path / "backups")
    restored = restore_backup(batch.batch_dir, tmp_path / "restored")
    root.root.rename(tmp_path / "source-unavailable")
    recovered = run_cli(
        tmp_path,
        "paper",
        "trace",
        paper,
        "--database",
        str(restored.target_dir / "database.sqlite3"),
        "--data-root",
        str(restored.target_dir),
        "--verify-source-bytes",
        "--json",
        "--show-abstract",
    )
    assert recovered.returncode == 0, recovered.stderr
    assert json.loads(recovered.stdout) == expected
