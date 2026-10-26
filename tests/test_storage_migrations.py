"""A3 真实旧库的显式升级、原子 DDL 和 revision 分类。"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine

from paper_radar.storage import database as database_module
from paper_radar.storage.database import upgrade_database
from paper_radar.storage.errors import StorageError


def old_database(path: Path) -> None:
    config = Config()
    config.set_main_option(
        "script_location", str(Path(database_module.__file__).parent / "migrations")
    )
    engine = create_engine(f"sqlite:///{path}")
    try:
        with engine.connect() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "a201_profile_snapshot")
            connection.commit()
    finally:
        engine.dispose()


def test_failed_ddl_and_stamp_upgrade_rolls_back_as_one_transaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "db.sqlite3"
    old_database(database)
    scripts = tmp_path / "migrations"
    shutil.copytree(Path(database_module.__file__).parent / "migrations", scripts)
    # 安装包迁移故障注入;真实 DDL 后抛错,不能留下不可重跑的表。
    (scripts / "versions/failing.py").write_text(
        "from alembic import op\nfrom pathlib import Path\n"
        'revision = "test_atomic_head"\n'
        'down_revision = "a201_profile_snapshot"\n'
        "def upgrade():\n"
        '    op.execute("CREATE TABLE migration_probe (id INTEGER)")\n'
        f"    Path({str(tmp_path / 'reached')!r}).touch()\n"
        '    raise RuntimeError("injected")\n',
        encoding="utf-8",
    )
    # 后续新增随包 migration 时,从副本移除,保持本故障探针为唯一 head。
    for script in (scripts / "versions").glob("*.py"):
        if script.name not in ("a201_profile_snapshot.py", "failing.py"):
            script.unlink()
    monkeypatch.setattr(database_module, "_MIGRATIONS", scripts)
    with pytest.raises(StorageError):
        upgrade_database(database)
    assert (tmp_path / "reached").exists()
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone() == ("a201_profile_snapshot",)
        assert (
            connection.execute(
                "SELECT name FROM sqlite_master WHERE name = 'migration_probe'"
            ).fetchall()
            == []
        )


def seed_old_history(tmp_path: Path) -> tuple[Path, Path, str]:
    from paper_radar.config import compile_config
    from paper_radar.storage.database import DatabaseMode, open_database
    from paper_radar.storage.records import VersionRecord
    from paper_radar.storage.repository import save_snapshot
    from tests.config_projection_support import full_inputs

    settings, seed = full_inputs(tmp_path / "validated")
    saved = compile_config(settings, seed)
    assert (
        saved.snapshot_id
        == "cc63bda022c43f5f20d139d3cbe8b882e245f97eea5484f1348beb7833f23b9d"
    )
    with sqlite3.connect(seed) as connection:
        records = tuple(
            VersionRecord(kind, name, version, raw)
            for kind, name, version, raw in connection.execute(
                "SELECT kind,name,declared_version,raw_content FROM config_versions"
            )
        )
    database = tmp_path / "old.sqlite3"
    old_database(database)
    engine = open_database(database, mode=DatabaseMode.READ_WRITE)
    try:
        save_snapshot(engine, saved.snapshot_id, saved.payload_json, records)
    finally:
        engine.dispose()
    return settings, database, saved.snapshot_id


@pytest.mark.parametrize("stop", ["success", "failure", "kill"])
def test_real_a201_history_survives_atomic_upgrade_and_retry(
    tmp_path: Path, stop: str
) -> None:
    from paper_radar.config import load_config_snapshot, project_config
    from tests.artifact_support import fail_sql, paused_operation
    from tests.config_transaction_support import config_facts

    settings, database, snapshot_id = seed_old_history(tmp_path)
    original = config_facts(database)
    with sqlite3.connect(database) as connection:
        original_tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    if stop == "failure":
        with fail_sql("UPDATE alembic_version"), pytest.raises(StorageError):
            upgrade_database(database)
    elif stop == "kill":
        with paused_operation(
            (
                "from pathlib import Path;import sys;from paper_radar.storage"
                ".database import upgrade_database;upgrade_database(Path(sys."
                "argv[1]))"
            ),
            [str(database)],
            "UPDATE alembic_version",
        ) as process:
            process.kill()
            process.wait(timeout=15)
    if stop != "success":
        with sqlite3.connect(database) as connection:
            assert (
                connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                ).fetchall()
                == original_tables
            )
            assert connection.execute(
                "SELECT version_num FROM alembic_version"
            ).fetchone() == ("a201_profile_snapshot",)
        assert config_facts(database) == original
    assert upgrade_database(database) == "a1001_fixture_audit"
    assert config_facts(database) == original
    restored = load_config_snapshot(database, snapshot_id)
    assert restored.payload_json == original[1][0][1]
    # 对照由固定 ID 的原材料生成的既有公共语义入口,而非复制投影算法。
    from paper_radar.config import compile_config

    expected = compile_config(settings, settings.parent.parent / "db.sqlite3")
    assert project_config(restored) == project_config(expected)
    assert len(project_config(restored).projections) == 6
    assert upgrade_database(database) == "a1001_fixture_audit"
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone() == ("wal",)


@pytest.mark.parametrize(
    "command_args",
    [
        ["config", "check"],
        ["config", "compile"],
        ["config", "diff", "0" * 64, "1" * 64],
        ["config", "snapshots", "list"],
    ],
)
def test_configuration_cli_on_known_old_database_directs_explicit_upgrade(
    tmp_path: Path, command_args: list[str]
) -> None:
    from typer.testing import CliRunner

    from paper_radar.cli import app

    settings, database, _ = seed_old_history(tmp_path)
    args = [*command_args, "--database", str(database)]
    if command_args[-1] in ("check", "compile"):
        args.extend(["--settings", str(settings)])
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 2
    assert "db upgrade" in result.output
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone() == ("a201_profile_snapshot",)


@pytest.mark.parametrize(
    ("state", "reason"),
    [
        ("missing", "database_missing"),
        ("empty", "database_uninitialized"),
        ("ancestor", "upgrade_required"),
        ("unknown", "unknown_revision"),
        ("zero_rows", "database_revision_corrupt"),
        ("multiple_rows", "database_revision_corrupt"),
        ("multiple_heads", "package_migrations_invalid"),
    ],
)
def test_database_revision_failures_have_distinct_controlled_reasons(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, state: str, reason: str
) -> None:
    from paper_radar.storage.database import (
        DatabaseMode,
        open_database,
        require_current_revision,
    )

    database = tmp_path / "db.sqlite3"
    if state == "empty":
        sqlite3.connect(database).close()
    elif state != "missing":
        old_database(database)
        with sqlite3.connect(database) as connection:
            if state == "unknown":
                connection.execute(
                    "UPDATE alembic_version SET version_num='not_in_graph'"
                )
            if state == "zero_rows":
                connection.execute("DELETE FROM alembic_version")
            if state == "multiple_rows":
                connection.execute("INSERT INTO alembic_version VALUES ('other')")
        if state == "multiple_heads":
            scripts = tmp_path / "migrations"
            shutil.copytree(
                Path(database_module.__file__).parent / "migrations", scripts
            )
            (scripts / "versions/other.py").write_text(
                'revision="other_head"\ndown_revision=None\ndef upgrade(): pass\n',
                encoding="utf-8",
            )
            monkeypatch.setattr(database_module, "_MIGRATIONS", scripts)
    with pytest.raises(StorageError) as failure:
        engine = open_database(database, mode=DatabaseMode.READ_ONLY)
        try:
            require_current_revision(engine)
        finally:
            engine.dispose()
    assert failure.value.reason == reason


@pytest.mark.parametrize(
    "bad_sql",
    [
        "INSERT INTO content_objects VALUES ('BAD', 0, 1, 'bad', 'now')",
        "INSERT INTO content_objects VALUES ('" + "a" * 64 + "', -1, 1, 'bad', 'now')",
        "INSERT INTO content_objects VALUES ('" + "a" * 64 + "', 1.5, 1, 'bad', 'now')",
        "INSERT INTO artifacts VALUES ('invalid', 'source_snapshot', 1, 'now')",
        "INSERT INTO artifact_members VALUES ('"
        + "a" * 64
        + "', 'payload', '"
        + "b" * 64
        + "', 0)",
    ],
)
def test_sqlite_enforces_storage_hex_size_and_foreign_keys(
    tmp_path: Path, bad_sql: str
) -> None:
    database = tmp_path / "db.sqlite3"
    upgrade_database(database)
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(bad_sql)


@pytest.mark.parametrize("table", ["content_objects", "artifacts", "artifact_members"])
def test_sqlite_enforces_registered_storage_primary_keys(
    tmp_path: Path, table: str
) -> None:
    from paper_radar.storage.artifacts import ArtifactStore

    database = tmp_path / "db.sqlite3"
    upgrade_database(database)
    ArtifactStore(database, tmp_path / "root").publish_single(
        "source_snapshot", [b"abc"]
    )
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(f"INSERT INTO {table} SELECT * FROM {table}")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO content_objects SELECT ?,size_bytes,layout_version,"
                "relative_path,created_at FROM content_objects",
                ("b" * 64,),
            )
