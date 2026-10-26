"""注入解析器的追加解释；默认核验声明与引用，显式运行时才重解析新版本。"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import Connection, select
from sqlalchemy.exc import SQLAlchemyError

from paper_radar.fixture_audit.abstract_models import AbstractAuditView, MatrixRow
from paper_radar.fixture_audit.abstract_parser import signals
from paper_radar.fixture_audit.abstract_service import AbstractService
from paper_radar.fixture_audit.acquisition_models import (
    identity_sha256,
    require_utc_timestamp,
)
from paper_radar.fixture_audit.acquisition_service import utc_now
from paper_radar.fixture_audit.errors import FixtureError, FixtureReason
from paper_radar.fixture_audit.interpretation_models import (
    AuditInterpretation,
    AuditMaterialParser,
    InterpretationReplay,
    InterpretationRow,
    InterpretedField,
    ParserDeclaration,
)
from paper_radar.fixture_audit.interpretation_tables import (
    interpretations,
    parser_declarations,
)
from paper_radar.papers.doi import normalize_doi
from paper_radar.papers.errors import PaperError
from paper_radar.papers.text_rules import normalize_text
from paper_radar.storage.artifacts import ArtifactStore
from paper_radar.storage.database import (
    DatabaseMode,
    open_database,
    require_current_revision,
)


def field_value(name: str, value: str) -> InterpretedField:
    if name == "identity_doi":
        value = normalize_doi(value)
    elif name == "category" and value not in {
        "journal_article",
        "non_journal_article",
        "unknown",
        "conflict",
    }:
        raise ValueError("category")
    value = normalize_text(value)
    flags = signals(value) if name == "abstract" else ()
    return InterpretedField.model_validate(
        dict(
            field=name,
            text_sha256=hashlib.sha256(value.encode()).hexdigest(),
            codepoints=len(value),
            signals=flags,
            suspected_truncated=bool(flags),
        )
    )


def baseline(view: AbstractAuditView, row: MatrixRow) -> tuple[InterpretedField, ...]:
    values = [
        InterpretedField(
            field=candidate.field,
            text_sha256=candidate.text_sha256,
            codepoints=candidate.codepoints,
            signals=candidate.signals,
            suspected_truncated=candidate.suspected_truncated,
        )
        for candidate in row.candidates
    ]
    source = next(
        value for value in view.executions if value.execution_id == row.acquisition_id
    )
    state = next(
        value for value in view.sampling if value.journal == row.request.journal
    )
    member = next(value for value in state.members if value.member_id == row.member_id)
    event = next(
        value for value in state.history if value.event_id == member.selection_event_id
    )
    doi = (
        event.candidate.doi
        if row.request.route == "feed" and event.candidate
        else source.settlement.identity_doi
        if source.settlement
        else None
    )
    if doi:
        values.append(field_value("identity_doi", doi))
    categories = {
        value.decision
        for value in event.category_bases
        if value.route == row.request.route
    }
    if categories:
        values.append(
            field_value(
                "category",
                "conflict"
                if len(categories - {"unknown"}) > 1
                else sorted(categories - {"unknown"} or categories)[0],
            )
        )
    return tuple(sorted(values, key=lambda value: value.field))


def row_projection(
    row: MatrixRow,
    old: tuple[InterpretedField, ...],
    new: tuple[InterpretedField, ...],
    *,
    material: bool,
) -> InterpretationRow:
    old_by = {value.field: value for value in old}
    new_by = {value.field: value for value in new}
    return InterpretationRow(
        base_row_id=row.row_id,
        acquisition_id=row.acquisition_id or "",
        fields=new,
        added=tuple(sorted(new_by.keys() - old_by.keys())),
        removed=tuple(sorted(old_by.keys() - new_by.keys())),
        changed=tuple(
            sorted(
                name
                for name in old_by.keys() & new_by.keys()
                if old_by[name] != new_by[name]
            )
        ),
        proof_level="material_reparsed" if material else "execution_facts_only",
    )


def basis_identity(rows: tuple[InterpretationRow, ...]) -> str:
    return hashlib.sha256(
        "\0".join(row.base_row_id for row in rows).encode()
    ).hexdigest()


def load_interpretations(
    connection: Connection, views: tuple[AbstractAuditView, ...]
) -> tuple[AuditInterpretation, ...]:
    by_plan = {view.plan.plan_id: view for view in views}
    declarations: dict[str, ParserDeclaration] = {}
    result: list[AuditInterpretation] = []
    latest: dict[str, AuditInterpretation] = {}
    try:
        for record in connection.execute(select(parser_declarations)).mappings():
            declaration = ParserDeclaration.model_validate_json(record["content_json"])
            if (
                declaration.declaration_id != record["declaration_id"]
                or declaration.parser_version != record["parser_version"]
                or declaration.model_dump_json() != record["content_json"]
                or identity_sha256(
                    declaration.model_copy(update={"declaration_id": ""})
                )
                != declaration.declaration_id
            ):
                raise FixtureError(
                    FixtureReason.CORRUPT_REFERENCE, path="audit.parser_declaration"
                )
            declarations[declaration.declaration_id] = declaration
        for record in connection.execute(
            select(interpretations).order_by(interpretations.c.event_no)
        ).mappings():
            value = AuditInterpretation.model_validate_json(record["content_json"])
            if (
                value.plan_id not in by_plan
                or value.interpretation_id != record["interpretation_id"]
                or value.plan_id != record["plan_id"]
                or value.request_key != record["request_key"]
                or value.previous_interpretation_id
                != record["previous_interpretation_id"]
                or value.parser_declaration
                != declarations.get(record["parser_declaration_id"])
                or value.parser_version != value.parser_declaration.parser_version
                or value.model_dump_json() != record["content_json"]
                or identity_sha256(value.model_copy(update={"interpretation_id": ""}))
                != value.interpretation_id
                or require_utc_timestamp(value.created_at) != value.created_at
            ):
                raise FixtureError(
                    FixtureReason.CORRUPT_REFERENCE, path="audit.interpretation"
                )
            previous = latest.get(value.plan_id)
            if value.previous_interpretation_id != (
                previous.interpretation_id if previous else None
            ):
                raise FixtureError(
                    FixtureReason.CORRUPT_REFERENCE, path="audit.interpretation_chain"
                )
            view = by_plan[value.plan_id]
            original = {row.row_id: row for row in view.matrix_history}
            if value.basis_sha256 != basis_identity(value.rows) or len(
                value.rows
            ) != len(view.matrix):
                raise FixtureError(
                    FixtureReason.CORRUPT_REFERENCE, path="audit.interpretation_basis"
                )
            keys = set()
            for item in value.rows:
                row = original.get(item.base_row_id)
                if row is None or row.acquisition_id != item.acquisition_id:
                    raise FixtureError(
                        FixtureReason.CORRUPT_REFERENCE,
                        path="audit.interpretation_source",
                    )
                key = (row.member_id, row.request.route, row.request.channel)
                if (
                    key in keys
                    or tuple(sorted(item.fields, key=lambda field: field.field))
                    != item.fields
                    or len({field.field for field in item.fields}) != len(item.fields)
                    or any(
                        field.suspected_truncated != bool(field.signals)
                        for field in item.fields
                    )
                ):
                    raise FixtureError(
                        FixtureReason.CORRUPT_REFERENCE,
                        path="audit.interpretation_fields",
                    )
                keys.add(key)
                source = next(
                    source
                    for source in view.executions
                    if source.execution_id == row.acquisition_id
                )
                material = bool(source.settlement and source.settlement.artifact_id)
                if row_projection(
                    row, baseline(view, row), item.fields, material=material
                ) != item or (not material and item.fields != baseline(view, row)):
                    raise FixtureError(
                        FixtureReason.CORRUPT_REFERENCE,
                        path="audit.interpretation_difference",
                    )
            result.append(value)
            latest[value.plan_id] = value
        if {
            value.parser_declaration.declaration_id for value in result
        } != declarations.keys():
            raise FixtureError(
                FixtureReason.CORRUPT_REFERENCE, path="audit.parser_declaration"
            )
        return tuple(result)
    except (
        ValueError,
        TypeError,
        KeyError,
        StopIteration,
        ValidationError,
        PaperError,
    ):
        raise FixtureError(
            FixtureReason.CORRUPT_REFERENCE, path="audit.interpretation"
        ) from None


class InterpretationService:
    def __init__(
        self, database: Path, data_root: Path | None, abstracts: AbstractService
    ) -> None:
        self.database, self.data_root, self.abstracts = database, data_root, abstracts

    def list(self, plan_id: str | None = None) -> tuple[AuditInterpretation, ...]:
        engine = open_database(self.database, mode=DatabaseMode.READ_ONLY)
        try:
            require_current_revision(engine)
            with engine.connect() as connection:
                connection.exec_driver_sql("BEGIN")
                from paper_radar.fixture_audit.abstract_service import load_abstracts
                from paper_radar.fixture_audit.acquisition_records import load_audits
                from paper_radar.fixture_audit.sampling_records import load_sampling

                values = load_interpretations(
                    connection,
                    load_abstracts(
                        connection, load_sampling(connection, load_audits(connection))
                    ),
                )
                return tuple(
                    value
                    for value in values
                    if plan_id is None or value.plan_id == plan_id
                )
        except SQLAlchemyError:
            raise FixtureError(
                FixtureReason.CORRUPT_REFERENCE, path="audit.interpretation"
            ) from None
        finally:
            engine.dispose()

    def _declaration(self, parser: AuditMaterialParser) -> ParserDeclaration:
        try:
            declaration = ParserDeclaration(
                declaration_id="",
                parser_version=parser.version,
                implementation_sha256=parser.implementation_sha256,
            )
            if declaration.parser_version == "audit-abstract-v1":
                raise ValueError("published_parser")
            return declaration.model_copy(
                update={"declaration_id": identity_sha256(declaration)}
            )
        except Exception:
            raise FixtureError(
                FixtureReason.INVALID_REQUEST, path="audit.parser"
            ) from None

    def _rows(
        self,
        view: AbstractAuditView,
        rows: tuple[MatrixRow, ...],
        parser: AuditMaterialParser,
    ) -> tuple[InterpretationRow, ...]:
        result = []
        for row in rows:
            old = baseline(view, row)
            source = next(
                value
                for value in view.executions
                if value.execution_id == row.acquisition_id
            )
            if not source.settlement or not source.settlement.artifact_id:
                result.append(row_projection(row, old, old, material=False))
                continue
            if self.data_root is None:
                raise FixtureError(FixtureReason.EVIDENCE_REQUIRED, path="data_root")
            raw = ArtifactStore(self.database, self.data_root).read_artifact(
                source.settlement.artifact_id
            )["payload"]
            state = next(
                value for value in view.sampling if value.journal == row.request.journal
            )
            member = next(
                value for value in state.members if value.member_id == row.member_id
            )
            event = next(
                value
                for value in state.history
                if value.event_id == member.selection_event_id
            )
            try:
                values = parser.parse(
                    row.request,
                    raw,
                    decoding=source.settlement.content_decoding or "utf-8",
                    entry_locator=event.candidate.entry_locator
                    if row.request.route == "feed" and event.candidate
                    else None,
                )
                if (
                    not isinstance(values, Mapping)
                    or not values.keys()
                    <= {"title", "abstract", "identity_doi", "category"}
                    or any(
                        value is not None and not isinstance(value, str)
                        for value in values.values()
                    )
                ):
                    raise ValueError("fields")
                fields = tuple(
                    field_value(name, value)
                    for name, value in sorted(values.items())
                    if value is not None and value.strip()
                )
            except Exception:
                raise FixtureError(
                    FixtureReason.INVALID_REQUEST, path="audit.parser_output"
                ) from None
            result.append(row_projection(row, old, fields, material=True))
        return tuple(result)

    def append(
        self, plan_id: str, *, parser: AuditMaterialParser, request_key: str
    ) -> AuditInterpretation:
        declaration = self._declaration(parser)
        with self.abstracts.acquisitions.audit_execution(plan_id):
            view = self.abstracts.show_audit(plan_id)
            if view.status != "complete":
                raise FixtureError(
                    FixtureReason.EXECUTION_INCOMPLETE, path="audit.interpretation"
                )
            existing = self.list(plan_id)
            prior = next(
                (value for value in existing if value.request_key == request_key), None
            )
            rows = self._rows(view, view.matrix, parser)
            try:
                value = AuditInterpretation(
                    interpretation_id="",
                    plan_id=plan_id,
                    request_key=request_key,
                    parser_declaration=declaration,
                    parser_version=declaration.parser_version,
                    previous_interpretation_id=prior.previous_interpretation_id
                    if prior
                    else existing[-1].interpretation_id
                    if existing
                    else None,
                    basis_sha256=basis_identity(rows),
                    rows=rows,
                    created_at=prior.created_at if prior else utc_now(),
                )
            except ValidationError:
                raise FixtureError(
                    FixtureReason.INVALID_REQUEST, path="audit.interpretation"
                ) from None
            value = value.model_copy(
                update={"interpretation_id": identity_sha256(value)}
            )
            if prior:
                if prior != value:
                    raise FixtureError(
                        FixtureReason.RESULT_CONFLICT, path="audit.interpretation"
                    )
                return prior
            engine = open_database(self.database, mode=DatabaseMode.READ_WRITE)
            try:
                require_current_revision(engine)
                with engine.connect() as connection:
                    connection.exec_driver_sql("BEGIN IMMEDIATE")
                    known = (
                        connection.execute(
                            select(parser_declarations).where(
                                parser_declarations.c.parser_version
                                == declaration.parser_version
                            )
                        )
                        .mappings()
                        .first()
                    )
                    if (
                        known is not None
                        and known["declaration_id"] != declaration.declaration_id
                    ):
                        raise FixtureError(
                            FixtureReason.REQUEST_CONFLICT, path="audit.parser_version"
                        )
                    if known is None:
                        connection.execute(
                            parser_declarations.insert().values(
                                declaration_id=declaration.declaration_id,
                                parser_version=declaration.parser_version,
                                content_json=declaration.model_dump_json(),
                            )
                        )
                    connection.execute(
                        interpretations.insert().values(
                            interpretation_id=value.interpretation_id,
                            plan_id=plan_id,
                            request_key=request_key,
                            parser_declaration_id=declaration.declaration_id,
                            previous_interpretation_id=value.previous_interpretation_id,
                            content_json=value.model_dump_json(),
                        )
                    )
                    from paper_radar.fixture_audit.abstract_service import (
                        load_abstracts,
                    )
                    from paper_radar.fixture_audit.acquisition_records import (
                        load_audits,
                    )
                    from paper_radar.fixture_audit.sampling_records import load_sampling

                    load_interpretations(
                        connection,
                        load_abstracts(
                            connection,
                            load_sampling(connection, load_audits(connection)),
                        ),
                    )
                    connection.commit()
                return value
            except SQLAlchemyError:
                raise FixtureError(
                    FixtureReason.CORRUPT_REFERENCE, path="audit.interpretation"
                ) from None
            finally:
                engine.dispose()

    def replay(
        self,
        plan_id: str,
        interpretation_id: str,
        *,
        parser: AuditMaterialParser | None = None,
    ) -> InterpretationReplay:
        value = next(
            (
                value
                for value in self.list(plan_id)
                if value.interpretation_id == interpretation_id
            ),
            None,
        )
        if value is None:
            raise FixtureError(FixtureReason.RECORD_NOT_FOUND, path="interpretation_id")
        if parser is None or self._declaration(parser) != value.parser_declaration:
            raise FixtureError(FixtureReason.UNSUPPORTED_HISTORY, path="audit.parser")
        view = self.abstracts.show_audit(plan_id)
        by_id = {row.row_id: row for row in view.matrix_history}
        rows = self._rows(
            view, tuple(by_id[row.base_row_id] for row in value.rows), parser
        )
        if rows != value.rows:
            raise FixtureError(
                FixtureReason.CORRUPT_REFERENCE, path="audit.interpretation_replay"
            )
        return InterpretationReplay(interpretation=value)
