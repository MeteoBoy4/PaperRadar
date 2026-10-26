"""PDF 取得历史,与声明登记分开保存。"""

from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)

from paper_radar.storage.schema import metadata

fixture_pdf_acquisitions = Table(
    "fixture_pdf_acquisitions",
    metadata,
    Column("event_no", Integer, primary_key=True, autoincrement=True),
    Column("pdf_id", String(64), nullable=False, unique=True),
    Column(
        "sample_record_id",
        String(64),
        ForeignKey("fixture_records.record_id"),
        nullable=False,
    ),
    Column("request_key", String(128), nullable=False),
    Column(
        "artifact_id", String(64), ForeignKey("artifacts.artifact_id"), nullable=False
    ),
    Column("content_json", Text, nullable=False),
    Column(
        "replaces",
        String(64),
        ForeignKey("fixture_pdf_acquisitions.pdf_id"),
        unique=True,
    ),
    UniqueConstraint("sample_record_id", "request_key"),
)

fixture_pdf_expectations = Table(
    "fixture_pdf_expectations",
    metadata,
    Column("event_no", Integer, primary_key=True, autoincrement=True),
    Column("expectation_id", String(64), nullable=False, unique=True),
    Column(
        "pdf_id",
        String(64),
        ForeignKey("fixture_pdf_acquisitions.pdf_id"),
        nullable=False,
    ),
    Column("request_key", String(128), nullable=False),
    Column("backend_identity", String(64), nullable=False),
    Column("content_json", Text, nullable=False),
    UniqueConstraint("pdf_id", "request_key"),
    UniqueConstraint("pdf_id", "backend_identity"),
)
