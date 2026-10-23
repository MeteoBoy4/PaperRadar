"""a405 非空历史、a601 原子迁移及边界依赖。"""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine

from paper_radar.pi_supply import show_supply
from paper_radar.storage import database as database_module
from paper_radar.storage.artifacts import ArtifactStore
from paper_radar.storage.database import upgrade_database
from paper_radar.storage.errors import StorageError
from tests.artifact_support import fail_sql, paused_operation
from tests.config_test_support import imported_modules
from tests.pi_supply_support import inputs, prepare
from tests.restore_support import history_view


def previous_database(path: Path) -> None:
    config = Config()
    config.set_main_option(
        "script_location", str(Path(database_module.__file__).parent / "migrations")
    )
    engine = create_engine(f"sqlite:///{path}")
    try:
        with engine.connect() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "a405_pi_cleanup_execution")
            connection.commit()
    finally:
        engine.dispose()


@pytest.mark.parametrize("stop", ["success", "failure", "kill"])
def test_nonempty_a405_upgrade_preserves_config_artifact_and_pi_history(
    tmp_path: Path, stop: str
) -> None:
    source = inputs(tmp_path / "source")
    supply = prepare(tmp_path / "source", source)
    data_root = tmp_path / "source/data"
    ArtifactStore(source[0], data_root).publish_single(
        "source_snapshot", (b"old original bytes",)
    )
    old = tmp_path / "a405.sqlite3"
    previous_database(old)
    with (
        closing(sqlite3.connect(source[0])) as original,
        closing(sqlite3.connect(old)) as previous,
    ):
        names = [
            row[0]
            for row in previous.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND na"
                "me != 'alembic_version' ORDER BY name"
            )
        ]
        expected = {
            table: original.execute(f"SELECT * FROM {table}").fetchall()
            for table in names
        }
        for table, values in expected.items():
            previous.execute(f"DELETE FROM {table}")
            if values:
                previous.executemany(
                    f"INSERT INTO {table} VALUES ({','.join('?' for _ in values[0])})",
                    values,
                )
        previous.commit()
    if stop == "failure":
        with fail_sql("UPDATE alembic_version"), pytest.raises(StorageError) as failure:
            upgrade_database(old)
        assert failure.value.reason == "upgrade_failed"
    elif stop == "kill":
        with paused_operation(
            (
                "from pathlib import Path; import sys; from paper_radar.stora"
                "ge.database import upgrade_database; upgrade_database(Path(s"
                "ys.argv[1]))"
            ),
            [str(old)],
            "UPDATE alembic_version",
        ) as process:
            process.kill()
            process.wait(timeout=15)
    if stop != "success":
        with closing(sqlite3.connect(old)) as previous:
            assert previous.execute(
                "SELECT version_num FROM alembic_version"
            ).fetchone() == ("a405_pi_cleanup_execution",)
            assert (
                previous.execute(
                    "SELECT name FROM sqlite_master WHERE name='papers'"
                ).fetchall()
                == []
            )
    assert upgrade_database(old) == "a701_screening_registration"
    assert upgrade_database(old) == "a701_screening_registration"
    with closing(sqlite3.connect(old)) as previous:
        assert {
            table: previous.execute(f"SELECT * FROM {table}").fetchall()
            for table in names
        } == expected
    assert history_view(old, data_root) == history_view(source[0], data_root)
    assert show_supply(old, supply.supply_id) == show_supply(
        source[0], supply.supply_id
    )


def test_paper_module_dependency_boundaries() -> None:
    root = Path("src/paper_radar")
    for package in ("config", "screening", "stage_inputs"):
        for module in (root / package).rglob("*.py"):
            assert not any(
                name.startswith("paper_radar.papers")
                for name in imported_modules(module)
            ), module
    for module in (root / "papers").glob("*.py"):
        imports = imported_modules(module)
        assert not any(
            name.startswith(
                (
                    "httpx",
                    "requests",
                    "paper_radar.pi",
                    "paper_radar.adapters",
                    "docling",
                )
            )
            for name in imports
        ), module
        if module.stem in {"doi", "text", "rules", "models", "errors"}:
            assert not any(
                name.startswith(("sqlalchemy", "paper_radar.storage"))
                for name in imports
            ), module
