"""A2-09 公共配置服务在竞争、中断和文件替换下的承诺。"""

from __future__ import annotations

import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from sqlalchemy import Connection, Engine, event

from paper_radar.config import (
    ConfigError,
    check_config,
    compile_config,
    load_config_snapshot,
    upgrade_database,
)
from tests.config_transaction_support import (
    before_sql,
    config_facts,
    profile_inputs,
    recovery_inputs,
)


def test_compile_lock_budget_is_fixed_and_busy_error_is_actionable(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    settings = profile_inputs(tmp_path)
    database = tmp_path / "db.sqlite3"
    upgrade_database(database)
    before = config_facts(database)
    with sqlite3.connect(database) as owner:
        owner.execute("BEGIN IMMEDIATE")
        started = time.monotonic()
        with pytest.raises(ConfigError, match=r"数据库忙.*5 秒.*请稍后重试"):
            compile_config(settings, database)
        elapsed = time.monotonic() - started
    # 墙钟包含 CI 调度延迟。上界仅防止失控等待。SQLite 锁预算仍固定为 5 秒。
    assert 4.5 <= elapsed < 30
    assert config_facts(database) == before
    assert "PRIVATE_PROFILE_MARKER" not in caplog.text
    assert compile_config(settings, database).profile_status == "configured"


def test_check_does_not_report_corruption_when_compiler_commits_between_reads(
    tmp_path: Path,
) -> None:
    settings = profile_inputs(tmp_path)
    database = tmp_path / "db.sqlite3"
    upgrade_database(database)
    committed = False

    def commit_competing_compile(connection: Connection) -> None:
        nonlocal committed
        if not committed:
            committed = True
            compile_config(settings, database)

    with before_sql(
        "SELECT snapshot_version_refs.snapshot_id", commit_competing_compile
    ):
        checked = check_config(settings, database)
    assert committed
    assert load_config_snapshot(database, checked.snapshot_id) == checked


@pytest.mark.parametrize("different_bytes", [False, True])
def test_independent_compilers_reread_winner_inside_write_transaction(
    tmp_path: Path, different_bytes: bool, caplog: pytest.LogCaptureFixture
) -> None:
    first = profile_inputs(tmp_path / "first")
    second = profile_inputs(tmp_path / "second")
    if different_bytes:
        profile = second.parent / "profiles/profile-v1.yaml"
        profile.write_bytes(profile.read_bytes() + b"# PRIVATE_SECRET_MARKER\n")
    original = {p: p.read_bytes() for p in tmp_path.rglob("*.yaml")}
    database = tmp_path / "db.sqlite3"
    upgrade_database(database)
    barrier = Barrier(3, timeout=10)
    connections: list[object] = []

    def synchronise(connection: Connection) -> None:
        driver = connection.connection.driver_connection
        assert driver is not None
        assert connection.exec_driver_sql("PRAGMA busy_timeout").scalar() == 5000
        connections.append(driver)
        barrier.wait()

    with (
        before_sql("BEGIN IMMEDIATE", synchronise),
        sqlite3.connect(database) as owner,
        ThreadPoolExecutor(2) as workers,
    ):
        owner.execute("BEGIN IMMEDIATE")
        pending = [
            workers.submit(compile_config, path, database) for path in (first, second)
        ]
        try:
            barrier.wait()
        finally:
            owner.rollback()
        successes = []
        failures = []
        for future in pending:
            try:
                successes.append(future.result(timeout=10))
            except ConfigError as error:
                failures.append(str(error))
    assert len(connections) == 2 and connections[0] is not connections[1]
    if different_bytes:
        assert len(successes) == len(failures) == 1
        assert "声明版本已登记不同字节" in failures[0]
        assert "数据库忙" not in failures[0]
    else:
        assert not failures
        assert successes[0] == successes[1]
    saved = successes[0]
    assert load_config_snapshot(database, saved.snapshot_id) == saved
    assert tuple(len(rows) for rows in config_facts(database)) == (1, 1, 1)
    assert {p: p.read_bytes() for p in original} == original
    assert "PRIVATE_PROFILE_MARKER" not in caplog.text + "".join(failures)
    assert "PRIVATE_SECRET_MARKER" not in caplog.text + "".join(failures)


def test_replacing_source_after_read_does_not_change_committed_material(
    tmp_path: Path,
) -> None:
    settings = profile_inputs(tmp_path)
    database = tmp_path / "db.sqlite3"
    upgrade_database(database)
    profile = settings.parent / "profiles/profile-v1.yaml"
    original = profile.read_bytes()
    replacement = original.replace(b"PRIVATE_PROFILE_MARKER", b"EXTERNAL_REPLACEMENT")

    def replace_source(connection: Connection) -> None:
        temporary = profile.with_suffix(".replacement")
        temporary.write_bytes(replacement)
        temporary.replace(profile)

    with before_sql("BEGIN IMMEDIATE", replace_source):
        saved = compile_config(settings, database)
    assert profile.read_bytes() == replacement
    versions, _, _ = config_facts(database)
    assert versions[0][4] == original
    assert "PRIVATE_PROFILE_MARKER" in saved.payload_json
    assert "EXTERNAL_REPLACEMENT" not in saved.payload_json
    assert load_config_snapshot(database, saved.snapshot_id) == saved
    with pytest.raises(ConfigError, match="声明版本已登记不同字节"):
        compile_config(settings, database)
    assert profile.read_bytes() == replacement


@pytest.mark.parametrize("stage", ["snapshot", "references", "commit"])
@pytest.mark.parametrize("disconnect", [False, True])
def test_transaction_failure_preserves_history_and_allows_clean_rerun(
    tmp_path: Path,
    stage: str,
    disconnect: bool,
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings = profile_inputs(tmp_path)
    database = tmp_path / "db.sqlite3"
    upgrade_database(database)
    historical = compile_config(settings, database)
    before = config_facts(database)
    settings, prompt = recovery_inputs(tmp_path)
    inputs = {
        p: p.read_bytes() for p in (settings, prompt, *settings.parent.rglob("*.yaml"))
    }
    references = 0

    def fail(connection: Connection) -> None:
        nonlocal references
        if stage == "references":
            references += 1
            if references != 2:
                return
        if disconnect:
            driver = connection.connection.driver_connection
            assert driver is not None
            driver.close()
        else:
            connection.exec_driver_sql("SELECT PRIVATE_SECRET_MARKER")

    if stage == "commit":
        event.listen(Engine, "commit", fail)
        try:
            with pytest.raises(ConfigError, match="数据库写入失败") as failure:
                compile_config(settings, database)
        finally:
            event.remove(Engine, "commit", fail)
    else:
        prefix = {
            "snapshot": "INSERT INTO runtime_config_snapshots",
            "references": "INSERT INTO snapshot_version_refs",
        }[stage]
        with (
            before_sql(prefix, fail),
            pytest.raises(ConfigError, match="数据库写入失败") as failure,
        ):
            compile_config(settings, database)
    assert config_facts(database) == before
    assert load_config_snapshot(database, historical.snapshot_id) == historical
    recovered = compile_config(settings, database)
    assert load_config_snapshot(database, recovered.snapshot_id) == recovered
    assert load_config_snapshot(database, historical.snapshot_id) == historical
    assert tuple(len(rows) for rows in config_facts(database)) == (3, 2, 3)
    assert {p: p.read_bytes() for p in inputs} == inputs
    for marker in (
        "PRIVATE_PROFILE_MARKER",
        "PRIVATE_PROMPT_MARKER",
        "PRIVATE_SECRET_MARKER",
        "SELECT",
        "INSERT INTO",
    ):
        assert marker not in str(failure.value) + caplog.text


@pytest.mark.parametrize("new_snapshot", [False, True])
def test_missing_historical_version_is_rejected_without_repair(
    tmp_path: Path, new_snapshot: bool, caplog: pytest.LogCaptureFixture
) -> None:
    settings = profile_inputs(tmp_path)
    database = tmp_path / "db.sqlite3"
    upgrade_database(database)
    historical = compile_config(settings, database)
    with sqlite3.connect(database) as connection:
        # 模拟外部关闭外键检查后删除历史材料。编译不能从可变文件修复它。
        connection.execute("DELETE FROM config_versions")
    if new_snapshot:
        settings.write_text("profile: profile-v1\nread: read-v1\n", encoding="utf-8")
        (settings.parent / "read").mkdir()
        (settings.parent / "read/read-v1.yaml").write_text(
            "version: read-v1\nchunking_version: v1\n", encoding="utf-8"
        )
    before = config_facts(database)
    for operation in (check_config, compile_config):
        with pytest.raises(ConfigError, match="版本引用损坏"):
            operation(settings, database)
        assert config_facts(database) == before
    with pytest.raises(ConfigError, match="版本引用损坏"):
        load_config_snapshot(database, historical.snapshot_id)
    assert "PRIVATE_PROFILE_MARKER" not in caplog.text
