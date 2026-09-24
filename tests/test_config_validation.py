"""A2-01 严格材料边界和受控错误。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from paper_radar.config import (
    ConfigError,
    check_config,
    compile_config,
    load_config_snapshot,
    upgrade_database,
)


@pytest.fixture
def config_files(tmp_path: Path) -> tuple[Path, Path, Path]:
    folder = tmp_path / "config"
    profiles = folder / "profiles"
    profiles.mkdir(parents=True)
    settings = folder / "settings.yaml"
    profile = profiles / "profile-v1.yaml"
    settings.write_text("profile: profile-v1\n", encoding="utf-8")
    profile.write_text(
        "version: profile-v1\nbackground: 2026-09-23\n", encoding="utf-8"
    )
    db = tmp_path / "db.sqlite3"
    upgrade_database(db)
    return settings, profile, db


@pytest.mark.parametrize(
    "content",
    [
        "version: profile-v1\nversion: profile-v1\n",
        "version: profile-v1\nbackground: &a text\ncore_questions: *a\n",
        "version: profile-v1\nbase: &a {background: text}\n<<: *a\n",
        "version: profile-v1\nbackground: !custom text\n",
        "version: profile-v1\n---\nbackground: text\n",
        "version: 1.0\n",
        "version: profile-v2\n",
        "version: profile-v1\napi_key: do-not-print-me\n",
        "version: profile-v1\nbackground: .nan\n",
        "version: profile-v1\nbackground: +.INF\n",
        "version: profile-v1\nbackground: [wrong-type]\n",
    ],
)
def test_invalid_profile_is_rejected_without_leaking_value(
    config_files: tuple[Path, Path, Path], content: str
) -> None:
    settings, profile, db = config_files
    profile.write_text(content, encoding="utf-8")
    with pytest.raises(ConfigError) as error:
        compile_config(settings, db)
    assert "do-not-print-me" not in str(error.value)
    with sqlite3.connect(db) as connection:
        assert connection.execute(
            "SELECT count(*) FROM config_versions"
        ).fetchone() == (0,)


@pytest.mark.parametrize(
    "content",
    [
        "profile: profile-v1\nprofile: profile-v1\n",
        "profile: 1.0\n",
        "profile: profile-v1\nsecret: do-not-print-me\n",
        "profile: profile-v1\nmodels: {screening: model-v1}\n",
        "profile: profile-v1\ntopics: topics-v1\n",
        "profile: profile-v1\nmodels: {screening: null, reading: null}\nunknown: 1\n",
    ],
)
def test_invalid_settings_are_rejected_without_registry_changes(
    config_files: tuple[Path, Path, Path], content: str
) -> None:
    settings, _, db = config_files
    settings.write_text(content, encoding="utf-8")
    with pytest.raises(ConfigError) as error:
        check_config(settings, db)
    assert "do-not-print-me" not in str(error.value)
    with sqlite3.connect(db) as connection:
        assert connection.execute(
            "SELECT count(*) FROM config_versions"
        ).fetchone() == (0,)


def test_date_text_and_exact_ascii_placeholder_rules(
    config_files: tuple[Path, Path, Path],
) -> None:
    settings, profile, db = config_files
    profile.write_text(
        "version: profile-v1\nbackground: 2026-09-23\ncore_questions: ' ... '\n"
        "transferable_methods: …\n",
        encoding="utf-8",
    )
    result = compile_config(settings, db)
    assert result.profile_fields["background"] == "configured"
    assert result.profile_fields["core_questions"] == "placeholder"
    assert result.profile_fields["transferable_methods"] == "configured"
    assert result.profile_fields["available_data_and_tools"] == "unconfigured"
    assert result.profile_status == "placeholder"


def test_quoted_nonfinite_spelling_is_profile_text(
    config_files: tuple[Path, Path, Path],
) -> None:
    settings, profile, db = config_files
    profile.write_text("version: profile-v1\nbackground: '.nan'\n", encoding="utf-8")
    assert compile_config(settings, db).profile_fields["background"] == "configured"


def test_unsupported_format_and_unknown_revision_fail_cleanly(
    config_files: tuple[Path, Path, Path],
) -> None:
    settings, _, db = config_files
    result = compile_config(settings, db)
    with sqlite3.connect(db) as connection:
        connection.execute(
            "UPDATE runtime_config_snapshots SET payload_json = "
            "replace(payload_json, 'format_version\":1', 'format_version\":2')"
        )
    with pytest.raises(ConfigError, match="编译格式"):
        load_config_snapshot(db, result.snapshot_id)
    with sqlite3.connect(db) as connection:
        connection.execute("UPDATE alembic_version SET version_num = 'future_revision'")
    with pytest.raises(ConfigError, match="revision"):
        check_config(settings, db)
