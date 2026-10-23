"""成功闭包通过既有备份/隔离恢复边界重建,不改变备份格式。"""

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
from paper_radar.storage.artifacts import ArtifactStore
from tests.a7_registration_support import archive, request_for
from tests.backup_support import tree
from tests.test_a7_attempt_backup import rehash_database
from tests.test_paper_mapping import screening_fields
from tests.test_paper_service import observation

NOW = datetime(2026, 1, 1, tzinfo=UTC)
RAW = b' \n{"boundary":"in_scope","reason_zh":"Atmospheric models are evaluated."}\n '


def test_moved_restore_replays_history_without_original_paths(
    tmp_path: Path,
) -> None:
    root = tmp_path / "original"
    root.mkdir()
    data = archive(root)
    tasks = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    first = tasks.register(request_for(data))
    success = tasks.submit(
        tasks.claim(first.receipt_id), SuccessCandidate(RAW, input_tokens=0)
    )
    assert isinstance(success, SuccessReceipt)
    cached = tasks.register(request_for(data, scheduled_day="2026-01-02"))
    assert cached.cached_success_id == success.success_id
    active = tasks.register(
        request_for(data, stage="value", original_title_is_zh=False)
    )
    tasks.claim(active.receipt_id)
    other = PaperFacts(data.database, data.data_root).submit(
        observation(doi="10.1234/invalid-output", fields=screening_fields())
    )
    assert other.paper_id
    failed = tasks.register(request_for(data, paper_id=other.paper_id))
    tasks.submit(tasks.claim(failed.receipt_id), SuccessCandidate(b"{"))
    orphan = ArtifactStore(data.database, data.data_root).publish_single(
        "model_success_response",
        (b'{"boundary":"uncertain","reason_zh":"Atmospheric evidence is limited."}',),
    )
    batch = create_backup(data.database, data.data_root, tmp_path / "backups")
    assert verify_backup(batch.batch_dir) == batch
    assert batch.manifest.format_version == 1
    assert (
        sum(item.kind == "model_success_response" for item in batch.manifest.artifacts)
        == 2
    )
    unavailable = tmp_path / "unavailable"
    root.rename(unavailable)
    restored = restore_backup(batch.batch_dir, tmp_path / "restored")
    moved = tmp_path / "moved"
    restored.target_dir.rename(moved)
    code = r"""
import json, sys
from datetime import UTC, datetime
from pathlib import Path
from paper_radar.screening_tasks import ScreeningTasks
from paper_radar.storage.artifacts import ArtifactStore
blocked = tuple(Path(p).resolve() for p in sys.argv[7:])
def audit(event, args):
    if event in {"open", "sqlite3.connect"} and isinstance(args[0], (str, bytes)):
        path = Path(args[0]).resolve()
        if any(path == base or base in path.parents for base in blocked):
            raise RuntimeError("original_directory_forbidden")
sys.addaudithook(audit)
root = Path(sys.argv[1])
tasks = ScreeningTasks(
    root / "database.sqlite3", root,
    clock=lambda: datetime(2026,1,1,tzinfo=UTC)
)
tasks.validate_all()
loaded = tasks.load_success(sys.argv[2])
assert loaded.raw_response == (
    b' \n{"boundary":"in_scope",'
    b'"reason_zh":"Atmospheric models are evaluated."}\n '
)
assert loaded.audit["input_tokens"] == 0 and loaded.audit["output_tokens"] is None
assert loaded.output.boundary == "in_scope"
first, cached, active, failed = sys.argv[3:7]
assert tasks.get_receipt(first).cached_success_id is None
assert tasks.get_receipt(cached).cached_success_id == loaded.receipt.success_id
assert tasks.status(first).state == "succeeded"
assert tasks.status(first).used_attempts == 1
assert tasks.status(active).state == "running"
assert tasks.status(active).used_attempts == 1
assert tasks.status(failed).last_failure == "output_invalid"
assert tasks.status(failed).used_attempts == 1
print(json.dumps({"success":True,"active":True,"failure":True}))
"""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
            str(moved),
            success.success_id,
            first.receipt_id,
            cached.receipt_id,
            active.receipt_id,
            failed.receipt_id,
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
    assert json.loads(result.stdout) == {
        "success": True,
        "active": True,
        "failure": True,
    }
    store = ArtifactStore(moved / "database.sqlite3", moved)
    assert (
        store.read_artifact(orphan.artifact_id)["payload"]
        == b'{"boundary":"uncertain","reason_zh":"Atmospheric evidence is limited."}'
    )


