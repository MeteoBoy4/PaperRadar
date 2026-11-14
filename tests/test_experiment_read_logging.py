"""已交付 Read 执行入口的独立 D1 文件日志装配守卫。"""

import json
from pathlib import Path

import pytest

from tests.experiment_read_support import read_fixture
from tests.test_experiment_candidates_cli import FeedFixture
from tests.test_experiment_candidates_cli import feed as feed

DELIVERED_EXECUTION_ENTRIES = ("read", "retry", "reclaim")


@pytest.mark.parametrize("entry", DELIVERED_EXECUTION_ENTRIES)
def test_every_read_execution_entry_uses_selected_root_sink_and_queries_are_readonly(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, entry: str
) -> None:
    fixture = read_fixture(
        feed, tmp_path, monkeypatch, mode="invalid" if entry == "retry" else "normal"
    )
    root = fixture.layout.extraction.root
    log = root.logs / "runtime.jsonl"
    if entry == "read":
        before = len(log.read_text().splitlines())
        result = fixture.read()
    else:
        first = fixture.read()
        assert first.exit_code == (4 if entry == "retry" else 0), first.output
        task = json.loads(first.stdout.splitlines()[0])["task"]["task_id"]
        before = len(log.read_text().splitlines())
        result = (
            fixture.query(
                "retry",
                task,
                "--request-id",
                "retry-logging",
                "--reason",
                "PRIVATE_RETRY_LOG_REASON",
                "--actor",
                "owner",
            )
            if entry == "retry"
            else fixture.query("reclaim", task)
        )
    assert result.exit_code == 0, result.output
    new_events = [json.loads(line) for line in log.read_text().splitlines()[before:]]
    assert [e["event"] for e in new_events] == (
        ["run_started", "claimed", "succeeded", "run_finished"]
        if entry == "read"
        else ["run_started", "run_finished"]
    )
    assert new_events[0]["component"] == new_events[-1]["component"] == "experiment"
    assert new_events[-1]["category"] == "completed"
    assert new_events[0]["run_id"] == new_events[-1]["run_id"]
    for sentinel in (
        "PRIVATE_READ_CONCLUSION",
        "PRIVATE_READ_PROMPT",
        "PRIVATE_RETRY_LOG_REASON",
        "oauth-test-only-sensitive-sentinel",
    ):
        assert sentinel not in log.read_text()
    stable = log.read_bytes()
    queried = fixture.query("tasks")
    assert queried.exit_code == 0, queried.output
    failed = fixture.query("failures", "--snapshot", fixture.snapshot)
    assert failed.exit_code == 0, failed.output
    if entry == "read":
        content = fixture.query(
            "analysis", json.loads(result.stdout)["task"]["analysis_id"]
        )
        assert content.exit_code == 0 and "PRIVATE_READ_CONCLUSION" in content.stdout
    assert log.read_bytes() == stable
