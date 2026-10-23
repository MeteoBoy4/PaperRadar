"""显式 retry 的唯一父链及来源;全程保持外键开启。"""

from alembic import op

revision = "a704_screening_retry"
down_revision = "a703_screening_success"
branch_labels = None
depends_on = None

# requests → successes → attempts → requests 构成真实可空 FK 环。
# 先保存闭包,断开缓存引用,清空后重建;全部操作由升级入口的单个事务保护。
_TABLES = (
    "screening_requests",
    "screening_attempts",
    "screening_leases",
    "screening_failures",
    "screening_successes",
)


def upgrade() -> None:
    connection = op.get_bind()
    if connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() != 1:
        raise RuntimeError("foreign keys must remain enabled")
    ddl = {
        name: connection.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).scalar_one()
        for name in _TABLES
    }
    indexes = (
        connection.exec_driver_sql(
            "SELECT sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL "
            "AND tbl_name IN ('screening_requests','screening_attempts',"
            "'screening_leases','screening_failures','screening_successes')"
        )
        .scalars()
        .all()
    )
    for name in _TABLES:
        connection.exec_driver_sql(
            f"CREATE TEMP TABLE saved_{name} AS SELECT * FROM {name}"
        )
    connection.exec_driver_sql("UPDATE screening_requests SET cached_success_id=NULL")
    for name in reversed(_TABLES):
        connection.exec_driver_sql(f"DELETE FROM {name}")
    for name in reversed(_TABLES):
        connection.exec_driver_sql(f"DROP TABLE {name}")
    ddl["screening_requests"] = (
        ddl["screening_requests"]
        .replace(
            "source IN ('scheduled','manual')",
            "source IN ('scheduled','manual','retry')",
        )
        .replace("source='manual'", "source IN ('manual','retry')")
    )
    for name in _TABLES:
        connection.exec_driver_sql(ddl[name])
    for sql in indexes:
        connection.exec_driver_sql(sql)
    for name in _TABLES:
        columns = [
            row[1] for row in connection.exec_driver_sql(f"PRAGMA table_info({name})")
        ]
        projection = ",".join(
            "NULL" if c == "cached_success_id" else c for c in columns
        )
        connection.exec_driver_sql(
            f"INSERT INTO {name} SELECT {projection} FROM saved_{name}"
        )
    connection.exec_driver_sql(
        "UPDATE screening_requests SET cached_success_id=(SELECT cached_success_id "
        "FROM saved_screening_requests saved "
        "WHERE saved.receipt_id=screening_requests.receipt_id)"
    )
    for name in _TABLES:
        connection.exec_driver_sql(f"DROP TABLE saved_{name}")
    connection.exec_driver_sql(
        "ALTER TABLE screening_tasks ADD COLUMN parent_task_id VARCHAR(36) "
        "REFERENCES screening_tasks(task_id)"
    )
    connection.exec_driver_sql(
        "CREATE UNIQUE INDEX uq_screening_parent ON screening_tasks(parent_task_id)"
    )
    if connection.exec_driver_sql("PRAGMA foreign_key_check").first() is not None:
        raise RuntimeError("foreign key violation")
