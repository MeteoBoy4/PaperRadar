"""纯规则边界守卫;不计入任何历史固定测试分母。"""

import ast
from pathlib import Path

import pytest

_ALLOWED_IMPORTS = {"__future__", "dataclasses", "enum", "typing"}
_FORBIDDEN_CALLS = {
    "__import__",
    "compile",
    "eval",
    "exec",
    "getattr",
    "globals",
    "locals",
    "open",
    "vars",
}


def _violations(source: str) -> list[str]:
    violations: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            violations.extend(
                alias.name for alias in node.names if alias.name not in _ALLOWED_IMPORTS
            )
        elif isinstance(node, ast.ImportFrom):
            if node.level or node.module not in _ALLOWED_IMPORTS:
                violations.append("." * node.level + (node.module or ""))
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in _FORBIDDEN_CALLS
        ):
            violations.append(node.func.id)
    return violations


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("import sqlite3", ["sqlite3"]),
        ("from sqlalchemy import Engine", ["sqlalchemy"]),
        ("import httpx", ["httpx"]),
        ("from paper_radar.pi_rpc import Session", ["paper_radar.pi_rpc"]),
        ("import docling", ["docling"]),
        ("from datetime import datetime as clock; clock.now()", ["datetime"]),
        ("import time as clock; clock.time()", ["time"]),
        ("from os import environ as values", ["os"]),
        ("from paper_radar import eligibility", ["paper_radar"]),
        ("from ..eligibility import evaluate", ["..eligibility"]),
        ("__import__('os')", ["__import__"]),
        ("open('paper.sqlite')", ["open"]),
    ],
)
def test_purity_guard_detects_io_implicit_inputs_and_upward_dependencies(
    source: str, expected: list[str]
) -> None:
    assert _violations(source) == expected


def test_visibility_entry_only_depends_on_pure_explicit_inputs() -> None:
    package = Path(__file__).parents[1] / "src/paper_radar/calibration"
    for name in ("__init__.py", "visibility.py"):
        path = package / name
        assert _violations(path.read_text(encoding="utf-8")) == [], name
