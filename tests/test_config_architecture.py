"""A2-01 的方向约束。保留 A1 固定哈希测试。"""

from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1] / "src/paper_radar"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
    } | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }


def test_pure_compiler_does_not_import_io_or_frameworks() -> None:
    for module in ("compile.py", "identity.py", "schema.py"):
        imported = _imports(_ROOT / "config" / module)
        assert not imported & {
            "yaml",
            "sqlite3",
            "sqlalchemy",
            "alembic",
            "typer",
        }


def test_existing_contracts_and_screening_do_not_depend_on_config_storage() -> None:
    for folder in ("contracts", "screening"):
        for file in (_ROOT / folder).glob("*.py"):
            imported = _imports(file)
            assert not any(
                name.startswith(("paper_radar.config", "paper_radar.storage"))
                for name in imported
            )


def test_storage_does_not_import_config() -> None:
    for file in (_ROOT / "storage").rglob("*.py"):
        assert not any(name.startswith("paper_radar.config") for name in _imports(file))
