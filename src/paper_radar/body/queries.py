"""Body 前置事实只读查询;调用者提供一致 Connection。"""

from sqlalchemy import Connection, select
from sqlalchemy.engine import RowMapping

from paper_radar.body import tables
from paper_radar.body.models import (
    BodyError,
    CurrentBody,
    DecisionEvent,
    PdfAttachment,
    RootRegistration,
    SampleAdmission,
)
from paper_radar.body.repository import digest
from paper_radar.eligibility import DecisionFact, RootPurpose
from paper_radar.papers.queries import load_trace
from paper_radar.screening.reasons import (
    ScreeningReasonInput,
    ScreeningSource,
    build_screening_reason,
)


def pdf_record(row: RowMapping) -> PdfAttachment:
    return PdfAttachment(
        **{key: row[key] for key in PdfAttachment.__dataclass_fields__}
    )


def sample_record(row: RowMapping) -> SampleAdmission:
    return SampleAdmission(
        **{key: row[key] for key in SampleAdmission.__dataclass_fields__}
    )


def root_fact(connection: Connection) -> RootRegistration:
    rows = connection.execute(select(tables.roots)).mappings().all()
    if len(rows) != 1 or rows[0]["singleton"] != 1:
        return RootRegistration()
    row = rows[0]
    try:
        if row["registration_hash"] != digest(
            [row["root_id"], row["purpose"], row["registered_at"]]
        ):
            return RootRegistration()
        return RootRegistration(
            row["root_id"], RootPurpose(row["purpose"]), row["registered_at"]
        )
    except ValueError:
        return RootRegistration()


def current_pdf(
    connection: Connection, paper_id: str, version_id: str
) -> PdfAttachment | None:
    row = (
        connection.execute(
            select(tables.pdfs)
            .where(
                tables.pdfs.c.paper_id == paper_id,
                tables.pdfs.c.version_id == version_id,
            )
            .order_by(tables.pdfs.c.sequence.desc())
        )
        .mappings()
        .first()
    )
    return pdf_record(row) if row is not None else None


def decision_events(connection: Connection, paper_id: str) -> tuple[DecisionEvent, ...]:
    trace = load_trace(connection, paper_id)
    result = []
    for row in connection.execute(
        select(tables.decisions)
        .where(tables.decisions.c.paper_id == paper_id)
        .order_by(tables.decisions.c.sequence)
    ).mappings():
        record = ScreeningReasonInput.model_validate_json(row["record_json"])
        build_screening_reason(record)
        if record.source is not ScreeningSource.DIRECT_MANUAL_DECISION:
            raise BodyError("corrupt_reference")
        refs = tuple(
            connection.execute(
                select(tables.decision_screenings.c.success_id)
                .where(tables.decision_screenings.c.decision_id == row["decision_id"])
                .order_by(tables.decision_screenings.c.success_id)
            ).scalars()
        )
        fact = DecisionFact(
            row["decision_id"],
            paper_id,
            row["sequence"],
            record,
            "current"
            if (row["version_id"], row["revision_no"])
            == (trace.current.version_id, trace.current.revision_no)
            else "historical",
            refs[0] if refs else None,
        )
        result.append(
            DecisionEvent(
                fact,
                row["version_id"],
                row["revision_no"],
                refs,
                row["actor"],
                row["decided_at"],
            )
        )
    if len({item.fact.sequence for item in result}) != len(result):
        raise BodyError("corrupt_reference")
    return tuple(result)


def current_body(connection: Connection, paper_id: str) -> CurrentBody:
    """只使用当前版本、显式 PDF 选择及唯一成功提取事实。"""
    from paper_radar.body.extraction import extraction_view

    trace = load_trace(connection, paper_id)
    pdf = current_pdf(connection, paper_id, trace.current.version_id)
    if pdf is None:
        return CurrentBody(None, "pdf_absent")
    keys = (
        connection.execute(
            select(tables.successes.c.fingerprint)
            .select_from(
                tables.successes.join(
                    tables.inputs,
                    tables.successes.c.fingerprint == tables.inputs.c.fingerprint,
                )
            )
            .where(tables.inputs.c.pdf_sha256 == pdf.pdf_sha256)
        )
        .scalars()
        .all()
    )
    if not keys:
        return CurrentBody(None, "extraction_absent")
    if len(keys) != 1:
        return CurrentBody(None, "ambiguous_extractions")
    extraction = extraction_view(connection, keys[0])
    if extraction is None or extraction.identity is None:
        raise BodyError("corrupt_reference")
    return CurrentBody(extraction.identity)
