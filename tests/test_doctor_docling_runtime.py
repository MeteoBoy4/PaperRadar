"""D1: 显式 doctor Docling 范围;不扩展历史固定分母。"""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from paper_radar.cli import app
from tests.config_extraction_support import extraction_inputs
from tests.docling_runtime_support import environment


def test_explicit_runtime_reports_missing_extra(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment(monkeypatch, versions={}, modules=set())
    settings, _, database = extraction_inputs(tmp_path)
    result = CliRunner().invoke(
        app,
        [
            "doctor",
            "--scope",
            "docling-runtime",
            "--database",
            str(database),
            "--settings",
            str(settings),
        ],
    )
    assert result.exit_code == 2, result.output
    assert "scope=docling-runtime result=failed" in result.output
    assert (
        "check=docling_fixture.dependency.docling-slim result=missing" in result.output
    )
    assert (
        "check=docling_fixture.dependency.docling-core result=missing" in result.output
    )
    assert "uv sync --locked --extra docling" in result.output
    assert (
        "category=docling_fixture Docling 样本门禁 result=not_assessed" in result.output
    )
    for check in ("models", "native_abi", "quality", "resources"):
        assert f"check=docling_fixture.{check} result=not_assessed" in result.output


@pytest.mark.parametrize("selection", ["settings", "snapshot"])
def test_required_checks_can_pass_while_fixture_and_runtime_remain_unassessed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    selection: str,
) -> None:
    import shutil

    from paper_radar.config import compile_config
    from tests.test_doctor_process import inventory, logical

    settings, path, database = extraction_inputs(tmp_path)
    path.write_text(path.read_text().replace("cpu-v1", "cpu-v2"))
    saved = compile_config(settings, database)
    chosen = str(settings) if selection == "settings" else saved.snapshot_id[:12]
    if selection == "snapshot":
        shutil.rmtree(settings.parent)
    before_tree, before_db = inventory(tmp_path), logical(database)
    environment(monkeypatch)
    result = CliRunner().invoke(
        app,
        [
            "doctor",
            "--scope",
            "docling-runtime",
            "--database",
            str(database),
            f"--{selection}",
            chosen,
        ],
    )
    assert result.exit_code == 0, result.output
    assert "scope=docling-runtime result=passed" in result.output
    assert (
        "check=docling_fixture.platform result=passed reason=platform_supported"
        in result.output
    )
    assert (
        "check=docling_fixture.dependency.docling-core result=passed" in result.output
    )
    assert "backend=pypdfium2" in result.output
    assert (
        "category=docling_fixture Docling 样本门禁 result=not_assessed" in result.output
    )
    assert "0 不代表任何阶段可运行。" in result.output
    assert inventory(tmp_path) == before_tree
    assert logical(database) == before_db


def test_invalid_material_preserves_config_reason_and_never_probes_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import importlib.metadata
    import importlib.util

    settings, _, database = extraction_inputs(tmp_path)
    settings.write_text("extraction: [SECRET]\n")

    def forbidden(*_args: object) -> None:
        pytest.fail("配置非法，不得推测运行状态")

    monkeypatch.setattr(importlib.metadata, "version", forbidden)
    monkeypatch.setattr(importlib.util, "find_spec", forbidden)
    result = CliRunner().invoke(
        app,
        [
            "doctor",
            "--scope",
            "docling-runtime",
            "--database",
            str(database),
            "--settings",
            str(settings),
        ],
    )
    assert result.exit_code == 2
    assert "check=selection result=invalid reason=content_invalid" in result.output
    assert "docling_fixture.platform" not in result.output
    assert "docling_fixture.dependency" not in result.output
    assert "SECRET" not in result.output


def test_missing_extraction_is_missing_even_when_every_package_is_installed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, _, database = extraction_inputs(tmp_path)
    settings.write_text("extraction: null\n")
    environment(monkeypatch)
    result = CliRunner().invoke(
        app,
        [
            "doctor",
            "--scope",
            "docling-runtime",
            "--database",
            str(database),
            "--settings",
            str(settings),
        ],
    )
    assert result.exit_code == 2
    assert (
        "check=docling_fixture.selection result=missing reason=extraction_unselected"
        in result.output
    )
    assert "docling_fixture.dependency" not in result.output
