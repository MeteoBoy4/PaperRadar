"""SQLite 连接和显式 Alembic 升级。"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from urllib.parse import quote

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool

from paper_radar.config.errors import ConfigError

REVISION = "a201_profile_snapshot"
_MIGRATIONS = Path(__file__).parent / "migrations"


def open_database(path: Path, *, mode: str) -> Engine:
    """mode 为 ro/rw/rwc。只有 upgrade 可以使用 rwc。"""
    if mode != "rwc" and not path.is_file():
        raise ConfigError("数据库不存在；请先运行 paper-radar db upgrade --database")
    absolute = path.resolve()

    def connect() -> sqlite3.Connection:
        uri = f"file:{quote(str(absolute))}?mode={mode}"
        connection = sqlite3.connect(uri, uri=True, timeout=5)
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    engine = create_engine("sqlite://", creator=connect, poolclass=NullPool)

    @event.listens_for(engine, "connect")
    def _verify_fk(dbapi_connection: sqlite3.Connection, _: object) -> None:
        if dbapi_connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise ConfigError("数据库外键校验未启用")

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
        raise ConfigError("数据库无法读取；请检查路径和权限") from None
    if len(rows) != 1:
        raise ConfigError("数据库 revision 缺失或损坏；请检查数据库")
    return str(rows[0][0])


def require_current_revision(engine: Engine) -> None:
    revision = _revision(engine)
    if revision is None:
        raise ConfigError("数据库未初始化；请先运行 paper-radar db upgrade --database")
    if revision != REVISION:
        raise ConfigError("数据库 revision 未知或较新；请使用匹配版本的程序检查数据库")


def upgrade_database(path: Path) -> str:
    """唯一可创建数据库的入口。WAL 也仅在此入口设置。"""
    engine = open_database(path, mode="rwc")
    try:
        revision = _revision(engine)
        if revision is not None and revision != REVISION:
            raise ConfigError(
                "数据库 revision 未知或较新；拒绝升级，请使用匹配版本的程序"
            )
        config = Config()
        config.set_main_option("script_location", str(_MIGRATIONS))
        with engine.connect() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            connection.commit()
        with engine.connect() as connection:
            mode = connection.exec_driver_sql("PRAGMA journal_mode=WAL").scalar()
            if mode != "wal":
                raise ConfigError("数据库无法启用 WAL；请检查存储介质和权限")
        return REVISION
    except ConfigError:
        raise
    except Exception:
        raise ConfigError("数据库升级失败；请检查路径和权限") from None
    finally:
        engine.dispose()
