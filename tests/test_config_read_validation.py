"""A2-06 严格 Read 配置与未来契约边界。"""

import sqlite3
from pathlib import Path

import pytest

from paper_radar.config import ConfigError, check_config, compile_config
from tests.config_read_support import read_inputs


@pytest.mark.parametrize(
    ("content", "field"),
    [
        ("version: read-v1\n", "read.chunking_version"),
        ("version: read-v1\nchunking_version: v2\n", "read.chunking_version"),
        ("version: read-v1\nchunking_version: null\n", "read.chunking_version"),
        ("version: read-v1\nchunking_version: true\n", "read.chunking_version"),
        ("version: read-v1\nchunking_version: 1\n", "read.chunking_version"),
        ("version: read-v2\nchunking_version: v1\n", "read.version"),
        ("version: '../secret-marker'\nchunking_version: v1\n", "read.version"),
        ("chunking_version: v1\n", "read.version"),
        ("version: read-v1\nchunking_version: v1\nchunking_version: v1\n", "重复"),
        ("version: read-v1\nchunking_version: &a v1\n", "锚点"),
        ("version: read-v1\nchunking_version: !custom v1\n", "tag"),
        ("version: read-v1\n---\nchunking_version: v1\n", "单文档"),
        (
            "version: read-v1\nchunking_version: v1\nlanguage: secret-marker\n",
            "read.language",
        ),
        (
            "version: read-v1\nchunking_version: v1\napi_key: secret-marker\n",
            "read.api_key",
        ),
        (
            "version: read-v1\nchunking_version: v1\npaper_id: secret-marker\n",
            "read.paper_id",
        ),
    ],
)
def test_invalid_read_material_is_rejected_without_partial_registration(
    tmp_path: Path, content: str, field: str
) -> None:
    settings, db = read_inputs(tmp_path)
    (settings.parent / "read/read-v1.yaml").write_text(content, encoding="utf-8")
    for operation in (check_config, compile_config):
        with pytest.raises(ConfigError, match=field) as error:
            operation(settings, db)
        assert "secret-marker" not in str(error.value)
    with sqlite3.connect(db) as connection:
        assert connection.execute(
            "SELECT count(*) FROM config_versions"
        ).fetchone() == (0,)


@pytest.mark.parametrize(
    ("extra", "field"),
    [
        ("read: '../secret-marker'\n", "settings.read"),
        ("read: 1\n", "settings.read"),
        ("read: {chunking_version: v1}\n", "settings.read"),
        ("language: secret-marker\n", "settings.language"),
        ("paper_id: secret-marker\n", "settings.paper_id"),
        ("artifact: secret-marker\n", "settings.artifact"),
        ("task: secret-marker\n", "settings.task"),
        ("contracts:\n  reading: v1\n", "settings.contracts.reading"),
        ("contracts:\n  read: v1\n", "contracts.read：missing_snapshot"),
    ],
)
def test_settings_cannot_supply_paper_inputs_or_unsupported_read_schema(
    tmp_path: Path, extra: str, field: str
) -> None:
    settings, db = read_inputs(tmp_path)
    settings.write_text(extra, encoding="utf-8")
    with pytest.raises(ConfigError, match=field) as error:
        compile_config(settings, db)
    assert "secret-marker" not in str(error.value)


@pytest.mark.parametrize("material", ["read", "reading"])
@pytest.mark.parametrize("damage", ["missing", "utf8"])
def test_selected_read_material_must_be_readable_utf8(
    tmp_path: Path, material: str, damage: str
) -> None:
    settings, db = read_inputs(tmp_path)
    path = tmp_path / (
        "config/read/read-v1.yaml" if material == "read" else "prompts/reading/v1.md"
    )
    if damage == "missing":
        path.unlink()
    else:
        path.write_bytes(b"\xffsecret-marker")
    with pytest.raises(ConfigError, match="read") as error:
        check_config(settings, db)
    assert "secret-marker" not in str(error.value)
