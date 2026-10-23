"""合法 SQLite 结构不能掩盖任务语义损坏;预算硬约束也不为坏例放宽。"""

import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from paper_radar.backup import create_backup, verify_backup
from paper_radar.backup.manifest import BackupError
from paper_radar.backup.restore import restore_backup
from paper_radar.backup.restore_contract import RestoreError
from paper_radar.screening_tasks import (
    FailureKind,
    FailureReport,
    ScreeningTasks,
    SuccessCandidate,
    SuccessReceipt,
    TaskError,
    TaskReason,
)
from tests.a7_registration_support import archive, request_for
from tests.backup_support import tree
from tests.test_a7_attempt_backup import rehash_database

NOW = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.mark.parametrize(
    "damage",
    [
        "request_task",
        "attempt_gap",
        "second_without_settlement",
        "lease_owner",
        "success_and_failure",
    ],
)
def test_rehashed_attempt_semantic_damage_rejected_without_source_or_target_write(
    tmp_path: Path,
    damage: str,
) -> None:
    data = archive(tmp_path / "source")
    now = NOW
    tasks = ScreeningTasks(data.database, data.data_root, clock=lambda: now)
    receipt = tasks.register(request_for(data))
    tasks.fail(tasks.claim(receipt.receipt_id), FailureReport(FailureKind.TIMEOUT))
    second = tasks.claim(receipt.receipt_id)
    now += timedelta(seconds=60)
    other = tasks.register(request_for(data, stage="value", original_title_is_zh=False))
    tasks.claim(other.receipt_id)
    if damage == "success_and_failure":
        success = tasks.submit(
            second,
            SuccessCandidate(
                b'{"boundary":"in_scope","reason_zh":"Atmospheric models are studied."}'
            ),
        )
        assert isinstance(success, SuccessReceipt)
    batch = create_backup(data.database, data.data_root, tmp_path / "backups")
    database = batch.batch_dir / "database.sqlite3"
    with closing(sqlite3.connect(database)) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        if damage == "request_task":
            connection.execute(
                "UPDATE screening_attempts SET receipt_id=? "
                "WHERE task_id=? AND attempt_no=2",
                (other.receipt_id, receipt.task_id),
            )
        elif damage == "attempt_gap":
            connection.execute(
                "DELETE FROM screening_failures WHERE task_id=?", (receipt.task_id,)
            )
            connection.execute(
                "DELETE FROM screening_leases WHERE task_id=? AND attempt_no=1",
                (receipt.task_id,),
            )
            connection.execute(
                "DELETE FROM screening_attempts WHERE task_id=? AND attempt_no=1",
                (receipt.task_id,),
            )
        elif damage == "second_without_settlement":
            connection.execute(
                "DELETE FROM screening_failures WHERE task_id=?", (receipt.task_id,)
            )
        elif damage == "lease_owner":
            # 两条真实租期互换仍满足 FK/PK,却让较晚领取的任务持有另一任务的早租期。
            expiry = connection.execute(
                "SELECT expires_at FROM screening_leases "
                "WHERE task_id=? AND attempt_no=2",
                (receipt.task_id,),
            ).fetchone()[0]
            other_expiry = connection.execute(
                "SELECT expires_at FROM screening_leases WHERE task_id=?",
                (other.task_id,),
            ).fetchone()[0]
            connection.execute(
                "UPDATE screening_leases SET expires_at=? "
                "WHERE task_id=? AND attempt_no=2",
                (other_expiry, receipt.task_id),
            )
            connection.execute(
                "UPDATE screening_leases SET expires_at=? WHERE task_id=?",
                (expiry, other.task_id),
            )
        else:
            connection.execute(
                "INSERT INTO screening_failures "
                "(task_id,attempt_no,kind,origin,settled_at) "
                "VALUES (?,2,'timeout','executor',?)",
                (receipt.task_id, now.isoformat(timespec="microseconds")),
            )
        connection.commit()
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    rehash_database(batch.batch_dir)
    before = tree(batch.batch_dir)
    with pytest.raises(TaskError) as invalid:
        ScreeningTasks(database, batch.batch_dir).validate_all()
    assert invalid.value.reason == TaskReason.CORRUPT_REFERENCE
    with pytest.raises(BackupError) as error:
        verify_backup(batch.batch_dir)
    assert error.value.reason == "registration_invalid"
    target = tmp_path / "rejected"
    with pytest.raises(RestoreError) as rejected:
        restore_backup(batch.batch_dir, target)
    assert rejected.value.reason == "registration_invalid"
    assert tree(batch.batch_dir) == before and not target.exists()


@pytest.mark.parametrize(("attempt_no", "constraint"), [(3, "CHECK"), (1, "UNIQUE")])
def test_over_budget_and_duplicate_attempt_numbers_are_structurally_rejected(
    tmp_path: Path,
    attempt_no: int,
    constraint: str,
) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    receipt = tasks.register(request_for(data))
    tasks.fail(tasks.claim(receipt.receipt_id), FailureReport(FailureKind.TIMEOUT))
    tasks.claim(receipt.receipt_id)
    with closing(sqlite3.connect(data.database)) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        before = tuple(connection.iterdump())
        with pytest.raises(
            sqlite3.IntegrityError, match=constraint + " constraint failed"
        ):
            connection.execute(
                "UPDATE screening_attempts SET attempt_no=? "
                "WHERE task_id=? AND attempt_no=2",
                (attempt_no, receipt.task_id),
            )
        connection.rollback()
        assert tuple(connection.iterdump()) == before
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()
    tasks.validate_all()
