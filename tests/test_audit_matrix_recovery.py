"""摘要解释进入固定备份副本的语义闭包与安全恢复。"""

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
from tests.audit_matrix_support import MAIN, MatrixSources
from tests.audit_sampling_support import CODE, sampling_service


def test_matrix_restores_original_text_without_original_directory_or_contact(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    root.mkdir()
    service = sampling_service(root, MatrixSources())
    view = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    assert service.data_root
    batch = create_backup(service.database, service.data_root, tmp_path / "backups")
    root.rename(tmp_path / "source-unavailable")
    restored = restore_backup(batch.batch_dir, tmp_path / "restored")
    recovered = FixtureAudit(
        restored.target_dir / "database.sqlite3", restored.target_dir
    )
    assert recovered.show_audit(view.plan.plan_id) == view
    identity = view.members[0].final_abstract_candidate_id
    assert identity and recovered.read_audit_text(view.plan.plan_id, identity) == MAIN
    recovered.validate_all()
    assert not list(restored.target_dir.rglob("*.lock"))
    for path in [*batch.batch_dir.rglob("*"), *restored.target_dir.rglob("*")]:
        if path.is_file():
            assert b"audit@example.org" not in path.read_bytes()


def test_rehashed_summary_candidate_tampering_is_rejected_by_backup(
    tmp_path: Path,
) -> None:
    service = sampling_service(tmp_path, MatrixSources())
    service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    assert service.data_root
    batch = create_backup(service.database, service.data_root, tmp_path / "backups")
    database = batch.batch_dir / "database.sqlite3"
    with closing(sqlite3.connect(database)) as connection:
        identity, raw = connection.execute(
            "SELECT row_id,content_json FROM audit_abstract_rows "
            "WHERE route='publisher' AND channel='http' LIMIT 1"
        ).fetchone()
        content = json.loads(raw)
        candidate = next(
            value for value in content["candidates"] if value["field"] == "abstract"
        )
        candidate["codepoints"] = 9999
        content["row_id"] = ""
        encoded = json.dumps(content, ensure_ascii=False, separators=(",", ":"))
        content["row_id"] = hashlib.sha256(encoded.encode()).hexdigest()
        connection.execute(
            "UPDATE audit_abstract_rows SET row_id=?,content_json=? WHERE row_id=?",
            (
                content["row_id"],
                json.dumps(content, ensure_ascii=False, separators=(",", ":")),
                identity,
            ),
        )
        connection.commit()
    path = batch.batch_dir / "manifest.json"
    manifest = json.loads(path.read_bytes())
    raw = database.read_bytes()
    manifest["database"].update(
        sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw)
    )
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    )
    with pytest.raises(BackupError) as caught:
        verify_backup(batch.batch_dir)
    assert caught.value.reason == "registration_invalid"


