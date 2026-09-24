"""公共配置服务。"""

from pathlib import Path

from paper_radar.config.compile import RuntimeConfigSnapshot, StageReadiness
from paper_radar.config.errors import ConfigError


def check_config(settings_path: Path, database: Path) -> RuntimeConfigSnapshot:
    from paper_radar.config.service import check_config as run

    return run(settings_path, database)


def compile_config(settings_path: Path, database: Path) -> RuntimeConfigSnapshot:
    from paper_radar.config.service import compile_config as run

    return run(settings_path, database)


def load_config_snapshot(database: Path, snapshot_id: str) -> RuntimeConfigSnapshot:
    from paper_radar.config.service import load_config_snapshot as run

    return run(database, snapshot_id)


def upgrade_database(path: Path) -> str:
    from paper_radar.storage.database import upgrade_database as run
    from paper_radar.storage.errors import StorageError

    try:
        return run(path)
    except StorageError as error:
        raise ConfigError(str(error)) from None


__all__ = [
    "ConfigError",
    "RuntimeConfigSnapshot",
    "StageReadiness",
    "check_config",
    "compile_config",
    "load_config_snapshot",
    "upgrade_database",
]
