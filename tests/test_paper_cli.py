"""只读 paper CLI 与无 I/O 帮助。"""

import json
from pathlib import Path

import pytest

from paper_radar.papers import PaperFacts
from paper_radar.storage.database import upgrade_database
from tests.config_test_support import run_cli
from tests.test_paper_service import observation


@pytest.mark.parametrize(
    "arguments",
    [("paper", "--help"), ("paper", "show", "--help"), ("paper", "trace", "--help")],
)
def test_paper_help_is_chinese_and_has_no_io(
    tmp_path: Path, arguments: tuple[str, ...]
) -> None:
    before = set(tmp_path.rglob("*"))
    result = run_cli(tmp_path, *arguments, help_only=True)
    assert result.returncode == 0, result.stderr
    assert set(tmp_path.rglob("*")) == before
    for text in (
        "当前用途",
        "参数与选项",
        "副作用",
        "自动配额",
        "输出去向",
        "常见失败",
        "只读",
        "paper-radar paper",
    ):
        assert text in result.stdout


def test_paper_show_and_trace_default_hide_every_abstract(tmp_path: Path) -> None:
    database = tmp_path / "facts.sqlite"
    upgrade_database(database)
    result = PaperFacts(database, tmp_path / "data").submit(
        observation(
            fields={
                "title": {"value": "论文题名", "locator": "title"},
                "abstract": {
                    "value": {
                        "text": "SECRET-ABSTRACT",
                        "is_truncated": False,
                        "rule": "fixture",
                    },
                    "locator": "abstract",
                },
            }
        )
    )
    assert result.paper_id
    for command in ("show", "trace"):
        default = run_cli(
            tmp_path,
            "paper",
            command,
            result.paper_id,
            "--database",
            str(database),
            "--json",
        )
        assert default.returncode == 0, default.stderr
        assert "SECRET" not in default.stdout
        assert "论文题名" in default.stdout
        assert isinstance(json.loads(default.stdout), dict)
        expanded = run_cli(
            tmp_path,
            "paper",
            command,
            result.paper_id,
            "--database",
            str(database),
            "--json",
            "--show-abstract",
        )
        assert expanded.returncode == 0, expanded.stderr
        assert "SECRET-ABSTRACT" in expanded.stdout
    verified = run_cli(
        tmp_path,
        "paper",
        "trace",
        result.paper_id,
        "--database",
        str(database),
        "--data-root",
        str(tmp_path / "data"),
        "--verify-source-bytes",
    )
    assert verified.returncode == 0, verified.stderr
    assert "original response" not in verified.stdout


@pytest.mark.parametrize(
    "arguments",
    [
        ("paper", "SECRET-UNKNOWN"),
        ("paper", "show", "id", "--SECRET-UNKNOWN"),
        ("paper", "show", "id", "--database"),
    ],
)
def test_cli_argument_failures_are_redacted(
    tmp_path: Path, arguments: tuple[str, ...]
) -> None:
    result = run_cli(tmp_path, *arguments)
    assert result.returncode == 2
    assert "SECRET" not in result.stdout + result.stderr


def test_paper_missing_database_does_not_create_it(tmp_path: Path) -> None:
    database = tmp_path / "absent.sqlite"
    result = run_cli(tmp_path, "paper", "show", "id", "--database", str(database))
    assert result.returncode == 1
    assert not database.exists()
