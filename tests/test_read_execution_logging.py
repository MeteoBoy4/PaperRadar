"""D1所选根显式文件汇、封闭DTO与敏感载荷不外泄。"""

import json
from pathlib import Path

import pytest

from paper_radar.pi_execution import ExecutionError
from paper_radar.read_tasks import ReadAnalysis
from paper_radar.runtime_logging import FileSink
from tests.read_execution_support import allow_engineering_path, setup


def test_file_sink_is_explicit_and_events_have_only_safe_closed_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    data_root = tmp_path / "data"
    service, task, _ = setup(
        tmp_path, monkeypatch, mode="degrade", sink=FileSink(data_root)
    )
    with pytest.raises(ExecutionError, match="evidence_missing"):
        service.run_attempt(task.task_id)
    assert not (data_root / "logs").exists()
    allow_engineering_path(monkeypatch)
    service.run_attempt(task.task_id)
    result = service.run_attempt(task.task_id)
    assert isinstance(result, ReadAnalysis)
    path = data_root / "logs/runtime.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert [row["event"] for row in rows] == [
        "claimed",
        "failed",
        "claimed",
        "succeeded",
    ]
    allowed = {
        "format_version",
        "event",
        "component",
        "stage",
        "task_id",
        "paper_id",
        "fingerprint",
        "attempt",
        "kind",
        "timestamp",
        "elapsed_ms",
    }
    assert all(set(row) <= allowed for row in rows)
    assert all(row["component"] == row["stage"] == "read" for row in rows)
    assert [row["attempt"] for row in rows] == [1, 1, 2, 2]
    assert all(len(row["fingerprint"]) == 16 for row in rows if "fingerprint" in row)
    observed = path.read_text() + repr(capsys.readouterr()) + repr(result)
    for sensitive in (
        "BAD PRIVATE ID",
        "STDERR PRIVATE SENTINEL",
        "oauth-test-only-sensitive-sentinel",
        "Frozen effective Pi system prompt",
        "Read synthetic prompt",
        "real-model",
        "Exact source",
        "该方法提供了新的比较方式",
        "chatgpt_subscription",
        "OPENAI_API_KEY",
        "climate",
        "statistics",
        "reanalysis",
        "mechanisms",
    ):
        assert sensitive not in observed
    assert len(tuple(data_root.rglob("*.jsonl"))) == 1


def test_sink_failure_does_not_retry_or_change_analysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from collections.abc import Mapping

    class Broken:
        def emit(self, event: Mapping[str, object]) -> None:
            raise OSError("PRIVATE LOG SENTINEL")

    service, task, _ = setup(tmp_path, monkeypatch, sink=Broken())
    allow_engineering_path(monkeypatch)
    result = service.run_attempt(task.task_id)
    assert isinstance(result, ReadAnalysis) and result.attempt_ordinal == 1
    assert service.tasks.task(task.task_id).remaining_attempts == 1
    assert len(service.tasks.analyses(task.paper_id)) == 1
