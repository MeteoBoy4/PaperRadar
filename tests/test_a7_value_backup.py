"""非空 value 成功通过备份恢复闭包重建同一历史权威上下文。"""

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
from paper_radar.config import compile_config
from paper_radar.papers import PaperFacts
from paper_radar.screening_tasks import (
    ScreeningTasks,
    SuccessCandidate,
    SuccessReceipt,
    TaskError,
    TaskReason,
)
from paper_radar.storage.artifacts import ArtifactStore
from tests.a7_registration_support import request_for
from tests.a7_value_support import value_archive, value_payload
from tests.backup_support import tree
from tests.config_projection_support import new_yaml_version
from tests.test_a7_attempt_backup import rehash_database
from tests.test_paper_mapping import screening_fields
from tests.test_paper_service import observation

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_moved_value_restore_rebuilds_context_without_original_directories(
    tmp_path: Path,
) -> None:
    root = tmp_path / "original"
    root.mkdir()
    data = value_archive(root)
    service = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    request = request_for(data, stage="value", original_title_is_zh=False)
    receipt = service.register(request)
    raw = (
        b" \n"
        + value_payload(
            topic_ids=["extreme-rainfall"], display_title_zh="极端降水诊断方法"
        )
        + b"\n "
    )
    success = service.run_once(
        receipt.receipt_id, lambda *_: SuccessCandidate(raw, input_tokens=0)
    )
    assert isinstance(success, SuccessReceipt)
    cached = service.register({**request, "scheduled_day": "2026-01-02"})
    assert cached.cached_success_id == success.success_id
    boundary = service.register(request_for(data))
    service.run_once(
        boundary.receipt_id,
        lambda *_: SuccessCandidate(
            b'{"boundary":"out_of_scope","reason_zh":"The subject is oceanic biology."}'
        ),
    )
    other = PaperFacts(data.database, data.data_root).submit(
        observation(doi="10.1234/value-failed", fields=screening_fields())
    )
    assert other.paper_id
    failed = service.register({**request, "paper_id": other.paper_id})
    for _ in range(2):
        service.run_once(failed.receipt_id, lambda *_: SuccessCandidate(b"{}"))
    active = service.register(request_for(data, paper_id=other.paper_id))
    service.claim(active.receipt_id)
    new_yaml_version(
        data.settings,
        "topics",
        lambda content: content["topics"][0].update(enabled=False),
    )
    newer = compile_config(data.settings, data.database)
    batch = create_backup(data.database, data.data_root, tmp_path / "backups")
    assert verify_backup(batch.batch_dir) == batch
    unavailable = root.rename(tmp_path / "unavailable")
    restored = restore_backup(batch.batch_dir, tmp_path / "restored")
    moved = restored.target_dir.rename(tmp_path / "moved")
    before = tree(moved)
    code = r"""
import json, sys
from datetime import UTC, datetime
from pathlib import Path
from paper_radar.screening import ValuePredictionOutput
from paper_radar.screening_tasks import ScreeningTasks
from tests.a7_value_support import value_payload
(
    root, success, original, cached, failed, active, paper, historical, newer
) = sys.argv[1:10]
blocked = tuple(Path(p).resolve() for p in sys.argv[10:])
def audit(event, args):
    if event in {"open", "sqlite3.connect"} and isinstance(args[0], (str, bytes)):
        path = Path(args[0]).resolve()
        if any(path == base or base in path.parents for base in blocked):
            raise RuntimeError("original_directory_forbidden")
sys.addaudithook(audit)
tasks = ScreeningTasks(
    Path(root) / "database.sqlite3", Path(root),
    clock=lambda: datetime(2026,1,1,tzinfo=UTC),
)
tasks.validate_all()
loaded = tasks.load_success(success)
assert isinstance(loaded.output, ValuePredictionOutput)
assert loaded.raw_response == b" \n" + value_payload(
    topic_ids=["extreme-rainfall"], display_title_zh="极端降水诊断方法"
) + b"\n "
assert loaded.output.topic_ids == ["extreme-rainfall"]
assert loaded.output.display_title_zh == "极端降水诊断方法"
assert loaded.audit["input_tokens"] == 0 and loaded.audit["output_tokens"] is None
frozen = tasks.load_input(original)
assert frozen.snapshot.snapshot_id == historical
assert frozen.original_title_is_zh is False
context = frozen.stage_input.value_prediction_context(
    frozen.snapshot, original_title_is_zh=frozen.original_title_is_zh
)
assert context.enabled_topic_ids == frozenset({"extreme-rainfall"})
assert tasks.get_receipt(original).cached_success_id is None
assert tasks.get_receipt(cached).cached_success_id == success
assert tasks.status(original).state == "succeeded"
assert tasks.status(original).used_attempts == 1
assert tasks.status(failed).state == "failed"
assert tasks.status(failed).used_attempts == 2
assert tasks.status(active).state == "running"
assert tasks.status(active).used_attempts == 1
for snapshot, expected in ((historical,"current"),(newer,"historical")):
    view = tasks.query_successes(paper_id=paper,stage="value",snapshot_id=snapshot)[0]
    assert view.applicability == expected
print(json.dumps({"success": True, "context": True, "history": True}))
"""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
            str(moved),
            success.success_id,
            receipt.receipt_id,
            cached.receipt_id,
            failed.receipt_id,
            active.receipt_id,
            data.paper_id,
            data.snapshot_id,
            newer.snapshot_id,
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
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "success": True,
        "context": True,
        "history": True,
    }
    assert tree(moved) == before


