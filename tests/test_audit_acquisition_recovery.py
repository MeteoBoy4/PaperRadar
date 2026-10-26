"""来源取得事实的固定备份闭包、隐私与语义篡改拒绝。"""

import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import httpx
import pytest

from paper_radar.backup import create_backup, verify_backup
from paper_radar.backup.manifest import BackupError
from paper_radar.backup.restore import restore_backup
from paper_radar.fixture_audit import FixtureAudit
from paper_radar.fixture_audit.acquisition_models import CodeIdentity, SourceRequest
from paper_radar.fixture_audit.source_http import SourceHTTPExecutor
from paper_radar.storage.database import upgrade_database


def populated(root: Path) -> tuple[FixtureAudit, str]:
    root.mkdir()
    database = root / "facts.sqlite3"
    upgrade_database(database)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "journals.ametsoc.org":
            return httpx.Response(
                200,
                headers={"Set-Cookie": "secret-cookie-value"},
                stream=httpx.ByteStream(
                    b"<rss><channel><title>safe</title></channel></rss>"
                ),
            )
        return httpx.Response(404, content=b"secret-failure-page audit@example.org")

    service = FixtureAudit(
        database,
        root / "data",
        source_executors={
            "http": SourceHTTPExecutor(transport=httpx.MockTransport(handler))
        },
    )
    plan = service.create_audit_plan(
        contact_email="audit@example.org", code_identity=CodeIdentity(basis="synthetic")
    )
    service.acquire_source(
        plan.plan_id,
        request_key="feed",
        request=SourceRequest(journal="aies", route="feed"),
        contact_email="audit@example.org",
    )
    service.acquire_source(
        plan.plan_id,
        request_key="failed",
        request=SourceRequest(journal="jgr", route="feed"),
        contact_email="audit@example.org",
    )
    service.acquire_source(
        plan.plan_id,
        request_key="render",
        request=SourceRequest(journal="jgr", route="feed", channel="browser_render"),
        contact_email="audit@example.org",
    )
    return service, plan.plan_id


def test_nonempty_backup_restores_audit_without_source_or_contact(
    tmp_path: Path,
) -> None:
    service, plan_id = populated(tmp_path / "source")
    before = service.show_audit(plan_id)
    assert service.data_root is not None
    batch = create_backup(service.database, service.data_root, tmp_path / "backups")
    verify_backup(batch.batch_dir)
    for path in batch.batch_dir.rglob("*"):
        if path.is_file():
            raw = path.read_bytes()
            assert b"audit@example.org" not in raw
            assert b"secret-cookie-value" not in raw
            assert b"secret-failure-page" not in raw
    service.database.parent.rename(tmp_path / "source-unavailable")
    restored = restore_backup(batch.batch_dir, tmp_path / "restored")
    recovered = FixtureAudit(
        restored.target_dir / "database.sqlite3", restored.target_dir
    )
    assert recovered.show_audit(plan_id) == before
    recovered.validate_all()
    assert not list(restored.target_dir.rglob("*.lock"))
    assert [execution.reason for execution in before.executions] == [
        "acquired",
        "not_found",
        "channel_not_installed",
    ]


@pytest.mark.parametrize("damage", ["counter", "channel", "source_identity"])
def test_rehashed_backup_rejects_impossible_audit_facts(
    tmp_path: Path, damage: str
) -> None:
    service, _ = populated(tmp_path / "source")
    assert service.data_root is not None
    batch = create_backup(service.database, service.data_root, tmp_path / "backups")
    database = batch.batch_dir / "database.sqlite3"
    with closing(sqlite3.connect(database)) as connection:
        execution_id, request_json = connection.execute(
            "SELECT execution_id,request_json FROM audit_route_starts "
            "WHERE request_key='feed'"
        ).fetchone()
        if damage == "counter":
            value = json.loads(
                connection.execute(
                    "SELECT settlement_json FROM audit_route_settlements "
                    "WHERE execution_id=?",
                    (execution_id,),
                ).fetchone()[0]
            )
            value["http"]["retry_count"] = 1
            connection.execute(
                "UPDATE audit_route_settlements SET settlement_json=? "
                "WHERE execution_id=?",
                (
                    json.dumps(value, ensure_ascii=False, separators=(",", ":")),
                    execution_id,
                ),
            )
        else:
            value = json.loads(request_json)
            value["channel" if damage == "channel" else "journal"] = (
                "browser_render" if damage == "channel" else "jgr"
            )
            connection.execute(
                "UPDATE audit_route_starts SET request_json=? WHERE execution_id=?",
                (
                    json.dumps(value, ensure_ascii=False, separators=(",", ":")),
                    execution_id,
                ),
            )
        connection.commit()
    manifest_path = batch.batch_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    raw = database.read_bytes()
    manifest["database"].update(
        sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw)
    )
    manifest_path.write_bytes(
        (
            json.dumps(
                manifest, sort_keys=True, ensure_ascii=False, separators=(",", ":")
            )
            + "\n"
        ).encode()
    )
    with pytest.raises(BackupError) as caught:
        verify_backup(batch.batch_dir)
    assert caught.value.reason == "registration_invalid"
