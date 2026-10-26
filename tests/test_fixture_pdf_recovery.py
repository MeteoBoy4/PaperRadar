"""PDF 非空恢复闭包及重算外层身份后的语义拒绝。"""

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
from paper_radar.storage.artifacts import ArtifactStore
from tests.fixture_pdf_support import PDF_BYTES, PDF_SHA256, registered_jgr


def test_pdf_history_restores_without_the_source_pdf_or_declaration_files(
    tmp_path: Path,
) -> None:
    from paper_radar.fixture_audit.pdf_models import PdfBackendRegistration

    service, record_id = registered_jgr(tmp_path)
    source = tmp_path / "synthetic.pdf"
    source.write_bytes(PDF_BYTES)
    pdf = service.register_pdf(
        record_id,
        source,
        request_key="source",
        source_url="https://repository.example.org/pdf",
        access_basis="manual",
        license_basis="synthetic fixture",
        observed_date="2026-10-26",
    )
    service.register_pdf_backend(
        PdfBackendRegistration.model_validate(
            {
                "request_key": "backend",
                "pdf_id": pdf.pdf_id,
                "pdf_sha256": PDF_SHA256,
                "backend_component": "docling",
                "backend_version": "synthetic-v1",
                "extraction_fingerprint": "a" * 64,
                "reading_sha256": "b" * 64,
                "methods_data": {
                    "state": "located",
                    "locator": "section 2",
                    "inspection_basis": "synthetic inspection",
                },
                "availability_open_research": {
                    "state": "confirmed_absent",
                    "inspection_basis": "synthetic absence inspection",
                },
            }
        )
    )
    source.unlink()
    assert service.data_root is not None
    before = service.show(record_id)
    batch = create_backup(service.database, service.data_root, tmp_path / "backups")
    restored = restore_backup(batch.batch_dir, tmp_path / "restored")
    recovered = FixtureAudit(
        restored.target_dir / "database.sqlite3", restored.target_dir
    )
    assert recovered.show(record_id) == before
    assert recovered.check_pdf(record_id).status == "byte_verified"
    assert ArtifactStore(recovered.database, restored.target_dir).read_artifact(
        pdf.artifact_id
    ) == {"payload": PDF_BYTES}
    recovered.validate_all()


@pytest.mark.parametrize("damage", ["expected_hash", "byte_proof"])
def test_rehashed_pdf_fact_cannot_lie_about_byte_verification(
    tmp_path: Path, damage: str
) -> None:
    service, record_id = registered_jgr(tmp_path)
    source = tmp_path / "synthetic.pdf"
    source.write_bytes(PDF_BYTES)
    service.register_pdf(
        record_id,
        source,
        request_key="pdf",
        source_url="https://repository.example.org/pdf",
        access_basis="manual",
        license_basis="synthetic fixture",
        observed_date="2026-10-26",
    )
    assert service.data_root is not None
    batch = create_backup(service.database, service.data_root, tmp_path / "backups")
    copied = batch.batch_dir / "database.sqlite3"
    with closing(sqlite3.connect(copied)) as connection:
        content = json.loads(
            connection.execute(
                "SELECT content_json FROM fixture_pdf_acquisitions"
            ).fetchone()[0]
        )
        if damage == "expected_hash":
            content["registration"]["expected_sha256"] = "0" * 64
            identity_content = {
                key: value
                for key, value in content.items()
                if key not in {"pdf_id", "byte_verified"}
            }
            content["pdf_id"] = hashlib.sha256(
                json.dumps(
                    identity_content,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest()
        else:
            content["byte_verified"] = 1
        connection.execute(
            "UPDATE fixture_pdf_acquisitions SET pdf_id=?,content_json=?",
            (content["pdf_id"], json.dumps(content, separators=(",", ":"))),
        )
        connection.commit()
    manifest_path = batch.batch_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    raw = copied.read_bytes()
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


def test_pdf_publication_followed_by_registration_failure_leaves_no_acquisition(
    tmp_path: Path,
) -> None:
    from paper_radar.fixture_audit import FixtureError

    service, record_id = registered_jgr(tmp_path)
    source = tmp_path / "synthetic.pdf"
    source.write_bytes(PDF_BYTES)
    with closing(sqlite3.connect(service.database)) as connection:
        connection.execute(
            "CREATE TRIGGER fail_pdf BEFORE INSERT ON fixture_pdf_acquisitions "
            "BEGIN SELECT RAISE(ABORT, 'private failure body'); END"
        )
        connection.commit()
    with pytest.raises(FixtureError) as rejected:
        service.register_pdf(
            record_id,
            source,
            request_key="pdf",
            source_url="https://repository.example.org/pdf",
            access_basis="manual",
            license_basis="synthetic fixture",
            observed_date="2026-10-26",
        )
    assert rejected.value.reason == "corrupt_reference"
    assert "private failure body" not in str(rejected.value)
    assert service.check_pdf(record_id).status == "not_registered"
    assert service.data_root is not None
    artifacts = ArtifactStore(service.database, service.data_root).list_artifacts()
    assert len(artifacts) == 1
    assert ArtifactStore(service.database, service.data_root).read_artifact(
        artifacts[0].artifact_id
    ) == {"payload": PDF_BYTES}
    service.validate_all()
