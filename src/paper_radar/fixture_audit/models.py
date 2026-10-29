"""Fixture 声明 v1 的唯一权威格式;不属于模型 Frozen Contract。"""

from __future__ import annotations

import json
from datetime import date
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from paper_radar.fixture_audit.errors import FixtureError, FixtureReason
from paper_radar.fixture_audit.pdf_models import PdfFixtureState
from paper_radar.papers.doi import normalize_doi
from paper_radar.papers.errors import PaperError
from paper_radar.sources.feeds import Journal as Journal

DECLARATION_FORMAT_VERSION = 1
Purpose = Literal["feed", "abstract_audit", "references", "pdf"]
Basis = Literal["historical_declaration", "synthetic", "acquired"]


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ConditionalHeaders(FrozenModel):
    if_none_match: str | None = None
    if_modified_since: str | None = None
    prior_artifact_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class AuditReference(FrozenModel):
    plan_id: str = Field(min_length=1)
    summary_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    feed_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    feed_snapshots: dict[Journal, str] = Field(default_factory=dict)

    @field_validator("feed_snapshots")
    @classmethod
    def validate_snapshots(cls, values: dict[Journal, str]) -> dict[Journal, str]:
        if any(
            len(value) != 64 or any(c not in "0123456789abcdef" for c in value)
            for value in values.values()
        ):
            raise ValueError("feed_snapshots")
        return values


class FixtureExpectations(FrozenModel):
    publisher_count: int | None = Field(default=None, ge=0)
    registry_count: int | None = Field(default=None, ge=0)
    registry_record_absent: bool = False
    layout_features: tuple[str, ...] = ()
    known_failures: tuple[str, ...] = ()
    candidate_dois: tuple[str, ...] = ()

    @field_validator("candidate_dois")
    @classmethod
    def validate_candidates(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        for value in values:
            normalize_doi(value)
        return values


class FixtureEntry(FrozenModel):
    key: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,127}$")
    purpose: Purpose
    journal: Journal | None = None
    basis: Basis
    doi: str | None = None
    handle: str | None = Field(default=None, min_length=1)
    upstream_id: str | None = Field(default=None, min_length=1)
    declared_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    source_basis: str = Field(min_length=1, max_length=2000)
    notes: tuple[str, ...] = ()
    parser_version: str | None = Field(default=None, min_length=1)
    conditional_headers: ConditionalHeaders | None = None
    expectations: FixtureExpectations = Field(default_factory=FixtureExpectations)
    audit_reference: AuditReference | None = None
    replaces: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    replacement_reason: str | None = Field(default=None, min_length=1, max_length=2000)

    @field_validator("declared_date")
    @classmethod
    def validate_date(cls, value: str | None) -> str | None:
        if value is not None:
            date.fromisoformat(value)
        return value

    @field_validator("source_basis", "replacement_reason")
    @classmethod
    def validate_nonblank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("blank")
        return value

    @field_validator("doi")
    @classmethod
    def validate_doi(cls, value: str | None) -> str | None:
        if value is not None:
            normalize_doi(value)
        return value

    @model_validator(mode="after")
    def validate_relationships(self) -> Self:
        if (self.purpose == "abstract_audit") != (self.journal is None):
            raise ValueError("journal")
        if (self.replaces is None) != (self.replacement_reason is None):
            raise ValueError("replacement_reason")
        if self.audit_reference is not None and (
            self.purpose not in {"feed", "abstract_audit"} or self.basis != "acquired"
        ):
            raise ValueError("audit_reference")
        if self.basis != "acquired" and self.conditional_headers is not None:
            raise ValueError("conditional_headers")
        if self.purpose != "references" and (
            self.expectations.publisher_count is not None
            or self.expectations.registry_count is not None
            or self.expectations.registry_record_absent
        ):
            raise ValueError("expectations")
        if (
            self.expectations.registry_record_absent
            and self.expectations.registry_count is not None
        ):
            raise ValueError("expectations.registry_count")
        return self


class FixtureDeclaration(FrozenModel):
    format_version: Literal[1]
    declaration_key: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,127}$")
    declared_version: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$")
    entries: tuple[FixtureEntry, ...] = Field(min_length=1)

    @field_validator("format_version", mode="before")
    @classmethod
    def strict_format_version(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("format_version")
        return value

    @model_validator(mode="after")
    def unique_logical_keys(self) -> Self:
        keys = [(entry.purpose, entry.journal, entry.key) for entry in self.entries]
        if len(set(keys)) != len(keys):
            raise ValueError("entries.duplicate_key")
        return self


class FixtureRecord(FrozenModel):
    record_id: str
    declaration_id: str
    declaration_key: str
    declared_version: str
    raw_sha256: str
    entry: FixtureEntry
    current: bool
    byte_verified: bool = True
    pdf: PdfFixtureState | None = None
    audit_verification: (
        Literal[
            "declaration_and_reference_verified",
            "frozen_v1_material_and_execution_facts_verified",
        ]
        | None
    ) = None


class RegistrationResult(FrozenModel):
    declaration_id: str
    raw_sha256: str
    entries: tuple[FixtureRecord, ...]


class DeclarationCheck(FrozenModel):
    status: Literal["byte_verified", "source_missing", "unregistered", "drift"]
    source_available: bool
    declaration_id: str | None = None
    raw_sha256: str | None = None
    entries: tuple[FixtureRecord, ...] = ()


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def parse_declaration(raw: bytes) -> FixtureDeclaration:
    try:
        parsed = json.loads(raw, object_pairs_hook=_unique_json_object)
        if (
            isinstance(parsed, dict)
            and type(parsed.get("format_version")) is int
            and parsed["format_version"] != 1
        ):
            raise FixtureError(FixtureReason.UNSUPPORTED_FORMAT, path="format_version")
        return FixtureDeclaration.model_validate_json(raw)
    except FixtureError:
        raise
    except ValidationError as error:
        location = error.errors(include_input=False)[0]["loc"]
        # Extra-field names are caller-controlled, so only expose known schema paths.
        safe = (
            set(FixtureDeclaration.model_fields)
            | set(FixtureEntry.model_fields)
            | set(FixtureExpectations.model_fields)
        )
        path = ".".join(
            str(part) for part in location if isinstance(part, int) or part in safe
        )
        raise FixtureError(
            FixtureReason.INVALID_DECLARATION, path=path or "declaration"
        ) from None
    except (ValueError, UnicodeError, PaperError):
        raise FixtureError(FixtureReason.INVALID_DECLARATION) from None
