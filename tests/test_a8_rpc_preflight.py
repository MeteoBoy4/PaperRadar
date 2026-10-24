"""可在领取前发现的历史材料错误不能消耗预算。"""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from paper_radar.config import compile_config
from paper_radar.screening_tasks import ScreeningTasks, TaskError, TaskReason
from tests.a8_call_support import archive, request_for
from tests.a8_rpc_support import FakeFactory
from tests.a8_rpc_task_support import run_attempt


def test_corrupt_receipt_audit_snapshot_is_safe_preclaim_error(tmp_path: Path) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(
        data.database, data.data_root, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    first = tasks.register(request_for(data))
    adapter = data.settings.parent / "adapters/pi-v1.yaml"
    newer = data.settings.parent / "adapters/pi-v2.yaml"
    newer.write_text(
        adapter.read_text()
        .replace("version: pi-v1", "version: pi-v2")
        .replace("transport-v1", "transport-v2")
    )
    data.settings.write_text(
        data.settings.read_text().replace("screening: pi-v1", "screening: pi-v2")
    )
    snapshot = compile_config(data.settings, data.database)
    second = tasks.register(request_for(data, snapshot_id=snapshot.snapshot_id))
    assert second.budget_id == first.budget_id
    with sqlite3.connect(data.database) as connection:
        connection.execute(
            "UPDATE runtime_config_snapshots SET payload_json = ? "
            "WHERE snapshot_id = ?",
            ("AUDIT_CORRUPTION_SECRET", snapshot.snapshot_id),
        )
    factory = FakeFactory()
    with pytest.raises(TaskError) as failure:
        run_attempt(tasks, second.receipt_id, factory, clock=factory.clock)
    assert failure.value.reason is TaskReason.CORRUPT_REFERENCE
    assert "AUDIT_CORRUPTION_SECRET" not in repr(failure.value)
    assert tasks.status(first.receipt_id).used_attempts == 0
    assert factory.sessions == []


def test_outer_wire_expansion_is_checked_before_claim(tmp_path: Path) -> None:
    from paper_radar.llm import MAX_REQUEST_BYTES, render_request
    from paper_radar.papers import PaperFacts
    from tests.a8_call_support import prepare_call
    from tests.test_paper_mapping import screening_fields
    from tests.test_paper_service import observation

    data = archive(tmp_path)
    paper = PaperFacts(data.database, data.data_root).submit(
        observation(
            doi="10.1234/wire-expansion",
            query_key="wire-expansion",
            fields=screening_fields(abstract='"' * 120_000),
        )
    )
    tasks = ScreeningTasks(
        data.database, data.data_root, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    receipt = tasks.register(request_for(data, paper_id=paper.paper_id))
    assert (
        len(render_request(prepare_call(tasks, receipt.receipt_id))) < MAX_REQUEST_BYTES
    )
    factory = FakeFactory()
    with pytest.raises(TaskError) as failure:
        run_attempt(tasks, receipt.receipt_id, factory, clock=factory.clock)
    assert failure.value.reason is TaskReason.INVALID_CONTEXT
    assert tasks.status(receipt.receipt_id).used_attempts == 0
    assert factory.sessions == []
