"""正文提取纯配置不得依赖 YAML、SQLite、CLI 或解析器 SDK。"""

from pathlib import Path

from tests.config_test_support import imported_modules


def test_extraction_configuration_has_no_io_or_parser_dependencies() -> None:
    folder = Path(__file__).resolve().parents[1] / "src/paper_radar/config"
    for path in folder.glob("extraction*.py"):
        imports = imported_modules(path)
        assert not imports & {"yaml", "sqlite3", "sqlalchemy", "alembic", "typer"}
        assert not any(
            name.startswith(("docling", "paper_radar.storage")) for name in imports
        )
