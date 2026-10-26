"""固定选样的基本恢复及重新哈希后的成员篡改拒绝。"""

import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from paper_radar.backup import create_backup, verify_backup
from paper_radar.backup.manifest import BackupError
from paper_radar.backup.restore import restore_backup
from paper_radar.fixture_audit import FixtureAudit
from tests.audit_sampling_support import CODE, SamplingSources, sampling_service


def registered(root: Path) -> tuple[FixtureAudit, str]:
    root.mkdir()
    service = sampling_service(root, SamplingSources())
    plan = service.create_audit_plan(
        contact_email="audit@example.org", code_identity=CODE
    )
    service.select_audit_samples(
        plan.plan_id, contact_email="audit@example.org", code_identity=CODE
    )
    return service, plan.plan_id


def test_sampling_restores_without_feed_paths_and_does_not_acquire_execution_locks(
    tmp_path: Path,
) -> None:
    service, plan_id = registered(tmp_path / "source")
    before = service.show_audit(plan_id)
    assert service.data_root is not None
    batch = create_backup(service.database, service.data_root, tmp_path / "backups")
    service.database.parent.rename(tmp_path / "source-unavailable")
    restored = restore_backup(batch.batch_dir, tmp_path / "restored")
    recovered = FixtureAudit(
        restored.target_dir / "database.sqlite3", restored.target_dir
    )
    assert recovered.show_audit(plan_id) == before
    recovered.validate_all()
    assert not list(restored.target_dir.rglob("*.lock"))


def test_rehashed_member_identity_cannot_replace_explicit_source_doi(
    tmp_path: Path,
) -> None:
    service, _ = registered(tmp_path / "source")
    assert service.data_root is not None
    batch = create_backup(service.database, service.data_root, tmp_path / "backups")
    database = batch.batch_dir / "database.sqlite3"
    with closing(sqlite3.connect(database)) as connection:
        old_id, content = connection.execute(
            "SELECT event_id,content_json FROM audit_sampling_events "
            "WHERE journal='jgr'"
        ).fetchone()
        value = json.loads(content)
        value["doi"] = "10.1029/forged-member"
        member_input = [
            value["plan_id"],
            "jgr",
            1,
            "10.1029/forged-member",
            value["entry_id"],
        ]
        value["member_id"] = hashlib.sha256(
            json.dumps(member_input, ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest()
        value["event_id"] = ""
        value["event_id"] = hashlib.sha256(
            json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest()
        connection.execute(
            "UPDATE audit_sampling_events SET event_id=?,content_json=? "
            "WHERE event_id=?",
            (
                value["event_id"],
                json.dumps(value, ensure_ascii=False, separators=(",", ":")),
                old_id,
            ),
        )
        connection.commit()
    path = batch.batch_dir / "manifest.json"
    manifest = json.loads(path.read_bytes())
    raw = database.read_bytes()
    manifest["database"].update(
        sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw)
    )
    path.write_bytes(
        (
            json.dumps(
                manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            + "\n"
        ).encode()
    )
    with pytest.raises(BackupError) as caught:
        verify_backup(batch.batch_dir)
    assert caught.value.reason == "registration_invalid"
