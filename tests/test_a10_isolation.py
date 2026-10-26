"""A10 的无浏览器依赖边界;真实通道替换另由公共取得测试证明。"""

import ast
import hashlib
import importlib
import tomllib
from pathlib import Path

import pytest

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


@pytest.mark.parametrize(
    "arguments",
    [
        ["--help"],
        ["fixture", "--help"],
        ["fixture", "register", "--help"],
        ["audit", "--help"],
        ["audit", "run", "--help"],
        ["audit", "resume", "--help"],
        ["audit", "replay", "--help"],
    ],
)
def test_root_fixture_and_audit_help_remain_local_without_business_io(
    tmp_path: Path, arguments: list[str]
) -> None:
    import os
    import subprocess
    import sys

    executed = subprocess.run(
        [str(Path(sys.executable).parent / "paper-radar"), *arguments],
        cwd=tmp_path,
        env={
            "PATH": os.environ["PATH"],
            "PYTHONPATH": str(ROOT / "tests/deny_external_io"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONIOENCODING": "utf-8",
        },
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert executed.returncode == 0, executed.stderr
    assert "示例" in executed.stdout
    assert executed.stderr == ""
    assert list(tmp_path.iterdir()) == []
