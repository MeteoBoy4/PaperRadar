"""Read 材料的不可变登记、回滚和跨进程历史回放。"""

import json
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
from paper_radar.config.compile import StageName
from tests.config_read_support import read_inputs
from tests.config_test_support import run_cli


@pytest.mark.parametrize("material", ["models", "read", "prompt"])
def test_read_materials_require_new_versions_after_restart(
    tmp_path: Path, material: str
) -> None:
    settings, db = read_inputs(tmp_path)
    saved = compile_config(settings, db)
    relative, old, new = {
        "models": ("config/models/models-v1.yaml", "models-v1", "models-v2"),
        "read": ("config/read/read-v1.yaml", "read-v1", "read-v2"),
        "prompt": ("prompts/reading/v1.md", "v1", "v2"),
    }[material]
    path = tmp_path / relative
    original = path.read_bytes()
    changed = original + b"\n"
    if material == "models":
        changed = changed.replace(b"read-model", b"new-read-model")
    path.write_bytes(changed)
    restarted = run_cli(
        tmp_path,
        "config",
        "compile",
        "--settings",
        str(settings),
        "--database",
        str(db),
    )
    assert restarted.returncode == 2
    assert "声明版本已登记不同字节" in restarted.stderr
    for operation in (check_config, compile_config):
        with pytest.raises(ConfigError, match="声明版本已登记不同字节"):
            operation(settings, db)
    assert load_config_snapshot(db, saved.snapshot_id) == saved
    newer_path = path.with_name(path.name.replace(old, new))
    newer_path.write_bytes(
        changed if material == "prompt" else changed.replace(old.encode(), new.encode())
    )
    path.write_bytes(original)
    settings.write_text(
        settings.read_text().replace("  reading: v1", "  reading: v2")
        if material == "prompt"
        else settings.read_text().replace(old, new)
    )
    newer = compile_config(settings, db)
    assert newer.snapshot_id != saved.snapshot_id
    for stage in (StageName.BOUNDARY, StageName.VALUE, StageName.REUSE):
        assert newer.stages[stage] == saved.stages[stage]
    assert newer.read == saved.read
    assert load_config_snapshot(db, saved.snapshot_id) == saved
    assert load_config_snapshot(db, newer.snapshot_id) == newer
    for snapshot in (saved, newer):
        payload = json.loads(snapshot.payload_json)
        entries = {m["name"]: m["config"] for m in payload["materials"]}
        assert entries["models"]["screening"]["model"] == "real-model"
        assert entries["reading"]["text"] == (
            "Synthetic Read business prompt\n\n"
            if material == "prompt" and snapshot == newer
            else "Synthetic Read business prompt\n"
        )
        assert entries["models"]["reading"]["model"] == (
            "new-read-model"
            if material == "models" and snapshot == newer
            else "read-model"
        )


def test_all_read_materials_roll_back_and_retry_idempotently(tmp_path: Path) -> None:
    settings, db = read_inputs(tmp_path)
    with sqlite3.connect(db) as connection:
        connection.execute(
            "CREATE TRIGGER fail_snapshot BEFORE INSERT ON runtime_config_snapshots "
            "BEGIN SELECT RAISE(ABORT, 'secret-marker'); END"
        )
    with pytest.raises(ConfigError, match="已回滚") as error:
        compile_config(settings, db)
    assert "secret-marker" not in str(error.value)
    with sqlite3.connect(db) as connection:
        for table in (
            "config_versions",
            "runtime_config_snapshots",
            "snapshot_version_refs",
        ):
            assert connection.execute(f"SELECT count(*) FROM {table}").fetchone() == (
                0,
            )
        connection.execute("DROP TRIGGER fail_snapshot")
    saved = compile_config(settings, db)
    assert compile_config(settings, db) == saved
    with sqlite3.connect(db) as connection:
        assert connection.execute(
            "SELECT count(*) FROM runtime_config_snapshots"
        ).fetchone() == (1,)
        assert connection.execute(
            "SELECT count(*) FROM config_versions"
        ).fetchone() == (7,)


def test_read_history_replays_after_files_removed_in_a_new_process(
    tmp_path: Path,
) -> None:
    settings, db = read_inputs(tmp_path)
    saved = compile_config(settings, db)
    for folder in ("config", "prompts", "contracts"):
        shutil.rmtree(tmp_path / folder)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from pathlib import Path; import sys; "
            "from paper_radar.config import load_config_snapshot; "
            "s=load_config_snapshot(Path(sys.argv[1]),sys.argv[2]); "
            "print(s.snapshot_id,s.read.chunking_version,"
            "s.stages['read'].status,','.join(s.stages['read'].missing))",
            str(db),
            saved.snapshot_id,
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"{saved.snapshot_id} v1 not_ready read_contract"
    assert load_config_snapshot(db, saved.snapshot_id) == saved


@pytest.mark.parametrize("kind", ["read", "prompt"])
def test_damaged_registered_read_bytes_never_use_current_files(
    tmp_path: Path, kind: str
) -> None:
    settings, db = read_inputs(tmp_path)
    saved = compile_config(settings, db)
    with sqlite3.connect(db) as connection:
        connection.execute(
            "UPDATE config_versions SET raw_content = ? WHERE kind = ?",
            (b"secret-marker", kind),
        )
    with pytest.raises(ConfigError, match="损坏") as error:
        load_config_snapshot(db, saved.snapshot_id)
    assert "secret-marker" not in str(error.value)


def test_read_snapshot_is_directory_independent_and_check_is_read_only(
    tmp_path: Path,
) -> None:
    settings, db = read_inputs(tmp_path)
    files = {
        p: p.read_bytes()
        for folder in ("config", "prompts", "contracts")
        for p in (tmp_path / folder).rglob("*")
        if p.is_file()
    }
    checked = check_config(settings, db)
    with sqlite3.connect(db) as connection:
        assert connection.execute(
            "SELECT count(*) FROM config_versions"
        ).fetchone() == (0,)
    assert compile_config(settings, db) == checked
    assert {p: p.read_bytes() for p in files} == files
    moved = tmp_path / "moved"
    for folder in ("config", "prompts", "contracts"):
        shutil.copytree(tmp_path / folder, moved / folder)
    moved_db = moved / "other.sqlite3"
    upgrade_database(moved_db)
    assert compile_config(moved / "config/settings.yaml", moved_db) == checked


def test_identical_read_prompt_bytes_can_have_distinct_declared_versions(
    tmp_path: Path,
) -> None:
    settings, db = read_inputs(tmp_path)
    saved = compile_config(settings, db)
    prompt = tmp_path / "prompts/reading/v1.md"
    (prompt.parent / "v2.md").write_bytes(prompt.read_bytes())
    settings.write_text(settings.read_text().replace("  reading: v1", "  reading: v2"))
    newer = compile_config(settings, db)
    assert newer.snapshot_id != saved.snapshot_id
    assert load_config_snapshot(db, saved.snapshot_id) == saved
    assert load_config_snapshot(db, newer.snapshot_id) == newer
