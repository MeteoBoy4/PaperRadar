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


@pytest.mark.parametrize(
    "damage", ["counter", "channel", "source_identity", "decoding"]
)
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
        if damage in {"counter", "decoding"}:
            value = json.loads(
                connection.execute(
                    "SELECT settlement_json FROM audit_route_settlements "
                    "WHERE execution_id=?",
                    (execution_id,),
                ).fetchone()[0]
            )
            if damage == "counter":
                value["http"]["retry_count"] = 1
            else:
                value["content_decoding"] = "ascii"
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


@pytest.mark.parametrize(
    "field,value",
    [
        ("settled_at", "not-a-timestamp"),
        ("settled_at", "2026-10-26T00:00:00"),
        ("started_at", "not-a-timestamp"),
    ],
)
def test_rehashed_backup_rejects_invalid_execution_times(
    tmp_path: Path, field: str, value: str
) -> None:
    service, _ = populated(tmp_path / "source")
    assert service.data_root is not None
    batch = create_backup(service.database, service.data_root, tmp_path / "backups")
    database = batch.batch_dir / "database.sqlite3"
    with closing(sqlite3.connect(database)) as connection:
        if field == "started_at":
            connection.execute(
                "UPDATE audit_route_starts SET started_at=? WHERE request_key='feed'",
                (value,),
            )
        else:
            execution_id = connection.execute(
                "SELECT execution_id FROM audit_route_starts WHERE request_key='feed'"
            ).fetchone()[0]
            settlement = json.loads(
                connection.execute(
                    "SELECT settlement_json FROM audit_route_settlements "
                    "WHERE execution_id=?",
                    (execution_id,),
                ).fetchone()[0]
            )
            settlement[field] = value
            connection.execute(
                "UPDATE audit_route_settlements SET settlement_json=? "
                "WHERE execution_id=?",
                (
                    json.dumps(settlement, ensure_ascii=False, separators=(",", ":")),
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
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    )
    with pytest.raises(BackupError) as rejected:
        verify_backup(batch.batch_dir)
    assert rejected.value.reason == "registration_invalid"


@pytest.mark.parametrize("encoding", ["utf-16", "utf-32"])
@pytest.mark.parametrize("echo_contact", [True, False])
def test_decoded_contact_is_never_persisted_and_safe_encoded_bytes_stay_original(
    tmp_path: Path, encoding: str, echo_contact: bool
) -> None:
    from paper_radar.storage.artifacts import ArtifactStore

    contact = "audit@example.org"
    text = (
        '<html><meta name="citation_doi" content="10.1029/example">'
        "<body>原始出版者页面 "
        + ("AuDiT@ExAmPlE.OrG" if echo_contact else "no contact echoed")
        + "</body></html>"
    )
    raw = text.encode(encoding)
    database = tmp_path / "facts.sqlite3"
    upgrade_database(database)
    service = FixtureAudit(
        database,
        tmp_path / "data",
        source_executors={
            "http": SourceHTTPExecutor(
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(
                        200,
                        headers={"Content-Type": f"text/html; charset={encoding}"},
                        stream=httpx.ByteStream(raw),
                    )
                )
            )
        },
    )
    plan = service.create_audit_plan(
        contact_email=contact, code_identity=CodeIdentity(basis="synthetic")
    )
    result = service.acquire_source(
        plan.plan_id,
        request_key="publisher",
        request=SourceRequest(journal="jgr", route="publisher", doi="10.1029/example"),
        contact_email=contact,
    )
    assert result.reason == ("invalid_response" if echo_contact else "acquired")
    assert result.settlement is not None
    assert service.data_root is not None
    store = ArtifactStore(database, service.data_root)
    if echo_contact:
        assert result.settlement.artifact_id is None
        assert store.list_artifacts() == ()
    else:
        assert result.settlement.artifact_id is not None
        assert result.settlement.content_decoding == encoding
        assert store.read_artifact(result.settlement.artifact_id) == {"payload": raw}
    for path in tmp_path.rglob("*"):
        if path.is_file():
            persisted = path.read_bytes()
            for spelling in (contact, "AuDiT@ExAmPlE.OrG"):
                for codec in (
                    "utf-8",
                    "utf-16-le",
                    "utf-16-be",
                    "utf-32-le",
                    "utf-32-be",
                ):
                    assert spelling.encode(codec) not in persisted
    assert contact not in repr(result)
    service.validate_all()


def test_injected_executor_cannot_persist_contact_hidden_by_text_encoding(
    tmp_path: Path,
) -> None:
    from paper_radar.fixture_audit import FixtureError
    from paper_radar.fixture_audit.acquisition_models import HTTPFacts, HTTPRequestFact
    from paper_radar.fixture_audit.source_http import SourceResponse
    from paper_radar.storage.artifacts import ArtifactStore

    class EncodedExecutor:
        def fetch(
            self, request: SourceRequest, *, contact_email: str
        ) -> SourceResponse:
            return SourceResponse(
                HTTPFacts(
                    reason="acquired",
                    status_code=200,
                    round_count=1,
                    requests=(
                        HTTPRequestFact(
                            url="https://agupubs.onlinelibrary.wiley.com/doi/10.1029/example",
                            round_no=1,
                            redirect_no=0,
                            status_code=200,
                            reason="acquired",
                        ),
                    ),
                    content_type="text/html",
                    charset="utf-16",
                    decoding="utf-16",
                ),
                (
                    '<html><meta name="citation_doi" content="10.1029/example">'
                    "audit@example.org</html>"
                ).encode("utf-16"),
            )

    database = tmp_path / "facts.sqlite3"
    upgrade_database(database)
    service = FixtureAudit(
        database, tmp_path / "data", source_executors={"http": EncodedExecutor()}
    )
    plan = service.create_audit_plan(
        contact_email="audit@example.org", code_identity=CodeIdentity(basis="synthetic")
    )
    with pytest.raises(FixtureError) as rejected:
        service.acquire_source(
            plan.plan_id,
            request_key="publisher",
            request=SourceRequest(
                journal="jgr", route="publisher", doi="10.1029/example"
            ),
            contact_email="audit@example.org",
        )
    assert rejected.value.reason == "invalid_request"
    assert rejected.value.path == "executor"
    assert "audit@example.org" not in str(rejected.value)
    assert service.data_root is not None
    assert ArtifactStore(database, service.data_root).list_artifacts() == ()
    for path in tmp_path.glob("facts.sqlite3*"):
        persisted = path.read_bytes()
        assert b"audit@example.org" not in persisted
        assert "audit@example.org".encode("utf-16-le") not in persisted
    assert service.show_audit(plan.plan_id).executions[0].settlement is None
    service.validate_all()
