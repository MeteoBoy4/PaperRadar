"""新解析器是显式注入接口；持久化解释不携带原摘要文本。"""

from collections.abc import Mapping
from typing import Literal, Protocol

from pydantic import Field

from paper_radar.fixture_audit.abstract_models import Signal
from paper_radar.fixture_audit.acquisition_models import SourceRequest
from paper_radar.fixture_audit.models import FrozenModel


class AuditMaterialParser(Protocol):
    version: str
    implementation_sha256: str

    def parse(
        self,
        request: SourceRequest,
        raw: bytes,
        *,
        decoding: str,
        entry_locator: str | None,
    ) -> Mapping[str, str | None]: ...


class ParserDeclaration(FrozenModel):
    declaration_id: str
    parser_version: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    implementation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


FieldName = Literal["title", "abstract", "identity_doi", "category"]


class InterpretedField(FrozenModel):
    field: FieldName
    text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    codepoints: int = Field(ge=1)
    signals: tuple[Signal, ...] = ()
    suspected_truncated: bool = False


class InterpretationRow(FrozenModel):
    base_row_id: str
    acquisition_id: str
    fields: tuple[InterpretedField, ...]
    added: tuple[FieldName, ...] = ()
    removed: tuple[FieldName, ...] = ()
    changed: tuple[FieldName, ...] = ()
    proof_level: Literal["material_reparsed", "execution_facts_only"]


class AuditInterpretation(FrozenModel):
    interpretation_id: str
    plan_id: str
    request_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    parser_declaration: ParserDeclaration
    parser_version: str
    previous_interpretation_id: str | None = None
    basis_sha256: str
    rows: tuple[InterpretationRow, ...]
    created_at: str
    proof_level: Literal["declaration_and_reference_verified"] = (
        "declaration_and_reference_verified"
    )


class InterpretationReplay(FrozenModel):
    interpretation: AuditInterpretation
    status: Literal["verified"] = "verified"
    proof_level: Literal["available_material_reparsed"] = "available_material_reparsed"
