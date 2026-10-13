"""期刊配置契约保持纯配置边界。复用既有依赖方向检查。"""

from pathlib import Path

from tests.config_test_support import imported_modules


def test_journals_configuration_has_no_io_or_execution_dependencies() -> None:
    path = Path(__file__).resolve().parents[1] / "src/paper_radar/config/journals.py"
    imported = imported_modules(path)
    assert not imported & {"yaml", "sqlalchemy", "alembic", "sqlite3", "typer"}
    assert not any(
        name.startswith(("paper_radar.storage", "paper_radar.cli")) for name in imported
    )
