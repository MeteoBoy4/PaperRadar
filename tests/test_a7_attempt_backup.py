"""A7-03 备份闭包保留预算及租约,恢复不执行任务。"""

import hashlib
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
from paper_radar.screening_tasks import FailureKind, FailureReport, ScreeningTasks
from tests.a7_registration_support import archive, request_for
from tests.backup_support import tree
from tests.test_paper_mapping import screening_fields
from tests.test_paper_service import observation

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def rehash_database(batch_dir: Path) -> None:
    database = batch_dir / "database.sqlite3"
    manifest_path = batch_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    raw = database.read_bytes()
    manifest["database"].update(
        sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw)
    )
    manifest_path.write_bytes(
        (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode()
    )


def test_rehashed_missing_lease_is_rejected_by_existing_backup_integrity_hook(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    root.mkdir()
    data = archive(root)
    tasks = ScreeningTasks(data.database, clock=lambda: NOW)
    receipt = tasks.register(request_for(data))
    tasks.claim(receipt.receipt_id)
    batch = create_backup(data.database, data.data_root, tmp_path / "backups")
    with closing(sqlite3.connect(batch.batch_dir / "database.sqlite3")) as connection:
        connection.execute("DELETE FROM screening_leases")
        connection.commit()
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    rehash_database(batch.batch_dir)
    before = tree(batch.batch_dir)
    with pytest.raises(BackupError) as failure:
        verify_backup(batch.batch_dir)
    assert failure.value.reason == "registration_invalid"
    target = tmp_path / "rejected"
    with pytest.raises(RestoreError) as restored:
        restore_backup(batch.batch_dir, target)
    assert restored.value.reason == "registration_invalid"
    assert tree(batch.batch_dir) == before
    assert not target.exists()


def test_moved_restore_keeps_active_failed_and_expired_facts_with_independent_history(
    tmp_path: Path,
) -> None:
    root = tmp_path / "original"
    root.mkdir()
    data = archive(root)
    now = NOW
    tasks = ScreeningTasks(data.database, clock=lambda: now)
    active = tasks.register(request_for(data))
    failed = tasks.register(
        request_for(data, stage="value", original_title_is_zh=False)
    )
    other = PaperFacts(data.database, data.data_root).submit(
        observation(doi="10.1234/expired", fields=screening_fields())
    )
    assert other.paper_id
    expired = tasks.register(request_for(data, paper_id=other.paper_id))
    active_claim = tasks.claim(active.receipt_id)
    for _ in range(2):
        tasks.fail(tasks.claim(failed.receipt_id), FailureReport(FailureKind.TIMEOUT))
    tasks.fail(tasks.claim(expired.receipt_id), FailureReport(FailureKind.CANCELLED))
    expired_claim = tasks.claim(expired.receipt_id)
    now = expired_claim.expires_at
    tasks.renew(active_claim.renewal_handle)
    receipts = (active, failed, expired)
    expected = {
        active.receipt_id: {
            "state": "running",
            "used": 1,
            "remaining": 1,
            "failure": None,
            "fingerprint": active.fingerprint,
        },
        failed.receipt_id: {
            "state": "failed",
            "used": 2,
            "remaining": 0,
            "failure": "timeout",
            "fingerprint": failed.fingerprint,
        },
        expired.receipt_id: {
            "state": "lease_expired",
            "used": 2,
            "remaining": 0,
            "failure": "cancelled",
            "fingerprint": expired.fingerprint,
        },
    }
    with closing(sqlite3.connect(data.database)) as reader:
        reader.execute("BEGIN")
        reader.execute("SELECT count(*) FROM screening_requests")
        tasks.register(request_for(data, scheduled_day="2026-01-02"))
        assert data.database.with_name(data.database.name + "-wal").stat().st_size > 0
        batch = create_backup(data.database, data.data_root, tmp_path / "backups")
    assert verify_backup(batch.batch_dir) == batch
    # 旧备份只保留其拍摄点;源库在之后独立用尽第二次预算。
    tasks.fail(active_claim, FailureReport(FailureKind.TIMEOUT))
    tasks.fail(tasks.claim(active.receipt_id), FailureReport(FailureKind.TIMEOUT))
    assert tasks.status(active.receipt_id).state == "failed"
    unavailable = tmp_path / "unavailable"
    root.rename(unavailable)
    restored = restore_backup(batch.batch_dir, tmp_path / "restored")
    moved = tmp_path / "moved"
    restored.target_dir.rename(moved)
    code = """
import json, sys
from datetime import datetime
from pathlib import Path
from paper_radar.screening_tasks import ScreeningTasks
blocked = tuple(Path(p).resolve() for p in sys.argv[4:])
def audit(event, args):
    if event == "open" and isinstance(args[0], (str, bytes)):
        path = Path(args[0]).resolve()
        if any(path == base or base in path.parents for base in blocked):
            raise RuntimeError("original_directory_forbidden")
sys.addaudithook(audit)
now = datetime.fromisoformat(sys.argv[3])
tasks = ScreeningTasks(
    Path(sys.argv[1]) / "database.sqlite3", Path(sys.argv[1]), clock=lambda: now
)
tasks.validate_all()
result = {}
for receipt_id in json.loads(sys.argv[2]):
    status = tasks.status(receipt_id)
    result[receipt_id] = {"state": status.state, "used": status.used_attempts,
        "remaining": status.remaining_attempts, "failure": status.last_failure,
        "fingerprint": tasks.load_input(receipt_id).fingerprint}
print(json.dumps(result, sort_keys=True))
"""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
            str(moved),
            json.dumps([receipt.receipt_id for receipt in receipts]),
            now.isoformat(),
            str(root),
            str(unavailable),
            str(batch.batch_dir),
        ],
        env={
            "PATH": os.environ["PATH"],
            "PYTHONPATH": str(Path(__file__).parent / "deny_network"),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected
    copied = ScreeningTasks(moved / "database.sqlite3", moved, clock=lambda: now)
    before = copied.database.read_bytes()
    assert copied.status(expired.receipt_id).state == "lease_expired"
    copied.validate_all()
    assert copied.database.read_bytes() == before
    # 同一旧能力在独立副本仍属未结算attempt;不承诺追回旧备份之后的源库attempt。
    copied.fail(active_claim, FailureReport(FailureKind.CANCELLED))
    assert copied.claim(active.receipt_id).attempt_no == 2
    assert copied.status(active.receipt_id).used_attempts == 2
    assert copied.reclaim(expired.receipt_id).state == "failed"
    copied.validate_all()
