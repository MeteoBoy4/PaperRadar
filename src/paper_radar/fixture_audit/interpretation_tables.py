"""显式解析器声明及安全解释的追加链。"""

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

parser_declarations = Table(
    "audit_parser_declarations",
    metadata,
    Column("declaration_id", String(64), primary_key=True),
    Column("parser_version", String(128), nullable=False, unique=True),
    Column("content_json", Text, nullable=False),
)
interpretations = Table(
    "audit_interpretations",
    metadata,
    Column("event_no", Integer, primary_key=True, autoincrement=True),
    Column("interpretation_id", String(64), nullable=False, unique=True),
    Column("plan_id", String(64), ForeignKey("audit_plans.plan_id"), nullable=False),
    Column("request_key", String(128), nullable=False),
    Column(
        "parser_declaration_id",
        String(64),
        ForeignKey("audit_parser_declarations.declaration_id"),
        nullable=False,
    ),
    Column(
        "previous_interpretation_id",
        String(64),
        ForeignKey("audit_interpretations.interpretation_id"),
        unique=True,
    ),
    Column("content_json", Text, nullable=False),
    UniqueConstraint("plan_id", "request_key"),
)
