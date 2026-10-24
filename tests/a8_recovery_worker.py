"""新解释器隔离恢复 RPC 事实;查询不导入执行入口,显式继续仅一次。"""

import json
import sqlite3
import sys
from contextlib import closing
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from paper_radar.backup.restore import restore_backup
from paper_radar.screening import BoundaryOutput, ValuePredictionOutput
from paper_radar.screening_tasks import (
    FailureKind,
    FailureReceipt,
    ScreeningTasks,
    TaskError,
    TaskReason,
)
from paper_radar.storage.database import upgrade_database
from tests.a7_recovery_support import _reject_paths
from tests.backup_support import tree


def run() -> None:
    batch, target, moved = (Path(value) for value in sys.argv[1:4])
    expected = json.loads(Path(sys.argv[4]).read_text())
    blocked = [Path(value).resolve() for value in sys.argv[5:]]
    _reject_paths(blocked)
    restored = restore_backup(batch, target)
    restored.target_dir.rename(moved)
    blocked.append(batch.resolve())
    _reject_paths(blocked)
    database = moved / "database.sqlite3"
    tasks = ScreeningTasks(
        database, moved, clock=lambda: datetime(2026, 1, 1, 0, 10, tzinfo=UTC)
    )
    before = tree(moved)
    with closing(sqlite3.connect(database)) as connection:
        before_dump = tuple(connection.iterdump())
    tasks.validate_all()
    for query in expected["queries"]:
        actual = tasks.query(
            paper_id=query["paper_id"],
            stage=query["stage"],
            snapshot_id=query["snapshot_id"],
        )
        assert json.loads(json.dumps(asdict(actual), default=str)) == query
    for item in expected["inputs"]:
        receipt = tasks.get_receipt(item["receipt"]["receipt_id"])
        assert json.loads(json.dumps(asdict(receipt))) == item["receipt"]
        frozen = tasks.load_input(receipt.receipt_id)
        assert frozen.stage_input.payload_bytes.hex() == item["payload"]
        assert frozen.snapshot.snapshot_id == item["semantic_snapshot"]
    for item in expected["successes"]:
        loaded = tasks.load_success(item["id"])
        assert loaded.raw_response.hex() == item["raw"]
        assert loaded.receipt.executor_kind == "test"
        assert loaded.audit["provider_request_id"] is None
        assert (loaded.audit["input_tokens"], loaded.audit["output_tokens"]) == (5, 2)
        if loaded.receipt.stage == "boundary":
            assert (
                isinstance(loaded.output, BoundaryOutput)
                and loaded.output.boundary == "in_scope"
            )
        else:
            assert isinstance(loaded.output, ValuePredictionOutput)
            assert (
                loaded.output.topic_ids == ["alpha"]
                and loaded.output.research_value == 4
            )
    parent = tasks.get_receipt(expected["parent"])
    successor = tasks.get_receipt(expected["successor"])
    budget = next(
        budget
        for budget in tasks.query(
            paper_id=parent.paper_id, stage=parent.stage, snapshot_id=parent.snapshot_id
        ).budgets
        if budget.budget_id == parent.budget_id
    )
    assert (
        budget.tasks[1].parent_task_id == parent.task_id and successor.generation == 1
    )
    assert tasks.load_input(parent.receipt_id) == tasks.load_input(successor.receipt_id)
    assert tasks.status(parent.receipt_id).used_attempts == 2
    pending = tasks.status(successor.receipt_id)
    assert (pending.state, pending.used_attempts, pending.remaining_attempts) == (
        "lease_expired",
        1,
        1,
    )
    assert "paper_radar.llm.rpc" not in sys.modules
    assert tree(moved) == before
    with closing(sqlite3.connect(database)) as connection:
        assert tuple(connection.iterdump()) == before_dump

    # 恢复和以上查询没有执行入口;下面是本票唯一一次恢复后显式继续。
    upgrade_database(database)
    from tests.a8_recovery_support import fault_factory
    from tests.a8_rpc_task_support import run_attempt

    factory = fault_factory("protocol")
    assert tasks.retry(expected["retry"]) == successor
    result = run_attempt(tasks, successor.receipt_id, factory, clock=factory.clock)
    assert type(result) is FailureReceipt and result.attempt_no == 2
    assert result.kind is FailureKind.PROTOCOL_ERROR
    assert len(factory.sessions) == 1
    description = factory.sessions[0].description
    assert description.semantic_snapshot_id == expected["semantic_snapshot"]
    assert description.audit_snapshot_id == expected["audit_snapshot"]
    assert description.adapter_version == "transport-v2"
    sent = json.loads(factory.sessions[0].commands[-1]["message"].split("\n", 1)[1])
    assert sent["correction"] == "上次执行结果未知,请重新完成本次冻结输入。"
    assert tasks.status(successor.receipt_id).remaining_attempts == 0
    attempts = (
        next(
            budget
            for budget in tasks.query(
                paper_id=parent.paper_id,
                stage=parent.stage,
                snapshot_id=parent.snapshot_id,
            ).budgets
            if budget.budget_id == parent.budget_id
        )
        .tasks[1]
        .attempts
    )
    assert attempts[0].failure is not None
    assert (attempts[0].failure.kind, attempts[0].failure.origin) == (
        FailureKind.OUTCOME_UNKNOWN,
        "recovery",
    )
    try:
        run_attempt(tasks, successor.receipt_id, factory, clock=factory.clock)
    except TaskError as error:
        assert error.reason is TaskReason.BUDGET_EXHAUSTED
    else:
        raise AssertionError("expected_budget_exhausted")
    assert len(factory.sessions) == 1
    assert tasks.status(parent.receipt_id).used_attempts == 2
    tasks.validate_all()
    print(
        json.dumps(
            {
                "read_only_restore": True,
                "remaining_calls": 1,
                "original_paths_blocked": True,
            }
        )
    )


if __name__ == "__main__":
    run()
