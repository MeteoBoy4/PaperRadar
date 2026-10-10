"""A2-05 安装入口的完整性、受控错误、help 和零网络承诺。"""

from pathlib import Path

import pytest

from paper_radar.config import load_config_snapshot
from tests.config_extraction_support import extraction_inputs
from tests.config_test_support import run_cli


def test_cli_checks_compiles_and_replays_extraction(tmp_path: Path) -> None:
    settings, _, db = extraction_inputs(tmp_path)
    args = ("--settings", str(settings), "--database", str(db))
    checked = run_cli(tmp_path, "config", "check", *args)
    assert checked.returncode == 0, checked.stderr
    assert "extraction：ready；缺项：" in checked.stdout
    saved = run_cli(tmp_path, "config", "compile", *args)
    assert saved.returncode == 0, saved.stderr
    assert saved.stdout == checked.stdout
    snapshot_id = saved.stdout.splitlines()[0].split("：")[1]
    assert load_config_snapshot(db, snapshot_id).extraction is not None
    settings.write_text("extraction: null\n")
    missing = run_cli(tmp_path, "config", "compile", *args)
    assert missing.returncode == 0, missing.stderr
    assert "extraction：not_ready；缺项：extraction_config" in missing.stdout


@pytest.mark.parametrize(
    ("old", "new", "field"),
    [
        ("toolchain: docling-2.135.0-cpu-v1\n", "", "toolchain"),
        (
            "normalization_version: v1",
            "normalization_version: PRIVATE_MARKER",
            "normalization_version",
        ),
        ("'" + "a" * 64 + "'", "PRIVATE_MARKER", "models.layout.files.0.sha256"),
        (
            "version: extraction-v1",
            "version: extraction-v1\ntimeout: PRIVATE_MARKER",
            "timeout",
        ),
        (
            "version: extraction-v1",
            "version: extraction-v1\npolicy:\n  do_ocr: true",
            "policy.do_ocr",
        ),
        (
            "version: extraction-v1",
            "version: extraction-v1\npassword: PRIVATE_MARKER",
            "password",
        ),
    ],
)
def test_cli_errors_are_sanitized_and_actionable(
    tmp_path: Path,
    old: str,
    new: str,
    field: str,
) -> None:
    settings, path, db = extraction_inputs(tmp_path)
    path.write_text(path.read_text().replace(old, new))
    for command in ("check", "compile"):
        result = run_cli(
            tmp_path,
            "config",
            command,
            "--settings",
            str(settings),
            "--database",
            str(db),
        )
        assert result.returncode == 2
        assert f"extraction.{field}" in result.stderr
        assert "PRIVATE_MARKER" not in result.stdout + result.stderr
        assert "Traceback" not in result.stderr


@pytest.mark.parametrize("level", [(), ("check",), ("compile",)])
def test_extraction_help_documents_scope_without_external_io(
    tmp_path: Path,
    level: tuple[str, ...],
) -> None:
    result = run_cli(tmp_path, "config", *level, "--help", help_only=True)
    assert result.returncode == 0, result.stderr
    if not level:
        assert "正文提取" in result.stdout
        assert "fixture" in result.stdout
    assert not list(tmp_path.iterdir())
