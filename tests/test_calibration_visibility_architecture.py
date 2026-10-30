"""纯规则边界守卫;不计入任何历史固定测试分母。"""

from pathlib import Path

import pytest

from tests.pure_dependency_support import pure_dependency_violations

_ALLOWED_IMPORTS = {"__future__", "dataclasses", "enum", "typing"}


def _violations(source: str) -> list[str]:
    return pure_dependency_violations(source, allowed_imports=_ALLOWED_IMPORTS)


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
        (
            "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n"
            "    from paper_radar.feed_metadata.models import MetadataResult",
            ["paper_radar.feed_metadata.models"],
        ),
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
