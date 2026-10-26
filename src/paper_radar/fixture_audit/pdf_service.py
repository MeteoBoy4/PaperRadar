"""PDF 本机字节发布和短事务登记,不访问来源 URL。"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from pathlib import Path

from sqlalchemy import select

from paper_radar.fixture_audit.errors import FixtureError, FixtureReason
from paper_radar.fixture_audit.pdf_models import (
    PdfAcquisition,
    PdfBackendExpectation,
    PdfBackendRegistration,
    PdfRegistration,
)
from paper_radar.fixture_audit.pdf_records import (
    SampleScope,
    acquisition_identity,
    backend_identity,
    load_pdf_states,
)
from paper_radar.fixture_audit.pdf_tables import (
    fixture_pdf_acquisitions,
    fixture_pdf_expectations,
)
from paper_radar.storage.artifacts import ArtifactStore
from paper_radar.storage.database import (
    DatabaseMode,
    open_database,
    require_current_revision,
)


def register_pdf(
    database: Path,
    data_root: Path,
    source: Path,
    request: PdfRegistration,
    samples: Mapping[str, SampleScope],
) -> PdfAcquisition:
    scope = samples.get(request.sample_record_id)
    if scope is None or scope[0] != "pdf":
        raise FixtureError(FixtureReason.INVALID_REFERENCE, path="pdf.sample_record_id")
    store = ArtifactStore(database, data_root)
    try:
        with source.open("rb") as stream:

            def chunks() -> Iterator[bytes]:
                while chunk := stream.read(1024 * 1024):
                    yield chunk

            artifact = store.publish_single(
                "original_pdf", chunks(), expected_sha256=request.expected_sha256
            )
    except OSError:
        raise FixtureError(
            FixtureReason.SOURCE_UNAVAILABLE, path="pdf.source"
        ) from None
    member = artifact.members[0]
    if member.size_bytes == 0:
        raise FixtureError(FixtureReason.INVALID_DECLARATION, path="pdf.size_bytes")
    content: dict[str, object] = {
        "registration": request.model_dump(mode="json"),
        "artifact_id": artifact.artifact_id,
        "pdf_sha256": member.sha256,
        "size_bytes": member.size_bytes,
    }
    item = PdfAcquisition(
        pdf_id=acquisition_identity(content),
        registration=request,
        artifact_id=artifact.artifact_id,
        pdf_sha256=member.sha256,
        size_bytes=member.size_bytes,
    )
    engine = open_database(database, mode=DatabaseMode.READ_WRITE)
    try:
        require_current_revision(engine)
        with engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            states = load_pdf_states(connection, samples, store, verify_bytes=True)
            prior = connection.execute(
                select(fixture_pdf_acquisitions.c.content_json).where(
                    fixture_pdf_acquisitions.c.sample_record_id
                    == request.sample_record_id,
                    fixture_pdf_acquisitions.c.request_key == request.request_key,
                )
            ).scalar_one_or_none()
            if prior is not None:
                if prior != item.model_dump_json():
                    raise FixtureError(
                        FixtureReason.DECLARATION_CONFLICT, path="pdf.request_key"
                    )
                return item
            current = states.get(scope)
            if request.replaces != (
                current.current_pdf_id if current is not None else None
            ):
                raise FixtureError(FixtureReason.INVALID_REFERENCE, path="pdf.replaces")
            connection.execute(
                fixture_pdf_acquisitions.insert().values(
                    pdf_id=item.pdf_id,
                    sample_record_id=request.sample_record_id,
                    request_key=request.request_key,
                    artifact_id=item.artifact_id,
                    content_json=item.model_dump_json(),
                    replaces=request.replaces,
                )
            )
            connection.commit()
            return item
    finally:
        engine.dispose()


def register_pdf_backend(
    database: Path,
    data_root: Path,
    request: PdfBackendRegistration,
    samples: Mapping[str, SampleScope],
) -> PdfBackendExpectation:
    item = PdfBackendExpectation(
        expectation_id=acquisition_identity(request.model_dump(mode="json")),
        registration=request,
    )
    engine = open_database(database, mode=DatabaseMode.READ_WRITE)
    try:
        require_current_revision(engine)
        with engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            states = load_pdf_states(
                connection,
                samples,
                ArtifactStore(database, data_root),
                verify_bytes=True,
            )
            pdfs = {
                pdf.pdf_id: pdf
                for state in states.values()
                for pdf in state.acquisitions
            }
            pdf = pdfs.get(request.pdf_id)
            if pdf is None or pdf.pdf_sha256 != request.pdf_sha256:
                raise FixtureError(
                    FixtureReason.INVALID_REFERENCE, path="pdf_backend.pdf_sha256"
                )
            prior = connection.execute(
                select(fixture_pdf_expectations.c.content_json).where(
                    fixture_pdf_expectations.c.pdf_id == request.pdf_id,
                    fixture_pdf_expectations.c.request_key == request.request_key,
                )
            ).scalar_one_or_none()
            if prior is not None:
                if prior != item.model_dump_json():
                    raise FixtureError(
                        FixtureReason.DECLARATION_CONFLICT,
                        path="pdf_backend.request_key",
                    )
                return item
            identity = backend_identity(request)
            duplicate = connection.execute(
                select(fixture_pdf_expectations.c.expectation_id).where(
                    fixture_pdf_expectations.c.pdf_id == request.pdf_id,
                    fixture_pdf_expectations.c.backend_identity == identity,
                )
            ).scalar_one_or_none()
            if duplicate is not None:
                raise FixtureError(
                    FixtureReason.DECLARATION_CONFLICT,
                    path="pdf_backend.backend_identity",
                )
            connection.execute(
                fixture_pdf_expectations.insert().values(
                    expectation_id=item.expectation_id,
                    pdf_id=request.pdf_id,
                    request_key=request.request_key,
                    backend_identity=identity,
                    content_json=item.model_dump_json(),
                )
            )
            connection.commit()
            return item
    finally:
        engine.dispose()
