"""A10 的无浏览器依赖边界;真实通道替换另由公共取得测试证明。"""

import ast
import hashlib
import importlib
import json
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
    # #150 允许独立 CPU extra;基础六包仍固定完整记录,不能借接入降级或换源。
    lock = tomllib.loads((ROOT / "uv.lock").read_text())
    packages = {package["name"]: package for package in lock["package"]}
    # 人工预期来自 #150 实施起点的六包,不从当前锁或供给实现生成。
    expected_records = {
        "alembic": "5abc68e8451aa8c88ad3a64c1fc3e3a7c5f8b41a33fd0e11533c9dbb399e7a67",
        "httpx": "aed038606fc110b72f6f30c4d2a89c3f2ea50e429d4c57d35031f6ff6d02fe45",
        "pydantic": "62f9b9899f3afc2f46a3906ba118ed581628fba8995b1c8167dc1e62c3445d72",
        "pyyaml": "bd40d52150cc233d79b3d47cae3d8aff81420ee3d63b61974f057e5dabd043a7",
        "sqlalchemy": (
            "63b4faa1bc537ea5399f0c8b935ba8a683fdfd9ca90fd09ac55f5d3518942ffe"
        ),
        "typer": "df034efc2db07f327802d1f9cf3f7ca2ceb1cc9e0c8fa34aada858e1ad49c278",
    }
    for name, expected_record in expected_records.items():
        record = json.dumps(packages[name], sort_keys=True, separators=(",", ":"))
        assert hashlib.sha256(record.encode()).hexdigest() == expected_record, name
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert set(project["project"]["optional-dependencies"]) == {"docling"}
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
