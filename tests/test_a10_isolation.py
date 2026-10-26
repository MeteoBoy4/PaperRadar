"""A10 的无浏览器依赖边界;真实通道替换另由公共取得测试证明。"""

import ast
import hashlib
import importlib
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_product_imports_do_not_require_browser_automation() -> None:
    forbidden = {"playwright", "selenium"}
    found: list[str] = []
    for path in sorted((ROOT / "src/paper_radar").rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_bytes())):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            found.extend(name for name in names if name.split(".")[0] in forbidden)
    assert found == []


def test_lockfile_and_existing_dependency_semantics_remain_fixed() -> None:
    assert hashlib.sha256((ROOT / "uv.lock").read_bytes()).hexdigest() == (
        "11aa458753aad1447061e7b8e5ef3adc74e53db4db98ecd36da5d88e14267512"
    )
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert "optional-dependencies" not in project["project"]
    assert set(project["dependency-groups"]) == {"dev"}
    assert project["project"]["dependencies"] == [
        "alembic>=1.17,<2",
        "httpx>=0.28,<1",
        "pydantic>=2.12,<3",
        "pyyaml>=6.0,<7",
        "sqlalchemy>=2.0,<3",
        "typer>=0.19,<1",
    ]
    base = ("alembic", "SQLAlchemy", "PyYAML")
    for scope in ("a2", "a2_full", "a3", "a4", "a5", "a6", "a7", "a8", "a9"):
        expected: tuple[str, ...] = base
        if scope not in ("a2", "a2_full"):
            expected += ("pydantic",)
        if scope in ("a3", "a4"):
            expected += ("typer",)
        if scope == "a4":
            expected += ("httpx",)
        assert (
            expected
            == importlib.import_module(f"scripts.{scope}_scope").REQUIRED_DEPENDENCIES
        )
