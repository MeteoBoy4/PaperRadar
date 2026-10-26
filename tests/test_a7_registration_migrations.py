"""非空 a604→a701 的原子升级及任务模块边界。"""

import ast
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine

from paper_radar.papers import PaperFacts
from paper_radar.screening_tasks import ScreeningTasks
from paper_radar.storage import database as database_module
from paper_radar.storage.database import upgrade_database
from paper_radar.storage.errors import StorageError
from tests.artifact_support import fail_sql, paused_operation
from tests.config_test_support import imported_modules
from tests.pi_supply_support import inputs, prepare
from tests.restore_support import history_view
from tests.test_paper_mapping import screening_fields
from tests.test_paper_service import observation


def a604_copy(source: Path, target: Path) -> dict[str, list[tuple[object, ...]]]:
    config = Config()
    config.set_main_option(
        "script_location", str(Path(database_module.__file__).parent / "migrations")
    )
    engine = create_engine(f"sqlite:///{target}")
    try:
        with engine.connect() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "a604_version_relations")
            connection.commit()
    finally:
        engine.dispose()
    with (
        closing(sqlite3.connect(source)) as original,
        closing(sqlite3.connect(target)) as previous,
    ):
        names = [
            row[0]
            for row in previous.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name!='alembic_version' ORDER BY name"
            )
        ]
        expected = {
            name: original.execute(f"SELECT * FROM {name}").fetchall() for name in names
        }
        for name, rows in expected.items():
            previous.execute(f"DELETE FROM {name}")
            if rows:
                previous.executemany(
                    f"INSERT INTO {name} VALUES ({','.join('?' for _ in rows[0])})",
                    rows,
                )
        previous.commit()
    return expected


@pytest.mark.parametrize(
    "stop", ["success", "ddl_failure", "stamp_failure", "kill_ddl", "kill_stamp"]
)
def test_nonempty_previous_revision_upgrade_is_atomic_and_retains_all_history(
    tmp_path: Path, stop: str
) -> None:
    root = tmp_path / "source"
    source = inputs(root)
    prepare(root, source)
    paper = PaperFacts(source[0], root / "data").submit(
        observation(fields=screening_fields())
    )
    assert paper.paper_id
    before = PaperFacts(source[0]).trace(paper.paper_id)
    old = tmp_path / "a604.sqlite"
    expected = a604_copy(source[0], old)
    with pytest.raises(StorageError) as failure:
        ScreeningTasks(old).register(
            {
                "paper_id": paper.paper_id,
                "snapshot_id": source[1],
                "stage": "boundary",
                "source": "scheduled",
                "scheduled_day": "2026-01-01",
            }
        )
    assert failure.value.reason == "upgrade_required"
    prefix = (
        "\nCREATE TABLE screening_requests"
        if "ddl" in stop
        else "UPDATE alembic_version"
    )
    if "failure" in stop:
        with fail_sql(prefix), pytest.raises(StorageError) as failure:
            upgrade_database(old)
        assert failure.value.reason == "upgrade_failed"
    elif stop.startswith("kill"):
        with paused_operation(
            "from pathlib import Path; import sys; from paper_radar.storage.database "
            "import upgrade_database; upgrade_database(Path(sys.argv[1]))",
            [str(old)],
            prefix,
        ) as process:
            process.kill()
            process.wait(timeout=15)
    if stop != "success":
        with closing(sqlite3.connect(old)) as connection:
            assert connection.execute(
                "SELECT version_num FROM alembic_version"
            ).fetchone() == ("a604_version_relations",)
            assert not connection.execute(
                "SELECT name FROM sqlite_master WHERE name LIKE 'screening_%'"
            ).fetchall()
            assert {
                name: connection.execute(f"SELECT * FROM {name}").fetchall()
                for name in expected
            } == expected
    assert upgrade_database(old) == "a1001_fixture_audit"
    assert upgrade_database(old) == "a1001_fixture_audit"
    with closing(sqlite3.connect(old)) as connection:
        assert {
            name: connection.execute(f"SELECT * FROM {name}").fetchall()
            for name in expected
        } == expected
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()
        assert connection.execute("PRAGMA journal_mode").fetchone() == ("wal",)
        names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE name LIKE 'screening_%' "
                "AND type='table'"
            )
        }
        assert names == {
            "screening_inputs",
            "screening_budgets",
            "screening_tasks",
            "screening_requests",
            "screening_attempts",
            "screening_leases",
            "screening_failures",
            "screening_successes",
        }
    assert PaperFacts(old).trace(paper.paper_id) == before
    assert history_view(old, root / "data") == history_view(source[0], root / "data")
    ScreeningTasks(old).validate_all()


def test_task_dependencies_and_pure_rules_do_not_acquire_execution_authority() -> None:
    root = Path("src/paper_radar")
    for package in ("config", "screening", "stage_inputs", "papers"):
        for module in (root / package).glob("*.py"):
            assert not any(
                name.startswith("paper_radar.screening_tasks")
                for name in imported_modules(module)
            ), module
    for module in (root / "screening_tasks").glob("*.py"):
        names = imported_modules(module)
        assert not any(
            name.startswith(
                (
                    "paper_radar.pi_supply",
                    "httpx",
                    "requests",
                    "docling",
                    "paper_radar.llm",
                )
            )
            for name in names
        ), module
        calls = [
            node.func
            for node in ast.walk(ast.parse(module.read_bytes()))
            if isinstance(node, ast.Call)
        ]
        assert not any(
            isinstance(node, ast.Attribute)
            and node.attr in {"now", "utcnow", "time", "getcwd", "getenv"}
            for node in calls
        ), module
        if module.stem in {"rules", "errors"}:
            assert not any(
                name.startswith(("sqlalchemy", "paper_radar.storage")) for name in names
            ), module
