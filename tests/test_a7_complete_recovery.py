"""同一 WAL 档案库的完整任务历史在隔离新进程恢复后仍可解释和有限继续。"""

import json
import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

from paper_radar.backup import create_backup, verify_backup
from paper_radar.config import compile_config
from paper_radar.papers import PaperFacts
from paper_radar.screening_tasks import ScreeningTasks, SuccessCandidate, SuccessReceipt
from paper_radar.storage.artifacts import ArtifactStore
from tests.a7_registration_support import Archive, request_for
from tests.a7_retry_support import exhaust, retry_for
from tests.a7_value_support import value_payload
from tests.backup_support import tree
from tests.config_test_support import value_inputs
from tests.test_paper_mapping import screening_fields
from tests.test_paper_service import observation

NOW = datetime(2026, 1, 1, tzinfo=UTC)
BOUNDARY = b'{"boundary":"in_scope","reason_zh":"Atmospheric prediction is studied."}'


def test_new_process_restores_complete_wal_history_and_continues_remaining_budget(
    tmp_path: Path,
) -> None:
    root = tmp_path / "original"
    settings, database = value_inputs(
        root,
        "\n  - id: extreme-rainfall\n    name: 极端降水\n"
        "    description: 区域极端降水诊断\n    enabled: true\n",
    )
    snapshot = compile_config(settings, database)
    data_root = root / "data"
    papers = PaperFacts(database, data_root)
    first = papers.submit(
        observation(doi="10.1/pre", version_kind="preprint", fields=screening_fields())
    )
    assert first.paper_id and first.version_id
    data = Archive(
        settings,
        database,
        data_root,
        snapshot.snapshot_id,
        first.paper_id,
        first.version_id,
    )
    now = NOW
    tasks = ScreeningTasks(database, data_root, clock=lambda: now)
    old_boundary = tasks.register(request_for(data))
    historical = tasks.run_once(
        old_boundary.receipt_id, lambda *_: SuccessCandidate(BOUNDARY)
    )
    assert isinstance(historical, SuccessReceipt)
    # 仅 boundary 语义改变: 同库同时有历史 boundary 与当前 value 制品。
    (root / "prompts/screening/boundary-v2.md").write_bytes(b"New boundary prompt\n")
    settings.write_text(settings.read_text().replace("boundary: v1", "boundary: v2", 1))
    current = compile_config(settings, database)
    boundary = tasks.register(request_for(data, snapshot_id=current.snapshot_id))
    current_boundary = tasks.run_once(
        boundary.receipt_id, lambda *_: SuccessCandidate(BOUNDARY)
    )
    value_request = request_for(
        data, snapshot_id=current.snapshot_id, stage="value", original_title_is_zh=False
    )
    value = tasks.register(value_request)
    raw = (
        b" \n"
        + value_payload(
            topic_ids=["extreme-rainfall"], display_title_zh="极端降水诊断方法"
        )
        + b"\n "
    )
    current_value = tasks.run_once(
        value.receipt_id, lambda *_: SuccessCandidate(raw, input_tokens=0)
    )
    assert isinstance(current_boundary, SuccessReceipt)
    assert isinstance(current_value, SuccessReceipt)
    cached = tasks.register({**value_request, "scheduled_day": "2026-01-02"})
    assert cached.cached_success_id == current_value.success_id
    other = papers.submit(observation(doi="10.1234/other", fields=screening_fields()))
    assert other.paper_id
    failed = tasks.register(
        request_for(data, paper_id=other.paper_id, snapshot_id=current.snapshot_id)
    )
    exhaust(tasks, failed)
    parent = tasks.register({**value_request, "paper_id": other.paper_id})
    # 安全 A1 字段路径必须穿过失败、retry 与恢复查询。
    for _ in range(2):
        tasks.run_once(
            parent.receipt_id,
            lambda *_: SuccessCandidate(value_payload(research_value=6)),
        )
    retry = retry_for(
        data, parent, paper_id=other.paper_id, snapshot_id=current.snapshot_id
    )
    successor = tasks.retry(retry)
    tasks.claim(successor.receipt_id)
    # 发布竞争可留下完整未引用响应; 不要求每个响应都被任务引用。
    ArtifactStore(database, data_root).publish_single(
        "model_success_response", (b"\n" + raw,)
    )
    now += timedelta(seconds=600)
    ids = {
        "paper": data.paper_id,
        "version": data.version_id,
        "other": other.paper_id,
        "snapshot": current.snapshot_id,
        "old_snapshot": snapshot.snapshot_id,
        "historical": historical.success_id,
        "boundary_success": current_boundary.success_id,
        "value_success": current_value.success_id,
        "value": value.receipt_id,
        "cached": cached.receipt_id,
        "failed": failed.receipt_id,
        "parent": parent.receipt_id,
        "successor": successor.receipt_id,
        "retry": retry,
        "value_request": value_request,
    }
    expected = [
        asdict(
            tasks.query(paper_id=paper, stage=stage, snapshot_id=current.snapshot_id)
        )
        for paper in (data.paper_id, other.paper_id)
        for stage in ("boundary", "value")
    ]
    with closing(sqlite3.connect(database)) as reader:
        reader.execute("PRAGMA journal_mode=WAL")
        reader.execute("BEGIN")
        reader.execute("SELECT count(*) FROM screening_requests").fetchone()
        tasks.register({**value_request, "scheduled_day": "2026-01-03"})
        assert database.with_name(database.name + "-wal").stat().st_size > 0
        # 这个新请求也属于可重建历史。
        expected[1] = asdict(
            tasks.query(
                paper_id=data.paper_id, stage="value", snapshot_id=current.snapshot_id
            )
        )
        ids["payloads"] = {
            receipt.receipt_id: tasks.load_input(
                receipt.receipt_id
            ).stage_input.payload_bytes.hex()
            for paper_id in (data.paper_id, other.paper_id)
            for receipt in tasks.receipts(paper_id)
        }
        batch = create_backup(database, data_root, tmp_path / "backups")
    assert verify_backup(batch.batch_dir) == batch
    batch_before = tree(batch.batch_dir)
    unavailable = root.rename(tmp_path / "unavailable")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.a7_recovery_support",
            str(batch.batch_dir),
            str(tmp_path / "restored"),
            str(tmp_path / "moved"),
            json.dumps(ids),
            json.dumps(expected, default=str),
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
        timeout=45,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "read_only": True,
        "remaining_calls": 1,
        "derived_applicability": True,
    }
    assert tree(batch.batch_dir) == batch_before
