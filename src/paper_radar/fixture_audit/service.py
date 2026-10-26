"""声明登记和历史公共服务;写入短事务,读取固定一致视图。"""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Mapping
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import Connection, select
from sqlalchemy.exc import DBAPIError, SQLAlchemyError

from paper_radar.fixture_audit.acquisition_models import (
    AuditPlan,
    AuditView,
    Channel,
    CodeIdentity,
    RouteExecution,
    SourceRequest,
)
from paper_radar.fixture_audit.acquisition_service import AcquisitionService
from paper_radar.fixture_audit.audit_protection import AuditProtection
from paper_radar.fixture_audit.errors import FixtureError, FixtureReason
from paper_radar.fixture_audit.models import (
    DeclarationCheck,
    FixtureDeclaration,
    FixtureEntry,
    FixtureRecord,
    RegistrationResult,
    parse_declaration,
)
from paper_radar.fixture_audit.pdf_models import (
    PdfAcquisition,
    PdfBackendExpectation,
    PdfBackendRegistration,
    PdfEvidenceCheck,
    PdfRegistration,
)
from paper_radar.fixture_audit.pdf_records import load_pdf_states
from paper_radar.fixture_audit.source_http import SourceExecutor
from paper_radar.fixture_audit.tables import fixture_declarations, fixture_records
from paper_radar.storage.artifacts import ArtifactStore
from paper_radar.storage.database import (
    DatabaseMode,
    open_database,
    require_current_revision,
)


def _record_id(declaration_id: str, entry: FixtureEntry) -> str:
    identity = "\0".join((declaration_id, entry.purpose, entry.journal, entry.key))
    return hashlib.sha256(identity.encode()).hexdigest()


def _database_error(error: SQLAlchemyError) -> FixtureError:
    if (
        isinstance(error, DBAPIError)
        and isinstance(error.orig, sqlite3.Error)
        and (getattr(error.orig, "sqlite_errorcode", 0) & 0xFF) == sqlite3.SQLITE_BUSY
    ):
        return FixtureError(FixtureReason.DATABASE_BUSY)
    return FixtureError(FixtureReason.CORRUPT_REFERENCE)


def _load_records(connection: Connection) -> tuple[FixtureRecord, ...]:
    declarations: dict[str, tuple[FixtureDeclaration, str]] = {}
    expected: dict[str, FixtureEntry] = {}
    for row in connection.execute(select(fixture_declarations)).mappings():
        raw = row["raw_content"]
        if not isinstance(raw, bytes):
            raise FixtureError(FixtureReason.CORRUPT_REFERENCE)
        digest = hashlib.sha256(raw).hexdigest()
        declaration = parse_declaration(raw)
        if any(entry.basis == "acquired" for entry in declaration.entries):
            raise FixtureError(FixtureReason.CORRUPT_REFERENCE, path="entries.basis")
        if (
            digest != row["raw_sha256"]
            or digest != row["declaration_id"]
            or declaration.declaration_key != row["declaration_key"]
            or declaration.declared_version != row["declared_version"]
            or declaration.format_version != row["format_version"]
        ):
            raise FixtureError(FixtureReason.CORRUPT_REFERENCE)
        declarations[digest] = declaration, digest
        for entry in declaration.entries:
            expected[_record_id(digest, entry)] = entry
    records: list[FixtureRecord] = []
    current: dict[tuple[str, str, str], str] = {}
    seen: set[str] = set()
    replaced: set[str] = set()
    for row in connection.execute(
        select(fixture_records).order_by(fixture_records.c.event_no)
    ).mappings():
        identity = row["record_id"]
        if identity not in expected or row["declaration_id"] not in declarations:
            raise FixtureError(FixtureReason.CORRUPT_REFERENCE)
        entry = expected[identity]
        declaration, digest = declarations[row["declaration_id"]]
        if (
            _record_id(digest, entry) != identity
            or entry.model_dump_json() != row["entry_json"]
            or entry.purpose != row["purpose"]
            or entry.journal != row["journal"]
            or entry.key != row["sample_key"]
            or entry.replaces != row["replaces"]
        ):
            raise FixtureError(FixtureReason.CORRUPT_REFERENCE)
        logical = entry.purpose, entry.journal, entry.key
        if entry.replaces is None:
            if logical in current:
                raise FixtureError(FixtureReason.CORRUPT_REFERENCE)
        elif entry.replaces not in seen or current.get(logical) != entry.replaces:
            raise FixtureError(FixtureReason.CORRUPT_REFERENCE)
        else:
            replaced.add(entry.replaces)
        current[logical] = identity
        seen.add(identity)
        records.append(
            FixtureRecord(
                record_id=identity,
                declaration_id=digest,
                declaration_key=declaration.declaration_key,
                declared_version=declaration.declared_version,
                raw_sha256=digest,
                entry=entry,
                current=True,
            )
        )
    if seen != set(expected):
        raise FixtureError(FixtureReason.CORRUPT_REFERENCE)
    return tuple(
        record.model_copy(update={"current": record.record_id not in replaced})
        for record in records
    )


