"""PDF 字节事实与 backend 期望通过公共 fixture 边界独立登记。"""

import json
from pathlib import Path

import pytest

from paper_radar.fixture_audit import FixtureAudit, FixtureError
from paper_radar.storage.artifacts import ArtifactStore
from tests.fixture_pdf_support import PDF_BYTES, PDF_SHA256, registered_jgr


def test_given_pdf_bytes_are_registered_separately_from_the_historical_declaration(
    tmp_path: Path,
) -> None:
    service, record_id = registered_jgr(tmp_path)
    source = tmp_path / "sample.pdf"
    source.write_bytes(PDF_BYTES)
    original = service.show(record_id)
    result = service.register_pdf(
        record_id,
        source,
        request_key="local-pdf-1",
        source_url="https://repository.example.org/handle/11094/103589",
        access_basis="open",
        license_basis="synthetic vector: redistribution permitted",
        observed_date="2026-10-26",
    )
    assert result.pdf_sha256 == PDF_SHA256
    assert result.size_bytes == 38
    assert result.byte_verified
    source.unlink()
    shown = service.show(record_id)
    assert shown.entry == original.entry
    assert shown.entry.handle == "11094/103589"
    assert shown.pdf is not None
    assert shown.pdf.current_pdf_id == result.pdf_id
    assert shown.pdf.acquisitions[0].backend_expectations == ()
    assert ArtifactStore(service.database, tmp_path / "data").read_artifact(
        result.artifact_id
    ) == {"payload": PDF_BYTES}
    service.validate_all()


def test_backend_expectations_append_without_replacing_pdf_and_bind_its_bytes(
    tmp_path: Path,
) -> None:
    from paper_radar.fixture_audit.pdf_models import PdfBackendRegistration

    service, record_id = registered_jgr(tmp_path)
    source = tmp_path / "sample.pdf"
    source.write_bytes(PDF_BYTES)
    pdf = service.register_pdf(
        record_id,
        source,
        request_key="pdf",
        source_url="https://repository.example.org/pdf",
        access_basis="manual",
        license_basis="synthetic fixture",
        observed_date="2026-10-26",
    )
    first = service.register_pdf_backend(
        PdfBackendRegistration.model_validate(
            {
                "request_key": "backend-v1",
                "pdf_id": pdf.pdf_id,
                "pdf_sha256": PDF_SHA256,
                "backend_component": "docling",
                "backend_version": "synthetic-v1",
                "model_versions": (
                    {"name": "layout", "version": "synthetic-model-v1"},
                ),
                "extraction_fingerprint": "a" * 64,
                "reading_sha256": "b" * 64,
                "methods_data": {
                    "state": "located",
                    "locator": "Methods §2 / pages 2–3",
                    "inspection_basis": "Synthetic inspection vector",
                },
                "availability_open_research": {
                    "state": "confirmed_absent",
                    "inspection_basis": "Synthetic inspection confirms section absent",
                },
            }
        )
    )
    second = service.register_pdf_backend(
        PdfBackendRegistration.model_validate(
            {
                "request_key": "backend-v2",
                "pdf_id": pdf.pdf_id,
                "pdf_sha256": PDF_SHA256,
                "backend_component": "docling",
                "backend_version": "synthetic-v2",
                "model_versions": (),
                "extraction_fingerprint": "c" * 64,
                "reading_sha256": "d" * 64,
                "methods_data": {"state": "unverified"},
                "availability_open_research": {"state": "unverified"},
            }
        )
    )
    shown = service.show(record_id)
    assert shown.pdf is not None and shown.pdf.current_pdf_id == pdf.pdf_id
    expectations = shown.pdf.acquisitions[0].backend_expectations
    assert expectations == (first, second)
    assert first.proof_level == "shape_only"
    assert first.registration.availability_open_research.state == "confirmed_absent"
    assert second.registration.methods_data.state == "unverified"
    assert service.register_pdf_backend(first.registration) == first


