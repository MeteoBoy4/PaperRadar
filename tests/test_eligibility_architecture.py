"""资格纯度和依赖方向守卫;独立工程证据。"""

import ast
from pathlib import Path

import pytest


def _violations(source: str) -> list[str]:
    tree = ast.parse(source)
    type_only = {
        id(child)
        for node in ast.walk(tree)
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Name)
        and node.test.id == "TYPE_CHECKING"
        for statement in node.body
        for child in ast.walk(statement)
    }
    allowed = {
        "__future__",
        "dataclasses",
        "enum",
        "typing",
        "collections.abc",
        "paper_radar.calibration.visibility",
        "paper_radar.screening.reasons",
        "paper_radar.eligibility.models",
        "paper_radar.eligibility.rules",
    }
    allowed_type_only = {
        "paper_radar.feed_metadata.models",
        "paper_radar.screening_tasks.success_models",
    }
    forbidden_calls = {
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
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            violations.extend(
                item.name for item in node.names if item.name not in allowed
            )
        elif isinstance(node, ast.ImportFrom):
            if node.level or (
                node.module not in allowed
                and not (id(node) in type_only and node.module in allowed_type_only)
            ):
                violations.append("." * node.level + (node.module or ""))
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in forbidden_calls
        ):
            violations.append(node.func.id)
    return violations


@pytest.mark.parametrize(
    "source",
    [
        "import sqlite3",
        "from sqlalchemy import Engine",
        "import httpx",
        "from paper_radar.llm import Session",
        "import docling",
        "from datetime import datetime as clock; clock.now()",
        "import time",
        "from os import environ",
        "open('database')",
        "__import__('os')",
        "from ..feed_pipeline import FeedPipeline",
        "from paper_radar.feed_metadata.models import MetadataResult",
    ],
)
def test_guard_rejects_io_implicit_inputs_and_runtime_service_dependencies(
    source: str,
) -> None:
    assert _violations(source)


def test_eligibility_runtime_depends_only_on_pure_rules_and_type_only_projections() -> (
    None
):
    root = Path(__file__).parents[1] / "src/paper_radar/eligibility"
    for path in root.glob("*.py"):
        assert _violations(path.read_text(encoding="utf-8")) == [], path.name


def test_type_only_projection_imports_are_allowed() -> None:
    assert (
        _violations(
            "from typing import TYPE_CHECKING\n"
            "if TYPE_CHECKING:\n"
            "    from paper_radar.feed_metadata.models import MetadataResult\n"
            "    from paper_radar.screening_tasks.success_models import SuccessView\n"
        )
        == []
    )


def test_visibility_and_screening_do_not_import_eligibility() -> None:
    root = Path(__file__).parents[1] / "src/paper_radar"
    for package in ("calibration", "screening"):
        for path in (root / package).rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Import):
                    assert all(
                        "eligibility" not in item.name.split(".") for item in node.names
                    )
                elif isinstance(node, ast.ImportFrom):
                    assert "eligibility" not in (node.module or "").split(".")
                    assert all(item.name != "eligibility" for item in node.names)
