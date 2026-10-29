"""组合登记前置引用与任务原子冻结。"""

from alembic import op

revision = "feed05_composition"
down_revision = "feed04_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE feed_value_registrations (
        request_key VARCHAR(64) PRIMARY KEY NOT NULL,
        receipt_id VARCHAR(64) NOT NULL REFERENCES screening_requests(receipt_id),
        basis_json TEXT NOT NULL,
        basis_sha256 VARCHAR(64) NOT NULL
    )""")


def downgrade() -> None:
    op.drop_table("feed_value_registrations")
