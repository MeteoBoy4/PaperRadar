"""SQLite 连接和显式 Alembic 升级。"""

from __future__ import annotations

import sqlite3
from enum import StrEnum
from pathlib import Path
from urllib.parse import quote

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine, event, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool

from paper_radar.storage.errors import StorageError

_MIGRATIONS = Path(__file__).parent / "migrations"


class DatabaseMode(StrEnum):
    READ_ONLY = "ro"
    READ_WRITE = "rw"
    CREATE = "rwc"


def _migration_config() -> Config:
    config = Config()
    config.set_main_option("script_location", str(_MIGRATIONS))
    return config


def current_revision() -> str:
    """从随包发布的迁移脚本读取唯一 head。"""
    try:
        head = ScriptDirectory.from_config(_migration_config()).get_current_head()
    except Exception:
        raise StorageError("迁移脚本无法读取或存在多个 head；请检查安装包") from None
    if head is None:
        raise StorageError("迁移脚本没有 head；请检查安装包")
    return head


def open_database(path: Path, *, mode: DatabaseMode) -> Engine:
    """只有显式 upgrade 可以使用 CREATE 模式。"""
    if mode is not DatabaseMode.CREATE and not path.is_file():
        raise StorageError("数据库不存在；请先运行 paper-radar db upgrade --database")
    absolute = path.resolve()

    def connect() -> sqlite3.Connection:
        uri = f"file:{quote(str(absolute))}?mode={mode.value}"
        connection = sqlite3.connect(uri, uri=True, timeout=5)
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    engine = create_engine("sqlite://", creator=connect, poolclass=NullPool)

    @event.listens_for(engine, "connect")
    def _verify_fk(dbapi_connection: sqlite3.Connection, _: object) -> None:
        if dbapi_connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise StorageError("数据库外键校验未启用")

    return engine


def _revision(engine: Engine) -> str | None:
    try:
        if not inspect(engine).has_table("alembic_version"):
            return None
        with engine.connect() as connection:
            rows = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).all()
    except (sqlite3.Error, OSError, SQLAlchemyError):
        raise StorageError("数据库无法读取；请检查路径和权限") from None
    if len(rows) != 1:
        raise StorageError("数据库 revision 缺失或损坏；请检查数据库")
    return str(rows[0][0])


def require_current_revision(engine: Engine) -> None:
    revision = _revision(engine)
    if revision is None:
        raise StorageError("数据库未初始化；请先运行 paper-radar db upgrade --database")
    if revision != current_revision():
        raise StorageError("数据库 revision 未知或较新；请使用匹配版本的程序检查数据库")


def upgrade_database(path: Path) -> str:
    """唯一可创建数据库的入口。WAL 也仅在此入口设置。"""
    engine = open_database(path, mode=DatabaseMode.CREATE)
    try:
        head = current_revision()
        revision = _revision(engine)
        if revision is not None and revision != head:
            raise StorageError(
                "数据库 revision 未知或较新；拒绝升级，请使用匹配版本的程序"
            )
        config = _migration_config()
        with engine.connect() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            connection.commit()
        with engine.connect() as connection:
            mode = connection.exec_driver_sql("PRAGMA journal_mode=WAL").scalar()
            if mode != "wal":
                raise StorageError("数据库无法启用 WAL；请检查存储介质和权限")
        return head
    except StorageError:
        raise
    except Exception:
        raise StorageError("数据库升级失败；请检查数据库状态和迁移脚本") from None
    finally:
        engine.dispose()
