"""纯备份清单规则不反向依赖 I/O 或业务组合。"""

from pathlib import Path

from tests.config_test_support import imported_modules


def test_backup_manifest_remains_independent_from_database_cli_and_network() -> None:
    path = Path(__file__).resolve().parents[1] / "src/paper_radar/backup/manifest.py"
    imports = imported_modules(path)
    forbidden = (
        "sqlite3",
        "sqlalchemy",
        "typer",
        "socket",
        "httpx",
        "paper_radar.config",
        "paper_radar.backup.service",
    )
    assert not {name for name in imports if name.startswith(forbidden)}
