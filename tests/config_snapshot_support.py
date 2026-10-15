"""快照索引异常/碰撞的固定 fixture。仅用于 #27 查询边界验收。"""

import sqlite3
from pathlib import Path


def insert_index_records(database: Path, rows: list[tuple[str, str]]) -> None:
    """固定索引碰撞 fixture。不伪造可通过 load 的快照。"""
    with sqlite3.connect(database) as connection:
        connection.executemany(
            "INSERT INTO runtime_config_snapshots VALUES (?, '{}', ?)", rows
        )


def checkpoint(database: Path) -> None:
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")


def database_damage(database: Path, damage: str) -> None:
    with sqlite3.connect(database) as connection:
        if damage == "uninitialized":
            connection.execute("DROP TABLE alembic_version")
        elif damage == "missing_revision":
            connection.execute("DELETE FROM alembic_version")
        elif damage in ("old_revision", "future_revision"):
            revision = "old" if damage == "old_revision" else "PRIVATE_REVISION_MARKER"
            connection.execute(
                "UPDATE alembic_version SET version_num = ?", (revision,)
            )
        elif damage == "missing_table":
            connection.execute("DROP TABLE runtime_config_snapshots")
        else:
            raise ValueError("未知测试损坏类型")
    checkpoint(database)
