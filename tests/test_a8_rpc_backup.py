"""真实非空 WAL 中 RPC 形成的两阶段事实隔离恢复,仅一例显式继续。"""

import json
import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from paper_radar.backup import create_backup, verify_backup
from paper_radar.papers import PaperFacts
from paper_radar.screening_tasks import (
    FailureKind,
    FailureReceipt,
    ScreeningTasks,
    SuccessReceipt,
)
from tests.a7_value_support import value_payload
from tests.a8_call_support import archive, request_for
from tests.a8_recovery_support import audit_upgrade, fault_factory, retry_request
from tests.a8_rpc_support import BOUNDARY_RAW, FakeFactory
from tests.a8_rpc_task_support import run_attempt
from tests.backup_support import tree
from tests.test_paper_mapping import screening_fields
from tests.test_paper_service import observation

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_rpc_wal_history_restores_independently_and_continues_remaining_attempt(
    tmp_path: Path,
) -> None:
    root = tmp_path / "original"
    data = archive(root)
    tasks = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    boundary = tasks.register(request_for(data))
    value = tasks.register(request_for(data, stage="value", original_title_is_zh=False))
    raw_value = (
        b" \n"
        + value_payload(topic_ids=["alpha"], display_title_zh="天气诊断方法")
        + b"\n "
    )
    successes = []
    for receipt, raw in ((boundary, BOUNDARY_RAW.encode()), (value, raw_value)):
        factory = FakeFactory(raw=raw.decode())
        success = run_attempt(tasks, receipt.receipt_id, factory, clock=factory.clock)
        assert type(success) is SuccessReceipt
        successes.append({"id": success.success_id, "raw": raw.hex()})
    cached = tasks.register(request_for(data, scheduled_day="2026-01-02"))
    assert cached.cached_success_id == successes[0]["id"]
    other = PaperFacts(data.database, data.data_root).submit(
        observation(doi="10.1234/rpc-recovery", fields=screening_fields())
    )
    assert other.paper_id
    parent = tasks.register(request_for(data, paper_id=other.paper_id))
    failed_value = tasks.register(
        request_for(
            data, paper_id=other.paper_id, stage="value", original_title_is_zh=False
        )
    )
    # 同库保留 RPC 协议预算失败和 A1 安全 issues,两者都是普通 A7 事实。
    invalid_raw = value_payload(
        research_value=6, research_value_reason_zh="完整失败原文_SECRET"
    ).decode()

    def private_noise(name: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if name == "prompt":
            records[0]["error"] = "FREE_UPSTREAM_ERROR_SECRET"
            records[8]["message"]["content"].append(
                {"type": "thinking", "thinking": "THINKING_TRANSCRIPT_SECRET"}
            )
        return records

    for receipt, kind in (
        (parent, FailureKind.PROTOCOL_ERROR),
        (failed_value, FailureKind.OUTPUT_INVALID),
    ):
        for _ in range(2):
            factory = (
                fault_factory("protocol")
                if receipt is parent
                else FakeFactory(raw=invalid_raw, mutate=private_noise)
            )
            failure = run_attempt(
                tasks, receipt.receipt_id, factory, clock=factory.clock
            )
            assert type(failure) is FailureReceipt and failure.kind is kind
            if receipt is failed_value:
                assert [
                    (issue.location, issue.category.value) for issue in failure.issues
                ] == [("$.research_value", "business_rule")]
    audit_id = audit_upgrade(data)
    retry = retry_request(data, parent, snapshot_id=audit_id)
    successor = tasks.retry(retry)
    interrupt = fault_factory("interrupt")
    with pytest.raises(KeyboardInterrupt):
        run_attempt(tasks, successor.receipt_id, interrupt, clock=interrupt.clock)
    assert interrupt.sessions[0].terminated
    assert tasks.status(successor.receipt_id).state == "running"
    tasks.validate_all()
    expected: dict[str, object] = {
        "parent": parent.receipt_id,
        "successor": successor.receipt_id,
        "retry": retry,
        "semantic_snapshot": data.snapshot_id,
        "audit_snapshot": audit_id,
        "successes": successes,
    }
    # WAL reader 持续占住旧快照,备份必须捕获之后提交的非空 WAL。
    with closing(sqlite3.connect(data.database)) as reader:
        assert reader.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
        reader.execute("BEGIN")
        reader.execute("SELECT count(*) FROM screening_requests").fetchone()
        tasks.register(
            request_for(data, scheduled_day="2026-01-03", snapshot_id=audit_id)
        )
        assert data.database.with_name(data.database.name + "-wal").stat().st_size > 0
        inputs = []
        for paper in (data.paper_id, other.paper_id):
            for receipt in tasks.receipts(paper):
                frozen = tasks.load_input(receipt.receipt_id)
                inputs.append(
                    {
                        "receipt": asdict(receipt),
                        "payload": frozen.stage_input.payload_bytes.hex(),
                        "semantic_snapshot": frozen.snapshot.snapshot_id,
                    }
                )
        expected["inputs"] = inputs
        batch = create_backup(data.database, data.data_root, tmp_path / "backups")
    assert verify_backup(batch.batch_dir) == batch
    before_batch = tree(batch.batch_dir)
    disk = b"".join(
        path.read_bytes() for path in batch.batch_dir.rglob("*") if path.is_file()
    )
    for private in (
        "queue_update",
        "完整失败原文_SECRET",
        "FREE_UPSTREAM_ERROR_SECRET",
        "THINKING_TRANSCRIPT_SECRET",
        invalid_raw,
    ):
        assert private.encode() not in disk
    expected_file = tmp_path / "expected.json"
    # 子进程使用自己的过期时钟读取 expected,父进程不回收未结算 attempt。
    expired = ScreeningTasks(
        data.database,
        data.data_root,
        clock=lambda: datetime(2026, 1, 1, 0, 10, tzinfo=UTC),
    )
    expected["queries"] = [
        asdict(expired.query(paper_id=paper, stage=stage, snapshot_id=audit_id))
        for paper in (data.paper_id, other.paper_id)
        for stage in ("boundary", "value")
    ]
    expected_file.write_text(json.dumps(expected, default=str))
    unavailable = root.rename(tmp_path / "unavailable")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.a8_recovery_worker",
            str(batch.batch_dir),
            str(tmp_path / "restored"),
            str(tmp_path / "moved"),
            str(expected_file),
            str(root),
            str(unavailable),
        ],
        env={
            "PATH": os.environ["PATH"],
            "PYTHONPATH": str(Path(__file__).parent / "deny_network"),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "read_only_restore": True,
        "remaining_calls": 1,
        "original_paths_blocked": True,
    }
    assert tree(batch.batch_dir) == before_batch