def test_pdf_replacement_keeps_old_bytes_and_does_not_inherit_backend_expectations(
    tmp_path: Path,
) -> None:
    from paper_radar.fixture_audit.pdf_models import PdfBackendRegistration

    service, record_id = registered_jgr(tmp_path)
    source = tmp_path / "sample.pdf"
    source.write_bytes(PDF_BYTES)
    assert service.check_pdf(record_id).status == "not_registered"
    first = service.register_pdf(
        record_id,
        source,
        request_key="first",
        source_url="https://repository.example.org/pdf",
        access_basis="manual",
        license_basis="synthetic fixture",
        observed_date="2026-10-26",
    )
    service.register_pdf_backend(
        PdfBackendRegistration.model_validate(
            {
                "request_key": "expectation",
                "pdf_id": first.pdf_id,
                "pdf_sha256": PDF_SHA256,
                "backend_component": "docling",
                "backend_version": "synthetic-v1",
                "extraction_fingerprint": "a" * 64,
                "reading_sha256": "b" * 64,
                "methods_data": {
                    "state": "confirmed_absent",
                    "inspection_basis": "explicit synthetic inspection",
                },
                "availability_open_research": {"state": "unverified"},
            }
        )
    )
    source.write_bytes(b"%PDF-1.7\na different synthetic PDF\n%%EOF\n")
    second = service.register_pdf(
        record_id,
        source,
        request_key="second",
        source_url="https://repository.example.org/pdf-new",
        access_basis="open",
        license_basis="synthetic replacement fixture",
        observed_date="2026-10-26",
        replaces=first.pdf_id,
        replacement_reason="replace the synthetic PDF",
    )
    assert (
        service.register_pdf(
            record_id,
            source,
            request_key="second",
            source_url="https://repository.example.org/pdf-new",
            access_basis="open",
            license_basis="synthetic replacement fixture",
            observed_date="2026-10-26",
            replaces=first.pdf_id,
            replacement_reason="replace the synthetic PDF",
        )
        == second
    )
    shown = service.show(record_id)
    assert shown.pdf is not None
    assert shown.pdf.current_pdf_id == second.pdf_id
    assert [(item.pdf_id, item.current) for item in shown.pdf.acquisitions] == [
        (first.pdf_id, False),
        (second.pdf_id, True),
    ]
    assert len(shown.pdf.acquisitions[0].backend_expectations) == 1
    assert shown.pdf.acquisitions[1].backend_expectations == ()
    assert service.check_pdf(record_id).status == "byte_verified"
    assert service.check_pdf(record_id).backend_expectation_count == 1
    assert ArtifactStore(service.database, tmp_path / "data").read_artifact(
        first.artifact_id
    ) == {"payload": PDF_BYTES}


