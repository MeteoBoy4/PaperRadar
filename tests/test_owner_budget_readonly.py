"""owner预算只读采样;仅合成SQLite,用合成字节核对采样零写入。"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from paper_radar.live_evidence.sealed_runtime import SiteConfiguration
from scripts import issue176_closure_workflow as workflow
from tests.site_collector_support import site_configuration


@pytest.fixture
def budget_site(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[SiteConfiguration, sqlite3.Connection]]:
    site = site_configuration(tmp_path)
    site.database.parent.mkdir(parents=True, exist_ok=True)
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "site.json").write_text(site.model_dump_json())
    monkeypatch.setattr(workflow, "RUNTIME", runtime)
    connection = sqlite3.connect(site.database)
    tables: dict[str, tuple[str, tuple[str | int, ...]]] = {
        "screening_budgets": ("budget_id TEXT,fingerprint TEXT", ("sb-1", "f" * 64)),
        "screening_tasks": (
            "task_id TEXT,budget_id TEXT,generation INTEGER",
            ("st-1", "sb-1", 2),
        ),
        "screening_attempts": ("task_id TEXT,attempt_no INTEGER", ("st-1", 1)),
        "screening_requests": (
            "receipt_id TEXT,task_id TEXT,source TEXT,scheduled_day TEXT",
            ("sr-1", "st-1", "scheduled", "2026-11-09"),
        ),
        "read_budgets": ("budget_id TEXT,fingerprint TEXT", ("rb-1", "e" * 64)),
        "read_tasks": (
            "task_id TEXT,budget_id TEXT,generation INTEGER",
            ("rt-1", "rb-1", 3),
        ),
        "read_attempts": (
            "attempt_id TEXT,task_id TEXT,ordinal INTEGER",
            ("ra-1", "rt-1", 1),
        ),
    }
    for table, (columns, row) in tables.items():
        connection.execute(f"CREATE TABLE {table} ({columns},payload TEXT)")
        connection.execute(
            f"INSERT INTO {table} VALUES({','.join('?' for _ in range(len(row) + 1))})",
            (*row, "synthetic-body-never-selected"),
        )
    connection.commit()
    # 仅fixture启用WAL;读首条记录即产生真实0-byte WAL与32768-byte SHM,无需checkpoint。
    assert connection.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
    connection.execute("SELECT budget_id FROM screening_budgets").fetchall()
    assert Path(str(site.database) + "-wal").stat().st_size == 0
    assert Path(str(site.database) + "-shm").stat().st_size == 32768
    try:
        yield site, connection
    finally:
        connection.close()


def test_stable_zero_wal_and_shm_allow_metadata_inventory_without_file_changes(
    budget_site: tuple[SiteConfiguration, sqlite3.Connection],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site, _ = budget_site
    paths = [
        site.database,
        Path(str(site.database) + "-wal"),
        Path(str(site.database) + "-shm"),
    ]
    before = {path: path.read_bytes() for path in paths}
    before_metadata = {path: path.stat() for path in paths}
    original_open = os.open
    original_connect = sqlite3.connect
    accessed_columns: set[str] = set()

    def open_main_only(
        path: str | os.PathLike[str],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        assert str(path) not in {str(item) for item in paths[1:]}, (
            "sidecar_content_opened"
        )
        return original_open(path, flags, mode, dir_fd=dir_fd)

    def readonly_connection(database: str, *, uri: bool = False) -> sqlite3.Connection:
        assert uri and database.endswith("?mode=ro&immutable=1")
        connection = original_connect(database, uri=uri)

        def authorize(
            action: int,
            table: str | None,
            column: str | None,
            database: str | None,
            trigger: str | None,
        ) -> int:
            if action == sqlite3.SQLITE_READ and column is not None:
                accessed_columns.add(column)
                if column == "payload":
                    return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        connection.set_authorizer(authorize)
        return connection

    monkeypatch.setattr(os, "open", open_main_only)
    monkeypatch.setattr(sqlite3, "connect", readonly_connection)
    result = workflow.budget_inventory()
    assert set(result) == {
        "screening_budgets",
        "screening_tasks",
        "screening_attempts",
        "screening_requests",
        "read_budgets",
        "read_tasks",
        "read_attempts",
    }
    assert all(item["count"] == 1 for item in result.values())
    assert {
        "budget_id",
        "fingerprint",
        "generation",
        "attempt_no",
        "ordinal",
        "scheduled_day",
        "receipt_id",
    } <= accessed_columns
    assert "payload" not in accessed_columns
    assert {path: path.stat() for path in paths} == before_metadata
    assert {path: path.read_bytes() for path in paths} == before
    assert not Path(str(site.database) + "-journal").exists()


def test_zero_wal_without_shm_is_read_without_creating_sidecars(
    budget_site: tuple[SiteConfiguration, sqlite3.Connection],
) -> None:
    site, _ = budget_site
    shm = Path(str(site.database) + "-shm")
    shm.unlink()  # 仅构造临时fixture,产品代码不删除。
    before = site.database.read_bytes()
    result = workflow.budget_inventory()
    assert all(item["count"] == 1 for item in result.values())
    assert not shm.exists()
    assert Path(str(site.database) + "-wal").stat().st_size == 0
    assert site.database.read_bytes() == before


@pytest.mark.parametrize(
    ("state", "reason"),
    [
        ("nonempty_wal", "closure_business_sidecars_present"),
        ("journal", "closure_business_sidecars_present"),
        ("wal_symlink", "closure_business_database_untrusted"),
        ("shm_hardlink", "closure_business_database_untrusted"),
        ("main_hardlink", "closure_business_database_untrusted"),
        ("wrong_owner", "closure_business_database_untrusted"),
        ("shm_without_wal", "closure_business_sidecars_present"),
    ],
)
def test_nonempty_or_untrusted_sidecars_still_refuse_without_cleanup(
    budget_site: tuple[SiteConfiguration, sqlite3.Connection], state: str, reason: str
) -> None:
    site, _ = budget_site
    wal, shm, journal = (
        Path(str(site.database) + suffix) for suffix in ("-wal", "-shm", "-journal")
    )
    if state == "nonempty_wal":
        wal.write_bytes(b"synthetic-nonempty-wal")
    elif state == "journal":
        journal.write_bytes(b"")
    elif state == "wal_symlink":
        wal.rename(wal.with_suffix(".original"))
        wal.symlink_to(wal.with_suffix(".original"))
    elif state == "shm_hardlink":
        os.link(shm, shm.with_suffix(".link"))
    elif state == "main_hardlink":
        os.link(site.database, site.database.with_suffix(".link"))
    elif state == "wrong_owner":
        (workflow.RUNTIME / "site.json").write_text(
            site.model_copy(
                update={"product_uid": site.product_uid + 1}
            ).model_dump_json()
        )
    else:
        wal.unlink()
    paths = [site.database, *(item for item in (wal, shm, journal) if item.exists())]
    before = {path: path.read_bytes() for path in paths}
    with pytest.raises(ValueError, match=reason):
        workflow.budget_inventory()
    assert {path: path.read_bytes() for path in paths} == before
    assert journal.exists() is (state == "journal")


@pytest.mark.parametrize(
    "change",
    [
        "wal_append",
        "wal_replace",
        "shm_touch",
        "main_replace",
        "journal_appear",
        "shm_disappear",
        "during_query",
        "main_unlink_on_open",
    ],
)
def test_changes_during_immutable_read_are_rejected_by_explicit_metadata_checks(
    budget_site: tuple[SiteConfiguration, sqlite3.Connection],
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    site, _ = budget_site
    wal, shm, journal = (
        Path(str(site.database) + suffix) for suffix in ("-wal", "-shm", "-journal")
    )
    connect = sqlite3.connect
    changed = False

    def mutate() -> None:
        nonlocal changed
        if changed:
            return
        changed = True
        if change == "wal_append":
            wal.write_bytes(b"concurrent-writer")
        elif change == "wal_replace":
            replacement = wal.with_suffix(".replacement")
            replacement.write_bytes(b"")
            replacement.replace(wal)
        elif change in {"shm_touch", "during_query"}:
            path = shm if change == "shm_touch" else site.database
            info = path.stat()
            os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns + 1))
        elif change == "main_replace":
            replacement = site.database.with_suffix(".replacement")
            replacement.write_bytes(site.database.read_bytes())
            replacement.replace(site.database)
        elif change == "journal_appear":
            journal.write_bytes(b"")
        else:
            shm.unlink()

    def interleaved_connection(
        database: str, *, uri: bool = False
    ) -> sqlite3.Connection:
        connection = connect(database, uri=uri)
        if change == "during_query":

            def trace(statement: str) -> None:
                if statement.startswith("SELECT "):
                    mutate()

            connection.set_trace_callback(trace)
        else:
            mutate()
        return connection

    if change == "main_unlink_on_open":
        original_open = os.open

        def disappear(
            path: str | os.PathLike[str],
            flags: int,
            mode: int = 0o777,
            *,
            dir_fd: int | None = None,
        ) -> int:
            nonlocal changed
            if Path(path) == site.database and not changed:
                changed = True
                site.database.unlink()
            return original_open(path, flags, mode, dir_fd=dir_fd)

        monkeypatch.setattr(os, "open", disappear)
    monkeypatch.setattr(sqlite3, "connect", interleaved_connection)
    with pytest.raises(ValueError, match="closure_business_database_changed"):
        workflow.budget_inventory()
    assert changed is True
