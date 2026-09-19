from __future__ import annotations

import ast
from importlib.util import resolve_name
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


def _module_name(path: Path, source_root: Path) -> str:
    parts = list(path.relative_to(source_root).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _imports_in(path: Path, source_root: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    module_name = _module_name(path, source_root)
    package_name = (
        module_name if path.name == "__init__.py" else module_name.rpartition(".")[0]
    )
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                relative_name = "." * node.level + (node.module or "")
                imported_from = resolve_name(relative_name, package_name)
            else:
                imported_from = node.module or ""
            if imported_from:
                imports.add(imported_from)
                imports.update(
                    f"{imported_from}.{alias.name}"
                    for alias in node.names
                    if alias.name != "*"
                )
    return imports


def _forbidden_imports(screening_root: Path, source_root: Path) -> list[str]:
    violations: list[str] = []
    for path in sorted(screening_root.rglob("*.py")):
        for imported_module in sorted(_imports_in(path, source_root)):
            if any(
                imported_module == prefix or imported_module.startswith(f"{prefix}.")
                for prefix in FORBIDDEN_IMPORT_PREFIXES
            ):
                relative_path = path.relative_to(screening_root)
                violations.append(f"{relative_path}: {imported_module}")
    return violations


def test_import_boundary_scanner_catches_nested_relative_imports(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "src"
    screening_root = source_root / "paper_radar" / "screening"
    nested_module = screening_root / "nested" / "rules.py"
    nested_module.parent.mkdir(parents=True)
    nested_module.write_text(
        "from ... import cli\nfrom ...storage import repositories\n",
        encoding="utf-8",
    )

    assert _forbidden_imports(screening_root, source_root) == [
        "nested/rules.py: paper_radar.cli",
        "nested/rules.py: paper_radar.storage",
        "nested/rules.py: paper_radar.storage.repositories",
    ]


def test_screening_contract_layer_has_no_external_or_upward_dependencies() -> None:
    source_root = Path(__file__).parents[1] / "src"
    screening_root = source_root / "paper_radar" / "screening"

    assert _forbidden_imports(screening_root, source_root) == []
