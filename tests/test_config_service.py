"""A2-01 公共配置服务的持久化行为。"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from paper_radar.config import (
    ConfigError,
    check_config,
    compile_config,
    load_config_snapshot,
    upgrade_database,
)
from paper_radar.storage.database import REVISION, open_database
from paper_radar.storage.schema import metadata

_EXAMPLE_ID = "9ae65bc9fc282e8c0eab654644cff50a8831044f5847456562a683b751c21e58"


def _write_profile(root: Path, *, version: str = "profile-v1") -> Path:
    profile_dir = root / "config" / "profiles"
    profile_dir.mkdir(parents=True)
    (profile_dir / f"{version}.yaml").write_text(
        f"version: {version}\n"
        "background: Climate dynamics\n"
        "core_questions: Monsoon variability\n"
        "transferable_methods: Bayesian inference\n"
        "available_data_and_tools: Reanalysis\n"
        "theory_and_cognitive_interests: Causal mechanisms\n"
        "constraints_and_exclusions: No proprietary data\n",
        encoding="utf-8",
    )
    settings = root / "config" / "settings.yaml"
    settings.write_text(f"profile: {version}\n", encoding="utf-8")
    return settings


def test_profile_snapshot_survives_source_removal_and_new_process(
    tmp_path: Path,
) -> None:
    settings = _write_profile(tmp_path)
    db = tmp_path / "data.sqlite3"
    upgrade_database(db)
    original = (tmp_path / "config/profiles/profile-v1.yaml").read_bytes()

    checked = check_config(settings, db)
    assert checked.profile_status == "configured"
    assert checked.stages["boundary"].status == "not_ready"
    with sqlite3.connect(db) as connection:
        assert connection.execute(
            "SELECT count(*) FROM config_versions"
        ).fetchone() == (0,)
    saved = compile_config(settings, db)
    assert saved.snapshot_id == checked.snapshot_id
    with sqlite3.connect(db) as connection:
        created_at = connection.execute(
            "SELECT created_at FROM runtime_config_snapshots"
        ).fetchone()
    assert compile_config(settings, db).snapshot_id == saved.snapshot_id
    with sqlite3.connect(db) as connection:
        assert (
            connection.execute(
                "SELECT created_at FROM runtime_config_snapshots"
            ).fetchone()
            == created_at
        )
    assert (tmp_path / "config/profiles/profile-v1.yaml").read_bytes() == original

    settings.unlink()
    (tmp_path / "config/profiles/profile-v1.yaml").unlink()
    assert load_config_snapshot(db, saved.snapshot_id) == saved


def test_check_is_read_only_and_compile_rejects_missing_database(
    tmp_path: Path,
) -> None:
    settings = _write_profile(tmp_path)
    db = tmp_path / "missing.sqlite3"
    with pytest.raises(ConfigError, match="数据库"):
        check_config(settings, db)
    with pytest.raises(ConfigError, match="数据库"):
        compile_config(settings, db)
    assert not db.exists()


def test_unselected_profile_is_savable_but_not_ready(tmp_path: Path) -> None:
    settings = tmp_path / "config/settings.yaml"
    settings.parent.mkdir()
    settings.write_text("profile: null\n", encoding="utf-8")
    db = tmp_path / "db.sqlite3"
    upgrade_database(db)
    result = compile_config(settings, db)
    assert result.profile_status == "unconfigured"
    assert load_config_snapshot(db, result.snapshot_id) == result


def test_version_bytes_are_immutable_across_restart(tmp_path: Path) -> None:
    settings = _write_profile(tmp_path)
    db = tmp_path / "db.sqlite3"
    upgrade_database(db)
    first = compile_config(settings, db)
    profile = tmp_path / "config/profiles/profile-v1.yaml"
    profile.write_bytes(profile.read_bytes() + b"# comment\n")
    with pytest.raises(ConfigError, match="声明版本已登记不同字节"):
        compile_config(settings, db)
    assert load_config_snapshot(db, first.snapshot_id) == first


def test_same_inputs_moved_to_another_root_keep_identity(tmp_path: Path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first = _write_profile(first_root)
    second = _write_profile(second_root)
    first_db = tmp_path / "first.sqlite3"
    second_db = tmp_path / "second.sqlite3"
    upgrade_database(first_db)
    upgrade_database(second_db)
    assert (
        compile_config(first, first_db).snapshot_id
        == compile_config(second, second_db).snapshot_id
    )


def test_upgrade_is_idempotent_and_schema_matches_metadata(tmp_path: Path) -> None:
    db = tmp_path / "db.sqlite3"
    assert upgrade_database(db) == REVISION
    assert upgrade_database(db) == REVISION
    engine = open_database(db, mode="rw")
    try:
        with engine.connect() as connection:
            assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
            assert connection.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
            context = MigrationContext.configure(connection)
            assert compare_metadata(context, metadata) == []
            driver = connection.connection.driver_connection
            assert driver is not None
            with pytest.raises(sqlite3.IntegrityError):
                driver.execute(
                    "INSERT INTO snapshot_version_refs "
                    "(snapshot_id, kind, name, declared_version, raw_sha256) "
                    "VALUES ('missing', 'profile', 'profile', 'v1', 'hash')"
                )
    finally:
        engine.dispose()


def test_mid_transaction_failure_leaves_no_config_facts(tmp_path: Path) -> None:
    settings = _write_profile(tmp_path)
    db = tmp_path / "db.sqlite3"
    upgrade_database(db)
    with sqlite3.connect(db) as connection:
        connection.execute(
            "CREATE TRIGGER fail_snapshot BEFORE INSERT ON runtime_config_snapshots "
            "BEGIN SELECT RAISE(ABORT, 'injected'); END"
        )
    with pytest.raises(ConfigError, match="已回滚"):
        compile_config(settings, db)
    with sqlite3.connect(db) as connection:
        assert connection.execute(
            "SELECT count(*) FROM config_versions"
        ).fetchone() == (0,)
        assert connection.execute(
            "SELECT count(*) FROM runtime_config_snapshots"
        ).fetchone() == (0,)


def test_load_rejects_damaged_version_content(tmp_path: Path) -> None:
    settings = _write_profile(tmp_path)
    db = tmp_path / "db.sqlite3"
    upgrade_database(db)
    snapshot = compile_config(settings, db)
    with sqlite3.connect(db) as connection:
        connection.execute("UPDATE config_versions SET raw_content = ?", (b"changed",))
    with pytest.raises(ConfigError, match="损坏"):
        load_config_snapshot(db, snapshot.snapshot_id)


def test_cross_process_load_uses_database_only(tmp_path: Path) -> None:
    settings = _write_profile(tmp_path)
    db = tmp_path / "db.sqlite3"
    upgrade_database(db)
    snapshot = compile_config(settings, db)
    (tmp_path / "config/profiles/profile-v1.yaml").unlink()
    script = (
        "import sys; from pathlib import Path; "
        "from paper_radar.config import load_config_snapshot; "
        "print(load_config_snapshot(Path(sys.argv[1]), sys.argv[2]).snapshot_id)"
    )
    result = subprocess.run(
        [sys.executable, "-c", script, str(db), snapshot.snapshot_id],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == snapshot.snapshot_id


def test_synthetic_example_has_fixed_snapshot_identity(tmp_path: Path) -> None:
    settings = Path(__file__).resolve().parents[1] / "examples/config/settings.yaml"
    db = tmp_path / "db.sqlite3"
    upgrade_database(db)
    assert compile_config(settings, db).snapshot_id == _EXAMPLE_ID
