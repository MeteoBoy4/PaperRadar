"""Read 受控算法配置的依赖方向。"""

from pathlib import Path

from tests.config_test_support import imported_modules


def test_read_configuration_remains_in_the_pure_configuration_layer() -> None:
    path = Path(__file__).resolve().parents[1] / "src/paper_radar/config/read.py"
    imported = imported_modules(path)
    assert not imported & {"yaml", "sqlalchemy", "alembic", "sqlite3", "typer"}
    assert not any(
        name.startswith(("paper_radar.storage", "paper_radar.cli")) for name in imported
    )
