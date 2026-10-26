"""给定 PDF 字节的取得事实;不证明身份、许可或解析质量。"""

from __future__ import annotations

from datetime import date
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from paper_radar.papers.errors import PaperError
from paper_radar.papers.text import require_public_url


class PdfModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, strict=True, revalidate_instances="always"
    )


class PdfRegistration(PdfModel):
    request_key: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$")
    sample_record_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_url: str
    access_basis: Literal["open", "licensed", "manual"]
    license_basis: str = Field(min_length=1, max_length=2000)
    observed_date: str
    expected_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    replaces: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    replacement_reason: str | None = Field(default=None, min_length=1, max_length=2000)

    @field_validator("source_url")
    @classmethod
    def public_source_url(cls, value: str) -> str:
        try:
            require_public_url(value, required=True)
        except PaperError:
            raise ValueError("source_url") from None
        return value

    @field_validator("observed_date")
    @classmethod
    def valid_date(cls, value: str) -> str:
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError("observed_date")
        return value

    @field_validator("license_basis", "replacement_reason")
    @classmethod
    def nonblank_basis(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("empty_basis")
        return value

    @model_validator(mode="after")
    def replacement_pair(self) -> Self:
        if (self.replaces is None) != (self.replacement_reason is None):
            raise ValueError("replacement_reason")
        return self


class PdfAcquisition(PdfModel):
    pdf_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    registration: PdfRegistration
    artifact_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    pdf_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(gt=0)
    byte_verified: Literal[True] = True

    @field_validator("byte_verified", mode="before")
    @classmethod
    def strict_byte_proof(cls, value: object) -> object:
        if value is not True:
            raise ValueError("byte_verified")
        return value

    @model_validator(mode="after")
    def expected_hash_matches(self) -> Self:
        if (
            self.registration.expected_sha256 is not None
            and self.registration.expected_sha256 != self.pdf_sha256
        ):
            raise ValueError("expected_sha256")
        return self


class SectionExpectation(PdfModel):
    state: Literal["unverified", "located", "confirmed_absent"]
    locator: str | None = Field(default=None, min_length=1, max_length=2000)
    inspection_basis: str | None = Field(default=None, min_length=1, max_length=2000)

    @model_validator(mode="after")
    def explicit_inspection(self) -> Self:
        if self.state == "unverified":
            if self.locator is not None or self.inspection_basis is not None:
                raise ValueError("unverified")
        elif self.inspection_basis is None or not self.inspection_basis.strip():
            raise ValueError("inspection_basis")
        if (self.state == "located") != (self.locator is not None):
            raise ValueError("locator")
        if self.locator is not None and not self.locator.strip():
            raise ValueError("locator")
        return self


class BackendModelVersion(PdfModel):
    name: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=256)

    @field_validator("name", "version")
    @classmethod
    def nonblank_version(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("version")
        return value


class PdfBackendRegistration(PdfModel):
    request_key: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$")
    pdf_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    pdf_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    backend_component: str = Field(min_length=1, max_length=128)
    backend_version: str = Field(min_length=1, max_length=256)
    model_versions: tuple[BackendModelVersion, ...] = ()
    extraction_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    reading_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    methods_data: SectionExpectation
    availability_open_research: SectionExpectation

    @field_validator("backend_component", "backend_version")
    @classmethod
    def nonblank_backend(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("backend")
        return value

    @model_validator(mode="after")
    def unique_models(self) -> Self:
        if len({item.name for item in self.model_versions}) != len(self.model_versions):
            raise ValueError("model_versions")
        return self


class PdfBackendExpectation(PdfModel):
    expectation_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    registration: PdfBackendRegistration
    proof_level: Literal["shape_only"] = "shape_only"


class PdfAcquisitionView(PdfAcquisition):
    current: bool
    backend_expectations: tuple[PdfBackendExpectation, ...] = ()


class PdfFixtureState(PdfModel):
    current_pdf_id: str | None
    acquisitions: tuple[PdfAcquisitionView, ...]


class PdfEvidenceCheck(PdfModel):
    status: Literal["not_registered", "byte_verified"]
    current_pdf_id: str | None
    acquisition_count: int
    backend_expectation_count: int
    backend_proof_level: Literal["shape_only"] = "shape_only"