class FixtureAudit:
    """构造不打开数据库、不创建目录;实际取得字节由后续入口登记。"""

    def __init__(
        self,
        database: Path,
        data_root: Path | None = None,
        *,
        source_executors: Mapping[Channel, SourceExecutor] | None = None,
    ) -> None:
        self.database = database
        self.data_root = data_root
        self.acquisitions = AcquisitionService(database, data_root, source_executors)

    def register(self, source: Path) -> RegistrationResult:
        try:
            raw = source.read_bytes()
        except OSError:
            raise FixtureError(FixtureReason.SOURCE_UNAVAILABLE) from None
        declaration = parse_declaration(raw)
        if any(entry.basis == "acquired" for entry in declaration.entries):
            raise FixtureError(FixtureReason.EVIDENCE_REQUIRED, path="entries.basis")
        digest = hashlib.sha256(raw).hexdigest()
        engine = open_database(self.database, mode=DatabaseMode.READ_WRITE)
        try:
            require_current_revision(engine)
            with engine.connect() as connection:
                connection.exec_driver_sql("BEGIN IMMEDIATE")
                records = _load_records(connection)
                existing = (
                    connection.execute(
                        select(fixture_declarations).where(
                            fixture_declarations.c.declaration_key
                            == declaration.declaration_key,
                            fixture_declarations.c.declared_version
                            == declaration.declared_version,
                        )
                    )
                    .mappings()
                    .first()
                )
                if existing is not None:
                    if existing["raw_content"] != raw:
                        raise FixtureError(FixtureReason.DECLARATION_CONFLICT)
                    return RegistrationResult(
                        declaration_id=digest,
                        raw_sha256=digest,
                        entries=tuple(
                            record
                            for record in records
                            if record.declaration_id == digest
                        ),
                    )
                current = {
                    (
                        record.entry.purpose,
                        record.entry.journal,
                        record.entry.key,
                    ): record.record_id
                    for record in records
                    if record.current
                }
                for entry in declaration.entries:
                    logical = entry.purpose, entry.journal, entry.key
                    if entry.replaces != current.get(logical):
                        raise FixtureError(
                            FixtureReason.INVALID_REFERENCE, path="entries.replaces"
                        )
                connection.execute(
                    fixture_declarations.insert().values(
                        declaration_id=digest,
                        declaration_key=declaration.declaration_key,
                        declared_version=declaration.declared_version,
                        format_version=declaration.format_version,
                        raw_sha256=digest,
                        raw_content=raw,
                    )
                )
                for entry in declaration.entries:
                    connection.execute(
                        fixture_records.insert().values(
                            record_id=_record_id(digest, entry),
                            declaration_id=digest,
                            purpose=entry.purpose,
                            journal=entry.journal,
                            sample_key=entry.key,
                            entry_json=entry.model_dump_json(),
                            replaces=entry.replaces,
                        )
                    )
                saved = tuple(
                    record
                    for record in _load_records(connection)
                    if record.declaration_id == digest
                )
                connection.commit()
                return RegistrationResult(
                    declaration_id=digest, raw_sha256=digest, entries=saved
                )
        except SQLAlchemyError as error:
            raise _database_error(error) from None
        finally:
            engine.dispose()

    def list(self, *, history: bool = False) -> tuple[FixtureRecord, ...]:
        engine = open_database(self.database, mode=DatabaseMode.READ_ONLY)
        try:
            require_current_revision(engine)
            with engine.connect() as connection:
                connection.exec_driver_sql("BEGIN")
                records = _load_records(connection)
                samples = {
                    record.record_id: (
                        record.entry.purpose,
                        record.entry.journal,
                        record.entry.key,
                    )
                    for record in records
                }
                states = load_pdf_states(
                    connection,
                    samples,
                    ArtifactStore(self.database, self.data_root or Path(".")),
                    verify_bytes=self.data_root is not None,
                )
                return tuple(
                    record.model_copy(
                        update={
                            "pdf": states.get(
                                (
                                    record.entry.purpose,
                                    record.entry.journal,
                                    record.entry.key,
                                )
                            )
                        }
                    )
                    for record in records
                    if history or record.current
                )
        except SQLAlchemyError as error:
            raise _database_error(error) from None
        finally:
            engine.dispose()

    def show(self, record_id: str) -> FixtureRecord:
        for record in self.list(history=True):
            if record.record_id == record_id:
                return record
        raise FixtureError(FixtureReason.RECORD_NOT_FOUND, path="record_id")

    def read_declaration(self, declaration_id: str) -> bytes:
        engine = open_database(self.database, mode=DatabaseMode.READ_ONLY)
        try:
            require_current_revision(engine)
            with engine.connect() as connection:
                connection.exec_driver_sql("BEGIN")
                _load_records(connection)
                raw = connection.execute(
                    select(fixture_declarations.c.raw_content).where(
                        fixture_declarations.c.declaration_id == declaration_id
                    )
                ).scalar_one_or_none()
                if not isinstance(raw, bytes):
                    raise FixtureError(
                        FixtureReason.RECORD_NOT_FOUND, path="declaration_id"
                    )
                return raw
        except SQLAlchemyError as error:
            raise _database_error(error) from None
        finally:
            engine.dispose()

    def check(self, source: Path) -> DeclarationCheck:
        try:
            raw = source.read_bytes()
        except OSError:
            return DeclarationCheck(status="source_missing", source_available=False)
        declaration = parse_declaration(raw)
        records = FixtureAudit(self.database).list(history=True)
        matches = [
            record
            for record in records
            if record.declaration_key == declaration.declaration_key
            and record.declared_version == declaration.declared_version
        ]
        digest = hashlib.sha256(raw).hexdigest()
        if not matches:
            return DeclarationCheck(
                status="unregistered", source_available=True, raw_sha256=digest
            )
        stored = matches[0]
        return DeclarationCheck(
            status="byte_verified"
            if self.read_declaration(stored.declaration_id) == raw
            else "drift",
            source_available=True,
            declaration_id=stored.declaration_id,
            raw_sha256=digest,
        )

    def create_audit_plan(
        self,
        *,
        contact_email: str | None,
        target_count: int = 5,
        plan_key: str | None = None,
        code_identity: CodeIdentity | None = None,
    ) -> AuditPlan:
        return self.acquisitions.create_audit_plan(
            contact_email=contact_email,
            target_count=target_count,
            plan_key=plan_key,
            code_identity=code_identity,
        )

    def audit_execution(self, plan_id: str) -> AuditProtection:
        return self.acquisitions.audit_execution(plan_id)

    def acquire_source(
        self,
        plan_id: str,
        *,
        request_key: str,
        request: SourceRequest,
        contact_email: str | None,
        protection: AuditProtection | None = None,
    ) -> RouteExecution:
        return self.acquisitions.acquire_source(
            plan_id,
            request_key=request_key,
            request=request,
            contact_email=contact_email,
            protection=protection,
        )

    def list_audits(self) -> tuple[AuditView, ...]:
        return self.acquisitions.list_audits()

    def show_audit(self, plan_id: str) -> AuditView:
        return self.acquisitions.show_audit(plan_id)

    def register_pdf(
        self,
        record_id: str,
        source: Path,
        *,
        request_key: str,
        source_url: str,
        access_basis: str,
        license_basis: str,
        observed_date: str,
        expected_sha256: str | None = None,
        replaces: str | None = None,
        replacement_reason: str | None = None,
    ) -> PdfAcquisition:
        from paper_radar.fixture_audit.pdf_service import register_pdf

        if self.data_root is None:
            raise FixtureError(FixtureReason.EVIDENCE_REQUIRED, path="data_root")
        try:
            request = PdfRegistration.model_validate(
                {
                    "sample_record_id": record_id,
                    "request_key": request_key,
                    "source_url": source_url,
                    "access_basis": access_basis,
                    "license_basis": license_basis,
                    "observed_date": observed_date,
                    "expected_sha256": expected_sha256,
                    "replaces": replaces,
                    "replacement_reason": replacement_reason,
                }
            )
        except (ValidationError, ValueError):
            raise FixtureError(FixtureReason.INVALID_DECLARATION, path="pdf") from None
        records = self.list(history=True)
        samples = {
            record.record_id: (
                record.entry.purpose,
                record.entry.journal,
                record.entry.key,
            )
            for record in records
        }
        try:
            return register_pdf(self.database, self.data_root, source, request, samples)
        except SQLAlchemyError as error:
            raise _database_error(error) from None

    def register_pdf_request(self, request_file: Path, source: Path) -> PdfAcquisition:
        from paper_radar.fixture_audit.pdf_requests import read_pdf_request

        request = read_pdf_request(request_file, PdfRegistration)
        return self.register_pdf(
            request.sample_record_id,
            source,
            request_key=request.request_key,
            source_url=request.source_url,
            access_basis=request.access_basis,
            license_basis=request.license_basis,
            observed_date=request.observed_date,
            expected_sha256=request.expected_sha256,
            replaces=request.replaces,
            replacement_reason=request.replacement_reason,
        )

    def register_pdf_backend(
        self, request: PdfBackendRegistration | Path
    ) -> PdfBackendExpectation:
        from paper_radar.fixture_audit.pdf_requests import read_pdf_request
        from paper_radar.fixture_audit.pdf_service import register_pdf_backend

        if isinstance(request, Path):
            request = read_pdf_request(request, PdfBackendRegistration)
        else:
            try:
                request = PdfBackendRegistration.model_validate(request)
            except (ValidationError, ValueError):
                raise FixtureError(
                    FixtureReason.INVALID_DECLARATION, path="pdf_backend"
                ) from None
        if self.data_root is None:
            raise FixtureError(FixtureReason.EVIDENCE_REQUIRED, path="data_root")
        records = self.list(history=True)
        samples = {
            record.record_id: (
                record.entry.purpose,
                record.entry.journal,
                record.entry.key,
            )
            for record in records
        }
        try:
            return register_pdf_backend(self.database, self.data_root, request, samples)
        except SQLAlchemyError as error:
            raise _database_error(error) from None

    def check_pdf(self, record_id: str) -> PdfEvidenceCheck:
        if self.data_root is None:
            raise FixtureError(FixtureReason.EVIDENCE_REQUIRED, path="data_root")
        record = self.show(record_id)
        if record.entry.purpose != "pdf":
            raise FixtureError(
                FixtureReason.INVALID_REFERENCE, path="pdf.sample_record_id"
            )
        state = record.pdf
        return PdfEvidenceCheck(
            status="byte_verified" if state is not None else "not_registered",
            current_pdf_id=state.current_pdf_id if state is not None else None,
            acquisition_count=len(state.acquisitions) if state is not None else 0,
            backend_expectation_count=sum(
                len(item.backend_expectations) for item in state.acquisitions
            )
            if state is not None
            else 0,
        )

    def validate_all(self) -> None:
        records = self.list(history=True)
        if self.data_root is None and any(record.pdf is not None for record in records):
            raise FixtureError(FixtureReason.EVIDENCE_REQUIRED, path="data_root")
        self.acquisitions.validate_all()
