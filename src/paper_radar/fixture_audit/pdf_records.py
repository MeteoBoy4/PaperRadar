"""PDF 历史身份及当前选择的只读重建。"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping

from pydantic import ValidationError
from sqlalchemy import Connection, select

from paper_radar.fixture_audit.errors import FixtureError, FixtureReason
from paper_radar.fixture_audit.pdf_models import (
    PdfAcquisition,
    PdfAcquisitionView,
    PdfBackendExpectation,
    PdfBackendRegistration,
    PdfFixtureState,
)
from paper_radar.fixture_audit.pdf_tables import (
    fixture_pdf_acquisitions,
    fixture_pdf_expectations,
)
from paper_radar.storage.artifact_repository import read_registration
from paper_radar.storage.artifacts import ArtifactStore

SampleScope = tuple[str, str | None, str]


def acquisition_identity(content: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(
            content, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()
    ).hexdigest()


def load_pdf_states(
    connection: Connection,
    samples: Mapping[str, SampleScope],
    store: ArtifactStore | None,
    *,
    verify_bytes: bool,
) -> dict[SampleScope, PdfFixtureState]:
    acquisitions: dict[SampleScope, list[PdfAcquisition]] = {}
    current: dict[SampleScope, str] = {}
    for row in connection.execute(
        select(fixture_pdf_acquisitions).order_by(fixture_pdf_acquisitions.c.event_no)
    ).mappings():
        try:
            item = PdfAcquisition.model_validate_json(row["content_json"])
        except (ValidationError, ValueError):
            raise FixtureError(FixtureReason.CORRUPT_REFERENCE, path="pdf") from None
        request = item.registration
        scope = samples.get(request.sample_record_id)
        if (
            scope is None
            or scope[0] != "pdf"
            or item.pdf_id != row["pdf_id"]
            or request.sample_record_id != row["sample_record_id"]
            or request.request_key != row["request_key"]
            or item.artifact_id != row["artifact_id"]
            or request.replaces != row["replaces"]
            or item.pdf_id
            != acquisition_identity(
                item.model_dump(mode="json", exclude={"pdf_id", "byte_verified"})
            )
            or request.replaces != current.get(scope)
        ):
            raise FixtureError(FixtureReason.CORRUPT_REFERENCE, path="pdf")
        # 缺失 data_root 时仍核验制品登记、种类及引用,不构造 cwd 假根。
        artifact = (
            store.get_artifact(item.artifact_id)
            if store is not None
            else read_registration(connection.engine, item.artifact_id)[0]
        )
        if (
            artifact.kind != "original_pdf"
            or len(artifact.members) != 1
            or artifact.members[0].sha256 != item.pdf_sha256
            or artifact.members[0].size_bytes != item.size_bytes
        ):
            raise FixtureError(FixtureReason.CORRUPT_REFERENCE, path="pdf.artifact")
        if verify_bytes:
            if store is None:
                raise FixtureError(FixtureReason.EVIDENCE_REQUIRED, path="data_root")
            store.read_artifact(item.artifact_id)
        acquisitions.setdefault(scope, []).append(item)
        current[scope] = item.pdf_id
    by_id = {item.pdf_id: item for items in acquisitions.values() for item in items}
    expectations: dict[str, list[PdfBackendExpectation]] = {}
    for row in connection.execute(
        select(fixture_pdf_expectations).order_by(fixture_pdf_expectations.c.event_no)
    ).mappings():
        try:
            expected = PdfBackendExpectation.model_validate_json(row["content_json"])
        except (ValidationError, ValueError):
            raise FixtureError(
                FixtureReason.CORRUPT_REFERENCE, path="pdf_backend"
            ) from None
        registration = expected.registration
        pdf = by_id.get(registration.pdf_id)
        if (
            pdf is None
            or registration.pdf_sha256 != pdf.pdf_sha256
            or expected.expectation_id != row["expectation_id"]
            or expected.expectation_id
            != acquisition_identity(registration.model_dump(mode="json"))
            or registration.request_key != row["request_key"]
            or registration.pdf_id != row["pdf_id"]
            or backend_identity(registration) != row["backend_identity"]
        ):
            raise FixtureError(FixtureReason.CORRUPT_REFERENCE, path="pdf_backend")
        expectations.setdefault(registration.pdf_id, []).append(expected)
    return {
        scope: PdfFixtureState(
            current_pdf_id=current[scope],
            acquisitions=tuple(
                PdfAcquisitionView(
                    **item.model_dump(),
                    current=item.pdf_id == current[scope],
                    backend_expectations=tuple(expectations.get(item.pdf_id, ())),
                )
                for item in values
            ),
        )
        for scope, values in acquisitions.items()
    }


def backend_identity(request: PdfBackendRegistration) -> str:
    identity = request.model_dump(
        mode="json",
        include={
            "backend_component",
            "backend_version",
            "extraction_fingerprint",
        },
    )
    identity["model_versions"] = [
        model.model_dump(mode="json")
        for model in sorted(request.model_versions, key=lambda model: model.name)
    ]
    return acquisition_identity(identity)