@pytest.mark.parametrize(
    "damage",
    ["snapshot", "projection", "language", "structure", "raw_reference", "model_audit"],
)
def test_rehashed_value_damage_rejected_by_load_verify_and_restore(
    tmp_path: Path, damage: str
) -> None:
    root = tmp_path / "source"
    root.mkdir()
    data = value_archive(root)
    service = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    receipt = service.register(
        request_for(data, stage="value", original_title_is_zh=False)
    )
    raw = value_payload(
        topic_ids=["extreme-rainfall"], display_title_zh="极端降水诊断方法"
    )
    success = service.run_once(receipt.receipt_id, lambda *_: SuccessCandidate(raw))
    assert isinstance(success, SuccessReceipt)
    new_yaml_version(
        data.settings,
        "topics",
        lambda content: content["topics"][0].update(enabled=False),
    )
    newer = compile_config(data.settings, data.database)
    replacement = ArtifactStore(data.database, data.data_root).publish_single(
        "model_success_response", (value_payload(research_value=5),)
    )
    batch = create_backup(data.database, data.data_root, tmp_path / "backups")
    database = batch.batch_dir / "database.sqlite3"
    with closing(sqlite3.connect(database)) as connection:
        if damage == "snapshot":
            connection.execute(
                "UPDATE screening_budgets SET snapshot_id=?", (newer.snapshot_id,)
            )
        elif damage == "projection":
            payload = json.loads(
                connection.execute("SELECT payload FROM screening_inputs").fetchone()[0]
            )
            payload["config_projection"]["projection_id"] = "0" * 64
            connection.execute(
                "UPDATE screening_inputs SET payload=?",
                (
                    json.dumps(
                        payload,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode(),
                ),
            )
        elif damage == "language":
            connection.execute("UPDATE screening_budgets SET original_title_is_zh=1")
        elif damage == "structure":
            connection.execute("UPDATE screening_successes SET structured_json='{}'")
        elif damage == "raw_reference":
            connection.execute(
                "UPDATE screening_successes SET artifact_id=?",
                (replacement.artifact_id,),
            )
        else:
            audit = json.loads(
                connection.execute(
                    "SELECT audit_json FROM screening_successes"
                ).fetchone()[0]
            )
            audit["reported_model"] = "PRIVATE_MODEL_SENTINEL"
            connection.execute(
                "UPDATE screening_successes SET audit_json=?",
                (
                    json.dumps(
                        audit, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                    ),
                ),
            )
        connection.commit()
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    rehash_database(batch.batch_dir)
    before = tree(batch.batch_dir)
    with pytest.raises(TaskError) as invalid:
        ScreeningTasks(database, batch.batch_dir).load_success(success.success_id)
    assert invalid.value.reason == TaskReason.CORRUPT_REFERENCE
    assert "PRIVATE_MODEL_SENTINEL" not in str(invalid.value)
    with pytest.raises(BackupError) as error:
        verify_backup(batch.batch_dir)
    assert error.value.reason == "registration_invalid"
    target = tmp_path / "rejected"
    with pytest.raises(RestoreError) as rejected:
        restore_backup(batch.batch_dir, target)
    assert rejected.value.reason == "registration_invalid"
    assert tree(batch.batch_dir) == before and not target.exists()