@pytest.mark.parametrize(
    "damage",
    [
        "structure",
        "raw_reference",
        "executor_kind",
        "double_settlement",
        "failure_location",
    ],
)
def test_rehashed_success_semantic_damage_is_rejected_by_verify_and_restore(
    tmp_path: Path, damage: str
) -> None:
    root = tmp_path / "source"
    root.mkdir()
    data = archive(root)
    tasks = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    receipt = tasks.register(request_for(data))
    success = tasks.submit(tasks.claim(receipt.receipt_id), SuccessCandidate(RAW))
    assert isinstance(success, SuccessReceipt)
    other = PaperFacts(data.database, data.data_root).submit(
        observation(doi="10.1234/invalid-output", fields=screening_fields())
    )
    assert other.paper_id
    failed = tasks.register(request_for(data, paper_id=other.paper_id))
    tasks.submit(tasks.claim(failed.receipt_id), SuccessCandidate(b"{"))
    replacement = ArtifactStore(data.database, data.data_root).publish_single(
        "model_success_response",
        (b'{"boundary":"out_of_scope","reason_zh":"The subject is oceanic biology."}',),
    )
    batch = create_backup(data.database, data.data_root, tmp_path / "backups")
    with closing(sqlite3.connect(batch.batch_dir / "database.sqlite3")) as connection:
        if damage == "structure":
            connection.execute("UPDATE screening_successes SET structured_json='{}'")
        elif damage == "raw_reference":
            connection.execute(
                "UPDATE screening_successes SET artifact_id=?",
                (replacement.artifact_id,),
            )
        elif damage == "executor_kind":
            audit = json.loads(
                connection.execute(
                    "SELECT audit_json FROM screening_successes"
                ).fetchone()[0]
            )
            audit["executor_kind"] = "production"
            connection.execute(
                "UPDATE screening_successes SET audit_json=?",
                (
                    json.dumps(
                        audit, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                    ),
                ),
            )
        elif damage == "double_settlement":
            connection.execute(
                "INSERT INTO screening_failures"
                "(task_id,attempt_no,kind,origin,settled_at) "
                "VALUES (?,1,'timeout','executor',?)",
                (success.task_id, NOW.isoformat(timespec="microseconds")),
            )
        else:
            issues = json.loads(
                connection.execute(
                    "SELECT issues_json FROM screening_failures"
                ).fetchone()[0]
            )
            issues[0]["location"] = "PRIVATE_FAILURE_OUTPUT_SENTINEL"
            connection.execute(
                "UPDATE screening_failures SET issues_json=?",
                (
                    json.dumps(
                        issues,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                ),
            )
        connection.commit()
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    rehash_database(batch.batch_dir)
    before = tree(batch.batch_dir)
    with pytest.raises(BackupError) as error:
        verify_backup(batch.batch_dir)
    assert error.value.reason == "registration_invalid"
    assert "PRIVATE_FAILURE_OUTPUT_SENTINEL" not in str(error.value)
    target = tmp_path / "rejected"
    with pytest.raises(RestoreError) as rejected:
        restore_backup(batch.batch_dir, target)
    assert rejected.value.reason == "registration_invalid"
    assert tree(batch.batch_dir) == before
    assert not target.exists()
