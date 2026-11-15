"""Body 前置事实只读查询;调用者提供一致 Connection。"""

from sqlalchemy import Connection, select
from sqlalchemy.engine import RowMapping

from paper_radar.body import tables
from paper_radar.body.models import (
    BodyError,
    CurrentBody,
    DecisionEvent,
    DecisionMetadata,
    SampleAdmission,
)
from paper_radar.body.query_records import (
    current_pdf as current_pdf,
)
from paper_radar.body.query_records import (
    pdf_record as pdf_record,
)
from paper_radar.body.query_records import (
    root_fact as root_fact,
)
from paper_radar.eligibility import DecisionFact
from paper_radar.papers.queries import load_trace
from paper_radar.screening.reasons import (
    ScreeningReasonInput,
    ScreeningSource,
    build_screening_reason,
)


def sample_record(row: RowMapping) -> SampleAdmission:
    return SampleAdmission(
        **{key: row[key] for key in SampleAdmission.__dataclass_fields__}
    )


def decision_metadata(
    connection: Connection, paper_id: str
) -> tuple[DecisionMetadata, ...]:
    """只投影 Body 元数据;调用者的事务决定可见范围,不解释上层关联。"""
    result = []
    try:
        for row in connection.execute(
            select(
                tables.decisions.c.decision_id,
                tables.decisions.c.sequence,
                tables.decisions.c.record_json,
            )
            .where(tables.decisions.c.paper_id == paper_id)
            .order_by(tables.decisions.c.sequence)
        ).mappings():
            record = ScreeningReasonInput.model_validate_json(row["record_json"])
            build_screening_reason(record)
            if record.source is not ScreeningSource.DIRECT_MANUAL_DECISION or (
                type(row["sequence"]) is not int or row["sequence"] <= 0
            ):
                raise ValueError
            result.append(
                DecisionMetadata(row["decision_id"], row["sequence"], record.result)
            )
        if len({r.sequence for r in result}) != len(result):
            raise ValueError
        return tuple(result)
    except (ValueError, TypeError, KeyError):
        raise BodyError("corrupt_reference") from None


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
    """有效显式选择优先;否则保留唯一成功规则。"""
    from paper_radar.body.extraction import extraction_view
    from paper_radar.body.selection import current_selection

    trace = load_trace(connection, paper_id)
    pdf = current_pdf(connection, paper_id, trace.current.version_id)
    if pdf is None:
        return CurrentBody(None, "pdf_absent")
    selected = current_selection(connection, paper_id)
    if selected is not None:
        return CurrentBody(selected.identity)
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
