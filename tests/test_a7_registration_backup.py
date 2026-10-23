"""登记事实的备份语义闭包与无原目录回放。"""

from pathlib import Path

import pytest

from paper_radar.backup import create_backup, verify_backup
from paper_radar.backup.restore import restore_backup
from paper_radar.config import compile_config
from paper_radar.papers import PaperFacts
from paper_radar.screening_tasks import ScreeningTasks
from tests.config_test_support import value_inputs
from tests.test_paper_mapping import screening_fields
from tests.test_paper_service import observation


def test_backup_restores_nonempty_frozen_registration_without_original_root(
    tmp_path: Path,
) -> None:
    root = tmp_path / "original"
    root.mkdir()
    settings, database = value_inputs(root)
    snapshot = compile_config(settings, database)
    paper = PaperFacts(database, root / "data").submit(
        observation(fields=screening_fields())
    )
    assert paper.paper_id
    tasks = ScreeningTasks(database)
    receipt = tasks.register(
        {
            "paper_id": paper.paper_id,
            "snapshot_id": snapshot.snapshot_id,
            "stage": "value",
            "original_title_is_zh": False,
            "source": "scheduled",
            "scheduled_day": "2026-01-01",
        }
    )
    expected = tasks.load_input(receipt.receipt_id)
    tasks.validate_all()
    batch = create_backup(database, root / "data", tmp_path / "backups")
    assert verify_backup(batch.batch_dir) == batch
    root.rename(tmp_path / "unavailable")
    restored = restore_backup(batch.batch_dir, tmp_path / "restored")
    moved = tmp_path / "moved"
    restored.target_dir.rename(moved)
    copied = ScreeningTasks(moved / "database.sqlite3", moved)
    copied.validate_all()
    assert copied.load_input(receipt.receipt_id) == expected
    assert copied.get_receipt(receipt.receipt_id) == receipt


def test_new_process_only_replays_moved_archive_with_original_access_denied(
    tmp_path: Path,
) -> None:
    import hashlib
    import json
    import os
    import sqlite3
    import subprocess
    import sys
    from contextlib import closing

    from tests.a7_registration_support import archive, request_for

    root = tmp_path / "original"
    root.mkdir()
    data = archive(root)
    tasks = ScreeningTasks(data.database)
    receipts = [
        tasks.register(request_for(data)),
        tasks.register(request_for(data, stage="value", original_title_is_zh=False)),
    ]
    expected = {
        r.receipt_id: hashlib.sha256(
            tasks.load_input(r.receipt_id).stage_input.payload_bytes
        ).hexdigest()
        for r in receipts
    }
    with closing(sqlite3.connect(data.database)) as reader:
        reader.execute("BEGIN")
        reader.execute("SELECT count(*) FROM screening_requests")
        extra = tasks.register(request_for(data, scheduled_day="2026-01-02"))
        expected[extra.receipt_id] = extra.fingerprint
        assert data.database.with_name(data.database.name + "-wal").stat().st_size > 0
        batch = create_backup(data.database, data.data_root, tmp_path / "backups")
    unavailable = tmp_path / "unavailable"
    root.rename(unavailable)
    copied = restore_backup(batch.batch_dir, tmp_path / "restored")
    moved = tmp_path / "moved"
    copied.target_dir.rename(moved)
    code = """
import hashlib, json, sys
from pathlib import Path
from paper_radar.screening_tasks import ScreeningTasks
blocked = tuple(Path(p).resolve() for p in sys.argv[3:])
def audit(event, args):
    if event == "open" and isinstance(args[0], (str, bytes)):
        path = Path(args[0]).resolve()
        if any(path == base or base in path.parents for base in blocked):
            raise RuntimeError("original_directory_forbidden")
sys.addaudithook(audit)
tasks = ScreeningTasks(Path(sys.argv[1]) / "database.sqlite3", Path(sys.argv[1]))
tasks.validate_all()
result = {}
for receipt in tasks.receipts(sys.argv[2]):
    payload = tasks.load_input(receipt.receipt_id).stage_input.payload_bytes
    result[receipt.receipt_id] = hashlib.sha256(payload).hexdigest()
print(json.dumps(result, sort_keys=True))
"""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
            str(moved),
            data.paper_id,
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
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == expected


@pytest.mark.parametrize(
    "damage",
    [
        "payload",
        "language",
        "request_hash",
        "request_day",
        "generation",
        "selection",
        "paper_owner",
        "stage",
    ],
)
def test_rehashed_semantic_registration_damage_is_rejected_without_repair(
    tmp_path: Path, damage: str
) -> None:
    import hashlib
    import json
    import sqlite3
    from contextlib import closing

    from paper_radar.backup.manifest import BackupError
    from paper_radar.backup.restore_contract import RestoreError
    from tests.a7_registration_support import archive, request_for
    from tests.backup_support import tree

    root = tmp_path / "source"
    root.mkdir()
    data = archive(root)
    other = PaperFacts(data.database, data.data_root).submit(
        observation(doi="10.1234/other", fields=screening_fields())
    )
    assert other.paper_id and other.version_id
    tasks = ScreeningTasks(data.database)
    tasks.register(request_for(data, stage="value", original_title_is_zh=False))
    batch = create_backup(data.database, data.data_root, tmp_path / "backups")
    database = batch.batch_dir / "database.sqlite3"
    with closing(sqlite3.connect(database)) as connection:
        if damage == "payload":
            connection.execute("UPDATE screening_inputs SET payload=?", (b"{}",))
        elif damage == "language":
            connection.execute("UPDATE screening_budgets SET original_title_is_zh=1")
        elif damage == "request_hash":
            connection.execute(
                "UPDATE screening_requests SET request_sha256=?", ("0" * 64,)
            )
        elif damage == "request_day":
            connection.execute(
                "UPDATE screening_requests SET scheduled_day='2026-01-02'"
            )
        elif damage == "generation":
            connection.execute("UPDATE screening_tasks SET generation=1")
        elif damage == "selection":
            selection = connection.execute(
                "SELECT selection_id FROM paper_selection_events WHERE paper_id=?",
                (other.paper_id,),
            ).fetchone()[0]
            connection.execute(
                "UPDATE screening_requests SET selection_id=?", (selection,)
            )
        elif damage == "paper_owner":
            connection.execute(
                "UPDATE screening_budgets SET paper_id=?,version_id=?",
                (other.paper_id, other.version_id),
            )
        else:
            connection.execute("UPDATE screening_inputs SET stage='boundary'")
        connection.commit()
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    manifest_path = batch.batch_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    raw = database.read_bytes()
    manifest["database"].update(
        sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw)
    )
    manifest_path.write_bytes(
        (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode()
    )
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
