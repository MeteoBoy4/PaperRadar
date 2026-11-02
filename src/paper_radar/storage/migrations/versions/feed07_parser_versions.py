"""冻结生产 Feed 检查的解析器版本;既有检查保持 v1 身份。"""

import sqlalchemy as sa
from alembic import op

revision = "feed07_parser_versions"
down_revision = "feed06_language_provenance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "feed_production_checks",
        sa.Column("parser_version", sa.Integer, nullable=False, server_default="1"),
    )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.exec_driver_sql(
        "SELECT 1 FROM feed_production_checks WHERE parser_version != 1 LIMIT 1"
    ).first():
        raise RuntimeError("不能降级含新版本解析检查的数据库")
    op.drop_column("feed_production_checks", "parser_version")
