"""根与 PDF 的轻量事实读取;不依赖正文选择或查询编排。"""

from sqlalchemy import Connection, select
from sqlalchemy.engine import RowMapping

from paper_radar.body import tables
from paper_radar.body.models import PdfAttachment, RootRegistration
from paper_radar.body.repository import digest
from paper_radar.eligibility import RootPurpose


def pdf_record(row: RowMapping) -> PdfAttachment:
    return PdfAttachment(
        **{key: row[key] for key in PdfAttachment.__dataclass_fields__}
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