def test_wrong_pdf_hash_and_cross_sample_replacement_leave_prior_selection_intact(
    tmp_path: Path,
) -> None:
    from paper_radar.storage.artifact_contract import ArtifactError

    service, record_id = registered_jgr(tmp_path)
    source = tmp_path / "sample.pdf"
    source.write_bytes(PDF_BYTES)
    with pytest.raises(ArtifactError) as mismatch:
        service.register_pdf(
            record_id,
            source,
            request_key="wrong-hash",
            source_url="https://repository.example.org/pdf",
            access_basis="manual",
            license_basis="synthetic fixture",
            observed_date="2026-10-26",
            expected_sha256="0" * 64,
        )
    assert mismatch.value.reason == "hash_mismatch"
    assert service.check_pdf(record_id).status == "not_registered"
    first = service.register_pdf(
        record_id,
        source,
        request_key="original",
        source_url="https://repository.example.org/pdf",
        access_basis="manual",
        license_basis="synthetic fixture",
        observed_date="2026-10-26",
    )
    other = next(
        item
        for item in service.list()
        if item.entry.purpose == "pdf" and item.entry.journal == "aies"
    )
    for target, replaces, reason in [
        (other.record_id, first.pdf_id, "cross sample"),
        (record_id, "0" * 64, "dangling"),
    ]:
        with pytest.raises(FixtureError) as rejected:
            service.register_pdf(
                target,
                source,
                request_key="invalid",
                source_url="https://repository.example.org/pdf",
                access_basis="manual",
                license_basis="synthetic fixture",
                observed_date="2026-10-26",
                replaces=replaces,
                replacement_reason=reason,
            )
        assert rejected.value.reason == "invalid_reference"
        assert rejected.value.path == "pdf.replaces"
    with pytest.raises(FixtureError) as conflict:
        service.register_pdf(
            record_id,
            source,
            request_key="original",
            source_url="https://repository.example.org/pdf",
            access_basis="manual",
            license_basis="different evidence",
            observed_date="2026-10-26",
        )
    assert conflict.value.reason == "declaration_conflict"
    assert service.check_pdf(record_id).acquisition_count == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("unknown_secret_field", "never-print-this-secret"),
        ("observed_date", "2026-02-30"),
        ("source_url", "https://person:password@example.org/private"),
        ("source_url", "file:///private.pdf"),
        ("license_basis", " "),
        ("replaces", "not-a-hash"),
    ],
)
def test_invalid_pdf_request_files_are_rejected_safely(
    tmp_path: Path, field: str, value: object
) -> None:
    service, record_id = registered_jgr(tmp_path)
    request: dict[str, object] = {
        "sample_record_id": record_id,
        "request_key": "request",
        "source_url": "https://repository.example.org/pdf",
        "access_basis": "manual",
        "license_basis": "synthetic fixture",
        "observed_date": "2026-10-26",
    }
    request[field] = value
    request_file = tmp_path / "request.json"
    request_file.write_text(json.dumps(request))
    source = tmp_path / "sample.pdf"
    source.write_bytes(PDF_BYTES)
    with pytest.raises(FixtureError) as rejected:
        service.register_pdf_request(request_file, source)
    assert rejected.value.reason == "invalid_declaration"
    assert rejected.value.path == "pdf.request"
    assert "password" not in str(
        rejected.value
    ) and "never-print-this-secret" not in str(rejected.value)
    assert service.check_pdf(record_id).status == "not_registered"


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("backend_version", " ", "invalid_declaration"),
        ("extraction_fingerprint", "unknown", "invalid_declaration"),
        ("reading_sha256", "A" * 64, "invalid_declaration"),
        ("pdf_sha256", "0" * 64, "invalid_reference"),
        ("pdf_id", "0" * 64, "invalid_reference"),
        ("methods_data", {"state": "confirmed_absent"}, "invalid_declaration"),
        (
            "methods_data",
            {"state": "located", "inspection_basis": "inspected"},
            "invalid_declaration",
        ),
        (
            "methods_data",
            {"state": "unverified", "locator": "invented"},
            "invalid_declaration",
        ),
        ("secret", "never-print-this-secret", "invalid_declaration"),
    ],
)
def test_backend_fields_and_pdf_content_binding_are_checked(
    tmp_path: Path, field: str, value: object, reason: str
) -> None:
    service, record_id = registered_jgr(tmp_path)
    source = tmp_path / "sample.pdf"
    source.write_bytes(PDF_BYTES)
    pdf = service.register_pdf(
        record_id,
        source,
        request_key="pdf",
        source_url="https://repository.example.org/pdf",
        access_basis="manual",
        license_basis="synthetic fixture",
        observed_date="2026-10-26",
    )
    request: dict[str, object] = {
        "request_key": "backend",
        "pdf_id": pdf.pdf_id,
        "pdf_sha256": PDF_SHA256,
        "backend_component": "docling",
        "backend_version": "synthetic-v1",
        "extraction_fingerprint": "a" * 64,
        "reading_sha256": "b" * 64,
        "methods_data": {"state": "unverified"},
        "availability_open_research": {"state": "unverified"},
    }
    request[field] = value
    request_file = tmp_path / "backend.json"
    request_file.write_text(json.dumps(request))
    with pytest.raises(FixtureError) as rejected:
        service.register_pdf_backend(request_file)
    assert rejected.value.reason == reason
    assert rejected.value.path in {"pdf.request", "pdf_backend.pdf_sha256"}
    assert "never-print-this-secret" not in str(rejected.value)
    assert service.check_pdf(record_id).backend_expectation_count == 0


def test_preconstructed_backend_models_cannot_bypass_the_public_boundary(
    tmp_path: Path,
) -> None:
    from paper_radar.fixture_audit.pdf_models import PdfBackendRegistration

    service, record_id = registered_jgr(tmp_path)
    source = tmp_path / "sample.pdf"
    source.write_bytes(PDF_BYTES)
    pdf = service.register_pdf(
        record_id,
        source,
        request_key="pdf",
        source_url="https://repository.example.org/pdf",
        access_basis="manual",
        license_basis="synthetic fixture",
        observed_date="2026-10-26",
    )
    valid = PdfBackendRegistration.model_validate(
        {
            "request_key": "backend",
            "pdf_id": pdf.pdf_id,
            "pdf_sha256": PDF_SHA256,
            "backend_component": "docling",
            "backend_version": "synthetic-v1",
            "extraction_fingerprint": "a" * 64,
            "reading_sha256": "b" * 64,
            "methods_data": {"state": "unverified"},
            "availability_open_research": {"state": "unverified"},
        }
    )
    with pytest.raises(FixtureError) as rejected:
        service.register_pdf_backend(valid.model_copy(update={"reading_sha256": "bad"}))
    assert rejected.value.reason == "invalid_declaration"
    assert rejected.value.path == "pdf_backend"
    assert service.check_pdf(record_id).backend_expectation_count == 0


