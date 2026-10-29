"""生产语言依据必存标识;保留真正历史显式bool预算。"""

from alembic import op

revision = "feed06_language_provenance"
down_revision = "feed05_composition"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE screening_language_requirements (
        budget_id VARCHAR(36) PRIMARY KEY NOT NULL
            REFERENCES screening_budgets(budget_id)
    )""")
    op.execute("""INSERT INTO screening_language_requirements (budget_id)
        SELECT budget_id FROM screening_language_basis
    """)


def downgrade() -> None:
    op.drop_table("screening_language_requirements")
