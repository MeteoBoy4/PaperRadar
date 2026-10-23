"""retry 父链与预算通过自包含备份恢复;语义损坏不能靠重哈希放行。"""

import json
import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import pytest

from paper_radar.backup import create_backup, verify_backup
from paper_radar.backup.manifest import BackupError
from paper_radar.backup.restore import restore_backup
from paper_radar.backup.restore_contract import RestoreError
from paper_radar.papers import PaperFacts
from paper_radar.screening_tasks import ScreeningTasks, SuccessCandidate, SuccessReceipt
from tests.a7_registration_support import archive, request_for
from tests.a7_retry_support import exhaust, retry_for
from tests.backup_support import tree
from tests.test_a7_attempt_backup import rehash_database
from tests.test_paper_mapping import screening_fields
from tests.test_paper_service import observation

NOW = datetime(2026, 1, 1, tzinfo=UTC)
RAW = b'{"boundary":"in_scope","reason_zh":"Atmospheric prediction is studied."}'


def test_moved_restore_keeps_retry_history_success_and_unsettled_budget(
    tmp_path: Path,
) -> None:
    root = tmp_path / "original"
    root.mkdir()
    data = archive(root)
    service = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    boundary = service.register(request_for(data))
    success = service.submit(service.claim(boundary.receipt_id), SuccessCandidate(RAW))
    assert isinstance(success, SuccessReceipt)
    initial = service.register(
        request_for(data, stage="value", original_title_is_zh=False)
    )
    exhaust(service, initial)
    request = retry_for(data, initial)
    successor = service.retry(request)
    service.claim(successor.receipt_id)
    second = PaperFacts(data.database, data.data_root).submit(
        observation(doi="10.1234/failed", fields=screening_fields())
    )
    failed = service.register(request_for(data, paper_id=second.paper_id))
    exhaust(service, failed)
    before = service.query(
        paper_id=data.paper_id, stage="value", snapshot_id=data.snapshot_id
    )
    batch = create_backup(data.database, data.data_root, tmp_path / "backups")
    assert verify_backup(batch.batch_dir) == batch
    root.rename(tmp_path / "unavailable")
    restored = restore_backup(batch.batch_dir, tmp_path / "restored")
    moved = tmp_path / "moved"
    restored.target_dir.rename(moved)
    code = """
import json, sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from paper_radar.screening_tasks import ScreeningTasks
root, paper, second, snapshot, original, successor, success, retry_json = sys.argv[1:9]
blocked = tuple(Path(p).resolve() for p in sys.argv[9:])
def audit(event, args):
    if event in {"open", "sqlite3.connect", "os.listdir", "os.scandir"}:
        if args and isinstance(args[0], (str, bytes)):
            path = Path(args[0]).resolve()
            if any(path == base or base in path.parents for base in blocked):
                raise RuntimeError("original_directory_forbidden")
sys.addaudithook(audit)
instant = datetime.fromisoformat("2026-01-01T00:10:00+00:00")
service = ScreeningTasks(
    Path(root)/"database.sqlite3", Path(root), clock=lambda: instant
)
service.validate_all()
view = service.query(paper_id=paper,stage="value",snapshot_id=snapshot)
assert [task.state for task in view.budgets[0].tasks] == ["failed","lease_expired"]
assert view.current_failures == ()
assert service.retry(json.loads(retry_json)).receipt_id == successor
assert service.load_input(original) == service.load_input(successor)
failures = service.query(paper_id=second,stage="boundary",snapshot_id=snapshot)
assert len(failures.current_failures) == 1
assert service.load_success(success).raw_response.startswith(b'{"boundary"')
assert service.status(successor).state == "lease_expired"
print(json.dumps(asdict(view),default=str))
"""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
            str(moved),
            data.paper_id,
            second.paper_id,
            data.snapshot_id,
            initial.receipt_id,
            successor.receipt_id,
            success.success_id,
            json.dumps(request),
            str(root),
            str(tmp_path / "unavailable"),
            str(batch.batch_dir),
        ],
        env={
            "PATH": os.environ["PATH"],
            "PYTHONPATH": str(Path(__file__).parent / "deny_network"),
        },
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    recovered = json.loads(result.stdout)
    assert (
        recovered["budgets"][0]["latest_generation"]
        == before.budgets[0].latest_generation
    )
    assert recovered["budgets"][0]["tasks"][1]["used_attempts"] == 1
    assert (
        request["reason"] not in result.stdout and request["actor"] not in result.stdout
    )


@pytest.mark.parametrize(
    "damage",
    [
        "gap",
        "cycle",
        "missing_parent",
        "request_digest",
        "unsettled_parent",
        "missing_retry_request",
    ],
)
def test_retry_semantic_damage_rejected_by_validation_backup_and_restore(
    tmp_path: Path, damage: str
) -> None:
    data = archive(tmp_path / "source")
    service = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    initial = service.register(request_for(data))
    exhaust(service, initial)
    successor = service.retry(retry_for(data, initial))
    batch = create_backup(data.database, data.data_root, tmp_path / "backups")
    with closing(sqlite3.connect(batch.batch_dir / "database.sqlite3")) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        if damage == "gap":
            connection.execute(
                "UPDATE screening_tasks SET generation=2 WHERE task_id=?",
                (successor.task_id,),
            )
        elif damage == "cycle":
            connection.execute(
                "UPDATE screening_tasks SET parent_task_id=? WHERE task_id=?",
                (successor.task_id, initial.task_id),
            )
        elif damage == "missing_parent":
            connection.execute(
                "UPDATE screening_tasks SET parent_task_id=NULL WHERE task_id=?",
                (successor.task_id,),
            )
        elif damage == "request_digest":
            connection.execute(
                "UPDATE screening_requests SET request_sha256=? WHERE receipt_id=?",
                ("0" * 64, successor.receipt_id),
            )
        elif damage == "unsettled_parent":
            connection.execute(
                "DELETE FROM screening_failures WHERE task_id=? AND attempt_no=2",
                (initial.task_id,),
            )
        else:
            connection.execute(
                "DELETE FROM screening_requests WHERE receipt_id=?",
                (successor.receipt_id,),
            )
        connection.commit()
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()
    rehash_database(batch.batch_dir)
    before = tree(batch.batch_dir)
    with pytest.raises(BackupError) as error:
        verify_backup(batch.batch_dir)
    assert error.value.reason == "registration_invalid"
    target = tmp_path / "rejected"
    with pytest.raises(RestoreError) as error:
        restore_backup(batch.batch_dir, target)
    assert error.value.reason == "registration_invalid"
    assert tree(batch.batch_dir) == before and not target.exists()
