"""真实 SQLite 的期刊版本保护、事务回滚与历史回放。"""

import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from paper_radar.config import (
    ConfigError,
    check_config,
    compile_config,
    load_config_snapshot,
    upgrade_database,
)
from tests.config_journals_support import journal_inputs
from tests.config_test_support import run_cli


@pytest.mark.parametrize("change", ["tier", "name", "identifier", "comment"])
def test_journal_versions_cannot_be_overwritten_after_restart(
    tmp_path: Path, change: str
) -> None:
    settings, database = journal_inputs(tmp_path)
    saved = compile_config(settings, database)
    path = settings.parent / "journals/journals-v1.yaml"
    original = path.read_bytes()
    changed = {
        "tier": original.replace(b"preferred", b"low"),
        "name": original.replace("电子期刊".encode(), b"New name"),
        "identifier": original.replace(b"2769-7525", b"0148-0227"),
        "comment": original + b"# private comment\n",
    }[change]
    path.write_bytes(changed)
    result = run_cli(
        tmp_path,
        "config",
        "compile",
        "--settings",
        str(settings),
        "--database",
        str(database),
    )
    assert result.returncode == 2
    assert "声明版本已登记不同字节" in result.stderr
    for operation in (check_config, compile_config):
        with pytest.raises(ConfigError, match="声明版本已登记不同字节"):
            operation(settings, database)
    assert load_config_snapshot(database, saved.snapshot_id) == saved
    new_bytes = changed.replace(b"journals-v1", b"journals-v2")
    path.with_name("journals-v2.yaml").write_bytes(new_bytes)
    path.write_bytes(original)
    settings.write_text(settings.read_text().replace("journals-v1", "journals-v2"))
    newer = compile_config(settings, database)
    assert newer.snapshot_id != saved.snapshot_id
    assert newer.stages == saved.stages
    assert newer.enabled_topics == saved.enabled_topics
    assert newer.adapters == saved.adapters
    assert newer.read == saved.read
    assert newer.extraction == saved.extraction
    assert newer.escalation == saved.escalation
    for snapshot in (saved, newer):
        assert load_config_snapshot(database, snapshot.snapshot_id) == snapshot
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT declared_version, raw_content FROM config_versions "
            "WHERE kind = 'journals' ORDER BY declared_version"
        ).fetchall() == [("journals-v1", original), ("journals-v2", new_bytes)]
        assert connection.execute(
            "SELECT count(*) FROM runtime_config_snapshots"
        ).fetchone() == (2,)


def test_journal_material_registration_rolls_back_and_retry_is_idempotent(
    tmp_path: Path,
) -> None:
    settings, database = journal_inputs(tmp_path)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TRIGGER fail_snapshot BEFORE INSERT ON runtime_config_snapshots "
            "BEGIN SELECT RAISE(ABORT, 'PRIVATE_MARKER'); END"
        )
    with pytest.raises(ConfigError, match="已回滚") as error:
        compile_config(settings, database)
    assert "PRIVATE_MARKER" not in str(error.value)
    with sqlite3.connect(database) as connection:
        for table in (
            "config_versions",
            "runtime_config_snapshots",
            "snapshot_version_refs",
        ):
            assert connection.execute(f"SELECT count(*) FROM {table}").fetchone() == (
                0,
            )
        connection.execute("DROP TRIGGER fail_snapshot")
    saved = compile_config(settings, database)
    assert compile_config(settings, database) == saved
    assert load_config_snapshot(database, saved.snapshot_id) == saved
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT count(*) FROM runtime_config_snapshots"
        ).fetchone() == (1,)
        assert connection.execute(
            "SELECT count(*) FROM config_versions WHERE kind = 'journals'"
        ).fetchone() == (1,)


def test_journal_check_is_read_only_and_identity_is_directory_independent(
    tmp_path: Path,
) -> None:
    settings, database = journal_inputs(tmp_path)
    files = {
        p: p.read_bytes()
        for folder in ("config", "prompts", "contracts")
        for p in (tmp_path / folder).rglob("*")
        if p.is_file()
    }
    checked = check_config(settings, database)
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT count(*) FROM config_versions"
        ).fetchone() == (0,)
    saved = compile_config(settings, database)
    assert saved == checked
    assert {p: p.read_bytes() for p in files} == files
    moved = tmp_path / "moved"
    for folder in ("config", "prompts", "contracts"):
        shutil.copytree(tmp_path / folder, moved / folder)
    other_database = moved / "db.sqlite3"
    upgrade_database(other_database)
    assert compile_config(moved / "config/settings.yaml", other_database) == saved


def test_journal_snapshot_replays_without_source_files_in_new_process(
    tmp_path: Path,
) -> None:
    settings, database = journal_inputs(tmp_path)
    saved = compile_config(settings, database)
    for folder in ("config", "prompts", "contracts"):
        shutil.rmtree(tmp_path / folder)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from pathlib import Path; import sys; "
            "from paper_radar.config import load_config_snapshot; "
            "s=load_config_snapshot(Path(sys.argv[1]),sys.argv[2]); "
            "print(s.snapshot_id,s.journals_status,"
            "','.join(j.issn_l for j in s.journals))",
            str(database),
            saved.snapshot_id,
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == (
        f"{saved.snapshot_id} configured 0035-9009,1006-9895,2169-897X,2769-7525"
    )


@pytest.mark.parametrize("damage", ["raw", "hash", "reference"])
def test_damaged_journal_history_fails_without_source_fallback(
    tmp_path: Path, damage: str
) -> None:
    settings, database = journal_inputs(tmp_path)
    saved = compile_config(settings, database)
    with sqlite3.connect(database) as connection:
        if damage == "raw":
            connection.execute(
                "UPDATE config_versions SET raw_content = ? WHERE kind = 'journals'",
                (b"PRIVATE_MARKER",),
            )
        elif damage == "hash":
            connection.execute(
                "UPDATE config_versions SET raw_sha256 = ? WHERE kind = 'journals'",
                ("0" * 64,),
            )
        else:
            connection.execute(
                "DELETE FROM snapshot_version_refs WHERE kind = 'journals'"
            )
    with pytest.raises(ConfigError, match="损坏") as error:
        load_config_snapshot(database, saved.snapshot_id)
    assert "PRIVATE_MARKER" not in str(error.value)
