from __future__ import annotations

import ast
from pathlib import Path

FORBIDDEN_IMPORT_PREFIXES = (
    "aiohttp",
    "alembic",
    "anthropic",
    "docling",
    "google.generativeai",
    "http",
    "httpx",
    "openai",
    "paper_radar.cli",
    "paper_radar.fulltext",
    "paper_radar.sources",
    "paper_radar.storage",
    "pydantic_ai",
    "requests",
    "socket",
    "sqlalchemy",
    "sqlite3",
    "sqlmodel",
    "typer",
    "urllib",
)


def _imports_in(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module)
    return imports


def test_screening_contract_layer_has_no_external_or_upward_dependencies() -> None:
    screening_root = Path(__file__).parents[1] / "src" / "paper_radar" / "screening"
    violations: list[str] = []

    for path in sorted(screening_root.glob("*.py")):
        for imported_module in sorted(_imports_in(path)):
            if any(
                imported_module == prefix or imported_module.startswith(f"{prefix}.")
                for prefix in FORBIDDEN_IMPORT_PREFIXES
            ):
                violations.append(f"{path.name}: {imported_module}")

    assert violations == []
