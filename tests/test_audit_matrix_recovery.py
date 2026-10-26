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
