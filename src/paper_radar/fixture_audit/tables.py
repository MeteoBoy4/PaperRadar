"""Fixture 登记的实际持久化事实;后续审计不借用论文表。"""

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Table,
    Text,
    UniqueConstraint,
)

from paper_radar.storage.schema import metadata

fixture_declarations = Table(
    "fixture_declarations",
    metadata,
    Column("declaration_id", String(64), primary_key=True),
    Column("declaration_key", String(128), nullable=False),
    Column("declared_version", String(64), nullable=False),
    Column("format_version", Integer, nullable=False),
    Column("raw_sha256", String(64), nullable=False),
    Column("raw_content", LargeBinary, nullable=False),
    UniqueConstraint("declaration_key", "declared_version"),
    CheckConstraint("format_version = 1"),
    CheckConstraint(
        "length(declaration_id)=64 AND declaration_id NOT GLOB '*[^0-9a-f]*'"
    ),
    CheckConstraint("length(raw_sha256)=64 AND raw_sha256 NOT GLOB '*[^0-9a-f]*'"),
)
fixture_records = Table(
    "fixture_records",
    metadata,
    Column("event_no", Integer, primary_key=True, autoincrement=True),
    Column("record_id", String(64), nullable=False, unique=True),
    Column(
        "declaration_id",
        String(64),
        ForeignKey("fixture_declarations.declaration_id"),
        nullable=False,
    ),
    Column("purpose", String(32), nullable=False),
    Column("journal", String(16), nullable=False),
    Column("sample_key", String(128), nullable=False),
    Column("entry_json", Text, nullable=False),
    Column(
        "replaces", String(64), ForeignKey("fixture_records.record_id"), unique=True
    ),
    UniqueConstraint("declaration_id", "purpose", "journal", "sample_key"),
    CheckConstraint("purpose IN ('feed','abstract_audit','references','pdf')"),
    CheckConstraint("journal IN ('aies','jgr','qjrms','dqkx')"),
    CheckConstraint("length(record_id)=64 AND record_id NOT GLOB '*[^0-9a-f]*'"),
)