def test_matrix_cannot_replace_frozen_feed_with_later_rehashed_acquisition(
    tmp_path: Path,
) -> None:
    from paper_radar.fixture_audit import FixtureError
    from paper_radar.fixture_audit.acquisition_models import SourceRequest

    sources = MatrixSources()
    service = sampling_service(tmp_path, sources)
    view = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    later = service.acquire_source(
        view.plan.plan_id,
        request_key="unrelated-feed",
        request=SourceRequest(journal="jgr", route="feed"),
        contact_email="audit@example.org",
    )
    assert later.settlement
    with closing(sqlite3.connect(service.database)) as connection:
        identity, raw = connection.execute(
            "SELECT row_id,content_json FROM audit_abstract_rows "
            "WHERE route='feed' AND content_json LIKE '%\"journal\":\"jgr\"%'"
        ).fetchone()
        value = json.loads(raw)
        value["acquisition_id"] = later.execution_id
        value["observed_at"] = later.settlement.settled_at
        value["payload_sha256"] = later.settlement.payload_sha256
        for candidate in value["candidates"]:
            candidate["candidate_id"] = hashlib.sha256(
                (
                    later.execution_id
                    + "\0item[1]\0"
                    + candidate["field"]
                    + "\0"
                    + candidate["locator"]
                    + "\0"
                    + candidate["text_sha256"]
                ).encode()
            ).hexdigest()
        value["row_id"] = ""
        value["row_id"] = hashlib.sha256(
            json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest()
        connection.execute(
            "UPDATE audit_abstract_rows SET row_id=?,content_json=?,acquisition_id=? "
            "WHERE row_id=?",
            (
                value["row_id"],
                json.dumps(value, ensure_ascii=False, separators=(",", ":")),
                later.execution_id,
                identity,
            ),
        )
        connection.commit()
    with pytest.raises(FixtureError) as caught:
        service.validate_all()
    assert caught.value.reason == "corrupt_reference"
    assert caught.value.path == "abstract.acquisition"


@pytest.mark.parametrize("target", ["live", "backup"])
@pytest.mark.parametrize("pretence", ["candidates", "empty"])
def test_rehashed_not_attempted_row_cannot_hide_a_completed_source(
    tmp_path: Path, target: str, pretence: str
) -> None:
    from paper_radar.fixture_audit import FixtureError

    service = sampling_service(tmp_path, MatrixSources())
    view = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    assert service.data_root is not None
    batch = create_backup(service.database, service.data_root, tmp_path / "backups")
    database = (
        service.database if target == "live" else batch.batch_dir / "database.sqlite3"
    )
    with closing(sqlite3.connect(database)) as connection:
        old_id, raw = connection.execute(
            "SELECT row_id,content_json FROM audit_abstract_rows "
            "WHERE route='publisher' AND channel='http' "
            'AND content_json LIKE \'%"journal":"jgr"%\''
        ).fetchone()
        content = json.loads(raw)
        content["reason"] = "not_attempted"
        if pretence == "candidates":
            next(
                candidate
                for candidate in content["candidates"]
                if candidate["field"] == "abstract"
            )["codepoints"] = 9999
        else:
            content["valid_record"] = False
            content["candidates"] = []
            content["excluded_blocks"] = []
        content["row_id"] = ""
        content["row_id"] = hashlib.sha256(
            json.dumps(content, ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest()
        connection.execute(
            "UPDATE audit_abstract_rows SET row_id=?,content_json=? WHERE row_id=?",
            (
                content["row_id"],
                json.dumps(content, ensure_ascii=False, separators=(",", ":")),
                old_id,
            ),
        )
        connection.commit()
    if target == "live":
        for operation in (
            lambda: service.show_audit(view.plan.plan_id),
            service.validate_all,
        ):
            with pytest.raises(FixtureError) as rejected:
                operation()
            assert rejected.value.reason == "corrupt_reference"
        with pytest.raises(BackupError) as rejected_backup:
            create_backup(
                service.database, service.data_root, tmp_path / "invalid-backups"
            )
        assert rejected_backup.value.reason == "registration_invalid"
    else:
        path = batch.batch_dir / "manifest.json"
        manifest = json.loads(path.read_bytes())
        raw = database.read_bytes()
        manifest["database"].update(
            sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw)
        )
        path.write_text(
            json.dumps(
                manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            + "\n"
        )
        with pytest.raises(BackupError) as rejected_backup:
            verify_backup(batch.batch_dir)
        assert rejected_backup.value.reason == "registration_invalid"


def test_acquired_material_without_persisted_interpretation_can_be_backed_up(
    tmp_path: Path,
) -> None:
    from paper_radar.fixture_audit import FixtureError

    root = tmp_path / "source"
    root.mkdir()
    service = sampling_service(root, MatrixSources())
    plan = service.create_audit_plan(
        contact_email="audit@example.org",
        code_identity=CODE,
        plan_key="pending-material",
    )
    with closing(sqlite3.connect(service.database)) as connection:
        connection.execute(
            "CREATE TRIGGER fail_matrix BEFORE INSERT ON audit_abstract_rows "
            "WHEN NEW.route='publisher' AND NEW.channel='http' "
            'AND NEW.content_json LIKE \'%"journal":"jgr"%\' '
            "BEGIN SELECT RAISE(ABORT, 'synthetic interpretation failure'); END"
        )
        connection.commit()
    with pytest.raises(FixtureError) as failed:
        service.run_audit(
            contact_email="audit@example.org",
            code_identity=CODE,
            plan_key="pending-material",
        )
    assert failed.value.reason == "corrupt_reference"
    with closing(sqlite3.connect(service.database)) as connection:
        connection.execute("DROP TRIGGER fail_matrix")
        connection.commit()
    before = service.show_audit(plan.plan_id)
    pending = next(
        row
        for row in before.matrix
        if row.request.journal == "jgr"
        and row.request.route == "publisher"
        and row.request.channel == "http"
    )
    assert pending.reason == "not_attempted"
    assert pending.acquisition_id is not None
    assert not pending.valid_record and not pending.candidates
    acquired = next(
        execution
        for execution in before.executions
        if execution.execution_id == pending.acquisition_id
    )
    assert acquired.reason == "acquired"
    assert (
        acquired.settlement is not None and acquired.settlement.artifact_id is not None
    )
    assert before.status == "partial"
    service.validate_all()
    assert service.data_root is not None
    batch = create_backup(service.database, service.data_root, tmp_path / "backups")
    root.rename(tmp_path / "source-unavailable")
    restored = restore_backup(batch.batch_dir, tmp_path / "restored")
    recovered = FixtureAudit(
        restored.target_dir / "database.sqlite3", restored.target_dir
    )
    assert recovered.show_audit(plan.plan_id) == before
    recovered.validate_all()


def test_stored_zero_request_not_attempted_settlement_remains_valid(
    tmp_path: Path,
) -> None:
    import httpx

    from paper_radar.fixture_audit.acquisition_models import HTTPFacts, SourceRequest
    from paper_radar.fixture_audit.source_http import SourceHTTPExecutor, SourceResponse
    from paper_radar.storage.database import upgrade_database
    from tests.audit_sampling_support import SamplingClock

    clock = SamplingClock()
    delegate = SourceHTTPExecutor(
        transport=httpx.MockTransport(MatrixSources()),
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )

    class AvailableExecutor:
        def fetch(
            self, request: SourceRequest, *, contact_email: str
        ) -> SourceResponse:
            if request.journal == "jgr" and request.route == "publisher":
                return SourceResponse(HTTPFacts(reason="not_attempted"))
            return delegate.fetch(request, contact_email=contact_email)

    database = tmp_path / "facts.sqlite3"
    upgrade_database(database)
    service = FixtureAudit(
        database, tmp_path / "data", source_executors={"http": AvailableExecutor()}
    )
    view = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    row = next(
        row
        for row in view.matrix
        if row.request.journal == "jgr"
        and row.request.route == "publisher"
        and row.request.channel == "http"
    )
    assert row.reason == "not_attempted"
    assert row.acquisition_id is not None and row.observed_at is not None
    assert not row.valid_record and not row.candidates and row.payload_sha256 is None
    execution = next(
        value for value in view.executions if value.execution_id == row.acquisition_id
    )
    assert execution.reason == "not_attempted" and execution.physical_requests == 0
    service.validate_all()
    assert service.data_root is not None
    batch = create_backup(database, service.data_root, tmp_path / "backups")
    restored = restore_backup(batch.batch_dir, tmp_path / "restored")
    recovered = FixtureAudit(
        restored.target_dir / "database.sqlite3", restored.target_dir
    )
    assert recovered.show_audit(view.plan.plan_id) == view
    recovered.validate_all()
