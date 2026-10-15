"""A2-09 真实安装入口的跨进程竞争、中断恢复及安全错误。"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

from paper_radar.config import compile_config, load_config_snapshot, upgrade_database
from tests.config_test_support import run_cli
from tests.config_transaction_support import (
    config_facts,
    paused_compile,
    profile_inputs,
    recovery_inputs,
)


@pytest.mark.parametrize("different_bytes", [False, True])
def test_installed_compilers_compete_with_deterministic_process_barrier(
    tmp_path: Path, different_bytes: bool
) -> None:
    first = profile_inputs(tmp_path / "first")
    second = profile_inputs(tmp_path / "second")
    if different_bytes:
        profile = second.parent / "profiles/profile-v1.yaml"
        profile.write_bytes(profile.read_bytes() + b"# PRIVATE_SECRET_MARKER\n")
    database = tmp_path / "db.sqlite3"
    upgrade_database(database)
    inputs = {p: p.read_bytes() for p in tmp_path.rglob("*.yaml")}
    with sqlite3.connect(database) as owner:
        owner.execute("BEGIN IMMEDIATE")
        with (
            paused_compile(first, database, pause_at="begin") as (one, release_one),
            paused_compile(second, database, pause_at="begin") as (two, release_two),
        ):
            os.write(release_one, b"G")
            os.write(release_two, b"G")
            owner.rollback()
            outputs = [p.communicate(timeout=15) for p in (one, two)]
            codes = [one.returncode, two.returncode]
    if different_bytes:
        assert sorted(codes) == [0, 2]
        assert "声明版本已登记不同字节" in outputs[codes.index(2)][1]
    else:
        assert codes == [0, 0], outputs
        assert outputs[0] == outputs[1]
    success_output = outputs[codes.index(0)][0]
    snapshot_id = success_output.splitlines()[0].split("：")[1]
    saved = load_config_snapshot(database, snapshot_id)
    assert saved.profile_status == "configured"
    facts = config_facts(database)
    assert tuple(len(rows) for rows in facts) == (1, 1, 1)
    winner = first if codes[0] == 0 else second
    repeated = run_cli(
        tmp_path,
        "config",
        "compile",
        "--settings",
        str(winner),
        "--database",
        str(database),
    )
    assert repeated.returncode == 0
    assert repeated.stdout == success_output
    assert config_facts(database) == facts
    assert {p: p.read_bytes() for p in inputs} == inputs
    combined = "".join(stdout + stderr for stdout, stderr in outputs)
    for marker in (
        "PRIVATE_PROFILE_MARKER",
        "PRIVATE_SECRET_MARKER",
        "Traceback",
        "INSERT INTO",
    ):
        assert marker not in combined


@pytest.mark.parametrize("pause_at", ["snapshot", "references", "commit"])
def test_killed_compile_rolls_back_every_fact_and_can_be_rerun(
    tmp_path: Path, pause_at: str
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
    with paused_compile(settings, database, pause_at=pause_at) as (process, _):
        # 读取连接在写事务中仍只能看到完整旧事实。
        assert config_facts(database) == before
        assert load_config_snapshot(database, historical.snapshot_id) == historical
        process.kill()
        stdout, stderr = process.communicate(timeout=10)
        assert process.returncode != 0
    assert not stdout + stderr
    assert config_facts(database) == before
    assert load_config_snapshot(database, historical.snapshot_id) == historical
    recovered = run_cli(
        tmp_path,
        "config",
        "compile",
        "--settings",
        str(settings),
        "--database",
        str(database),
    )
    assert recovered.returncode == 0, recovered.stderr
    snapshot_id = recovered.stdout.splitlines()[0].split("：")[1]
    assert load_config_snapshot(database, snapshot_id).profile_status == "configured"
    assert tuple(len(rows) for rows in config_facts(database)) == (3, 2, 3)
    assert load_config_snapshot(database, historical.snapshot_id) == historical
    assert {p: p.read_bytes() for p in inputs} == inputs
    for marker in ("PRIVATE_PROFILE_MARKER", "PRIVATE_PROMPT_MARKER"):
        assert marker not in recovered.stdout + recovered.stderr


def test_installed_compile_reports_busy_separately_from_conflict(
    tmp_path: Path,
) -> None:
    settings = profile_inputs(tmp_path)
    database = tmp_path / "db.sqlite3"
    upgrade_database(database)
    with sqlite3.connect(database) as owner:
        owner.execute("BEGIN IMMEDIATE")
        busy = run_cli(
            tmp_path,
            "config",
            "compile",
            "--settings",
            str(settings),
            "--database",
            str(database),
        )
    assert busy.returncode == 2
    assert "数据库忙（锁等待上限 5 秒）；请稍后重试" in busy.stderr
    assert "声明版本已登记不同字节" not in busy.stderr
    assert "PRIVATE_PROFILE_MARKER" not in busy.stdout + busy.stderr
    assert tuple(len(rows) for rows in config_facts(database)) == (0, 0, 0)


@pytest.mark.parametrize(
    "damage", ["database_error", "payload", "references", "version", "missing_version"]
)
def test_installed_compile_failure_is_redacted_and_does_not_repair_history(
    tmp_path: Path, damage: str
) -> None:
    settings = profile_inputs(tmp_path)
    database = tmp_path / "db.sqlite3"
    upgrade_database(database)
    compile_config(settings, database)
    with sqlite3.connect(database) as connection:
        if damage == "database_error":
            settings = profile_inputs(tmp_path, version="profile-v2")
            connection.execute(
                "CREATE TRIGGER fail_compile BEFORE INSERT ON runtime_config_snapshots "
                "BEGIN SELECT RAISE(ABORT, 'PRIVATE_SECRET_MARKER'); END"
            )
        elif damage == "payload":
            connection.execute(
                "UPDATE runtime_config_snapshots SET payload_json = ?",
                ("PRIVATE_PROMPT_MARKER",),
            )
        elif damage == "references":
            connection.execute("DELETE FROM snapshot_version_refs")
        elif damage == "missing_version":
            connection.execute("DELETE FROM config_versions")
        else:
            connection.execute(
                "UPDATE config_versions SET raw_content = ?",
                (b"PRIVATE_SECRET_MARKER",),
            )
    before = config_facts(database)
    inputs = {p: p.read_bytes() for p in tmp_path.rglob("*.yaml")}
    failed = run_cli(
        tmp_path,
        "config",
        "compile",
        "--settings",
        str(settings),
        "--database",
        str(database),
    )
    assert failed.returncode == 2
    assert "配置编译失败" in failed.stderr
    expected_reason = {
        "database_error": "数据库写入失败",
        "payload": "损坏",
        "references": "损坏",
        "version": "声明版本已登记不同字节",
        "missing_version": "版本引用损坏",
    }[damage]
    assert expected_reason in failed.stderr
    assert config_facts(database) == before
    assert {p: p.read_bytes() for p in inputs} == inputs
    for marker in (
        "PRIVATE_PROFILE_MARKER",
        "PRIVATE_PROMPT_MARKER",
        "PRIVATE_SECRET_MARKER",
        "Traceback",
        "INSERT INTO",
        "parameters:",
    ):
        assert marker not in failed.stdout + failed.stderr