def test_declaration_check_and_local_pdf_integrity_are_independent(
    tmp_path: Path,
) -> None:
    from paper_radar.storage.artifact_contract import ArtifactError

    service, record_id = registered_jgr(tmp_path)
    source = tmp_path / "sample.pdf"
    source.write_bytes(PDF_BYTES)
    pdf = service.register_pdf(
        record_id,
        source,
        request_key="pdf",
        source_url="https://repository.example.org/pdf",
        access_basis="manual",
        license_basis="synthetic fixture",
        observed_date="2026-10-26",
    )
    assert service.data_root is not None
    blob = service.data_root / "blobs/sha256" / PDF_SHA256[:2] / PDF_SHA256
    blob.chmod(0o600)
    blob.write_bytes(b"damaged")
    seed = Path(__file__).parents[1] / "fixtures/a10/historical-v1.json"
    assert service.check(seed).status == "byte_verified"
    with pytest.raises(ArtifactError) as rejected:
        service.check_pdf(record_id)
    assert rejected.value.reason == "blob_corrupt"
    recorded = FixtureAudit(service.database).show(record_id)
    assert recorded.pdf is not None and recorded.pdf.current_pdf_id == pdf.pdf_id


@pytest.mark.parametrize("field", ["model_versions", "methods_data"])
def test_malformed_backend_models_do_not_emit_private_serializer_diagnostics(
    tmp_path: Path, field: str
) -> None:
    import warnings

    from paper_radar.fixture_audit.pdf_models import PdfBackendRegistration

    service, record_id = registered_jgr(tmp_path)
    source = tmp_path / "sample.pdf"
    source.write_bytes(PDF_BYTES)
    pdf = service.register_pdf(
        record_id,
        source,
        request_key="pdf",
        source_url="https://repository.example.org/pdf",
        access_basis="manual",
        license_basis="synthetic fixture",
        observed_date="2026-10-26",
    )
    valid = PdfBackendRegistration.model_validate(
        {
            "request_key": "backend",
            "pdf_id": pdf.pdf_id,
            "pdf_sha256": PDF_SHA256,
            "backend_component": "docling",
            "backend_version": "synthetic-v1",
            "extraction_fingerprint": "a" * 64,
            "reading_sha256": "b" * 64,
            "methods_data": {"state": "unverified"},
            "availability_open_research": {"state": "unverified"},
        }
    )
    value: object = (
        ("PDF_PRIVATE_DIAGNOSTIC_SENTINEL",)
        if field == "model_versions"
        else "PDF_PRIVATE_DIAGNOSTIC_SENTINEL"
    )
    malformed = valid.model_copy(update={field: value})
    with warnings.catch_warnings(record=True) as diagnostic:
        warnings.simplefilter("always")
        with pytest.raises(FixtureError) as rejected:
            service.register_pdf_backend(malformed)
    assert rejected.value.reason == "invalid_declaration"
    assert rejected.value.path == "pdf_backend"
    assert "PDF_PRIVATE_DIAGNOSTIC_SENTINEL" not in str(rejected.value)
    assert diagnostic == []
    assert service.check_pdf(record_id).backend_expectation_count == 0


def test_reordering_the_same_named_model_set_cannot_change_backend_expectations(
    tmp_path: Path,
) -> None:
    from paper_radar.fixture_audit.pdf_models import PdfBackendRegistration

    service, record_id = registered_jgr(tmp_path)
    source = tmp_path / "sample.pdf"
    source.write_bytes(PDF_BYTES)
    pdf = service.register_pdf(
        record_id,
        source,
        request_key="pdf",
        source_url="https://repository.example.org/pdf",
        access_basis="manual",
        license_basis="synthetic fixture",
        observed_date="2026-10-26",
    )
    request = PdfBackendRegistration.model_validate(
        {
            "request_key": "backend-original",
            "pdf_id": pdf.pdf_id,
            "pdf_sha256": PDF_SHA256,
            "backend_component": "docling",
            "backend_version": "synthetic-v1",
            "model_versions": (
                {"name": "table", "version": "model-v1"},
                {"name": "layout", "version": "model-v1"},
            ),
            "extraction_fingerprint": "a" * 64,
            "reading_sha256": "b" * 64,
            "methods_data": {"state": "unverified"},
            "availability_open_research": {"state": "unverified"},
        }
    )
    original = service.register_pdf_backend(request)
    reordered = request.model_copy(
        update={
            "request_key": "backend-reordered",
            "model_versions": tuple(reversed(request.model_versions)),
            "reading_sha256": "c" * 64,
        }
    )
    with pytest.raises(FixtureError) as rejected:
        service.register_pdf_backend(reordered)
    assert rejected.value.reason == "declaration_conflict"
    assert rejected.value.path == "pdf_backend.backend_identity"
    state = service.show(record_id).pdf
    assert state is not None
    assert state.acquisitions[0].backend_expectations == (original,)
    assert [model.name for model in original.registration.model_versions] == [
        "table",
        "layout",
    ]
    service.validate_all()
