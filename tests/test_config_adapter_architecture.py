"""Pi 的纯配置不依赖执行环境、存储层或 CLI。"""

from pathlib import Path

from tests.config_test_support import imported_modules


def test_adapter_schema_and_semantics_have_no_io_or_executor_dependencies() -> None:
    path = Path(__file__).resolve().parents[1] / "src/paper_radar/config/adapters.py"
    imports = imported_modules(path)
    assert not imports & {
        "yaml",
        "sqlite3",
        "sqlalchemy",
        "alembic",
        "typer",
        "subprocess",
    }
    assert not any(
        name.startswith(("paper_radar.storage", "paper_radar.cli", "paper_radar.llm"))
        for name in imports
    )
