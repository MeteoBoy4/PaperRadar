"""真实临时 SQLite 上的精确字节登记、幂等、回放与回滚。"""

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
from tests.config_adapter_support import SYSTEM_PROMPT, adapter_inputs
from tests.config_test_support import run_cli


def registry_state(db: Path) -> tuple[list[tuple[object, ...]], ...]:
    with sqlite3.connect(db) as connection:
        return tuple(
            connection.execute(f"SELECT * FROM {table} ORDER BY 1, 2").fetchall()
            for table in (
                "config_versions",
                "runtime_config_snapshots",
                "snapshot_version_refs",
            )
        )


def test_check_is_read_only_compile_is_idempotent_and_registration_is_exact(
    tmp_path: Path,
) -> None:
    settings, path, db = adapter_inputs(tmp_path)
    originals = {p: p.read_bytes() for p in settings.parent.rglob("*") if p.is_file()}
    empty = registry_state(db)
    checked = check_config(settings, db)
    assert registry_state(db) == empty
    saved = compile_config(settings, db)
    assert saved == checked
    registered = registry_state(db)
    assert compile_config(settings, db) == saved
    assert check_config(settings, db) == saved
    assert registry_state(db) == registered
    assert {p: p.read_bytes() for p in originals} == originals
    versions = {(row[0], row[1], row[2]): row for row in registered[0]}
    assert versions[("adapter", "pi-rpc", "pi-v1")][4] == path.read_bytes()
    assert versions[("prompt", "pi-system", "v1")][4] == SYSTEM_PROMPT
    assert ("prompt", "boundary", "v1") in versions


def test_history_replays_after_selector_changes_and_sources_disappear(
    tmp_path: Path,
) -> None:
    settings, _, db = adapter_inputs(tmp_path)
    first = compile_config(settings, db)
    settings.write_text("{}\n")
    assert compile_config(settings, db).snapshot_id != first.snapshot_id
    shutil.rmtree(settings.parent)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from pathlib import Path; import sys; "
            "from paper_radar.config import load_config_snapshot; "
            "s=load_config_snapshot(Path(sys.argv[1]),sys.argv[2]); "
            "print(s.snapshot_id,s.adapters['reading'].semantics_id)",
            str(db),
            first.snapshot_id,
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == (
        f"{first.snapshot_id} "
        "8f27d5f34c1d940ad3e95b8ab6de2f50eb2177e91ed63fd250d763b4f72ba6e8"
    )
    assert load_config_snapshot(db, first.snapshot_id) == first


def test_adapter_comment_only_conflict_is_rejected_after_restart(
    tmp_path: Path,
) -> None:
    settings, path, db = adapter_inputs(tmp_path)
    saved = compile_config(settings, db)
    before = registry_state(db)
    path.write_bytes(path.read_bytes() + b"# PRIVATE_MARKER\n")
    result = run_cli(
        tmp_path,
        "config",
        "compile",
        "--settings",
        str(settings),
        "--database",
        str(db),
    )
    assert result.returncode == 2
    assert "声明版本已登记不同字节" in result.stderr
    assert "PRIVATE_MARKER" not in result.stderr + result.stdout
    assert registry_state(db) == before
    assert load_config_snapshot(db, saved.snapshot_id) == saved


def test_prompt_conflict_rolls_back_new_adapter_version(tmp_path: Path) -> None:
    settings, path, db = adapter_inputs(tmp_path)
    saved = compile_config(settings, db)
    before = registry_state(db)
    (settings.parent / "prompts/pi-system-v1.md").write_bytes(b"New system prompt\n")
    (path.parent / "pi-v2.yaml").write_text(
        path.read_text()
        .replace("version: pi-v1", "version: pi-v2")
        .replace(
            "212c2cd595c12aaf7ca2a4b6783b3f43f85ce077745c2a55f4f18d6c07b9e2d1",
            "373122be9e3bc17657d9d300e89131e9ed013179bc459fe377cd1888a6895cad",
        )
    )
    settings.write_text(settings.read_text().replace("pi-v1", "pi-v2"))
    with pytest.raises(ConfigError, match=r"prompt\.pi-system\.v1.*不同字节"):
        compile_config(settings, db)
    assert registry_state(db) == before
    assert load_config_snapshot(db, saved.snapshot_id) == saved


@pytest.mark.parametrize("table", ["runtime_config_snapshots", "snapshot_version_refs"])
def test_persistence_failure_rolls_back_all_new_materials_and_references(
    tmp_path: Path, table: str
) -> None:
    settings, _, db = adapter_inputs(tmp_path)
    before = registry_state(db)
    with sqlite3.connect(db) as connection:
        connection.execute(
            f"CREATE TRIGGER fail_insert BEFORE INSERT ON {table} "
            "BEGIN SELECT RAISE(ABORT, 'PRIVATE_MARKER'); END"
        )
    with pytest.raises(ConfigError, match="已回滚") as error:
        compile_config(settings, db)
    assert "PRIVATE_MARKER" not in str(error.value)
    assert registry_state(db) == before
    with sqlite3.connect(db) as connection:
        connection.execute("DROP TRIGGER fail_insert")
    saved = compile_config(settings, db)
    assert load_config_snapshot(db, saved.snapshot_id) == saved


@pytest.mark.parametrize(
    "damage", ["adapter_bytes", "prompt_bytes", "reference", "payload"]
)
def test_corrupted_history_fails_without_falling_back_to_current_files(
    tmp_path: Path, damage: str
) -> None:
    settings, _, db = adapter_inputs(tmp_path)
    saved = compile_config(settings, db)
    with sqlite3.connect(db) as connection:
        if damage.endswith("bytes"):
            kind, name = (
                ("adapter", "pi-rpc")
                if damage == "adapter_bytes"
                else ("prompt", "pi-system")
            )
            connection.execute(
                "UPDATE config_versions SET raw_content = ? "
                "WHERE kind = ? AND name = ?",
                (b"PRIVATE_MARKER", kind, name),
            )
        elif damage == "reference":
            connection.execute(
                "DELETE FROM snapshot_version_refs WHERE kind = 'adapter'"
            )
        else:
            connection.execute(
                "UPDATE runtime_config_snapshots SET payload_json = "
                "replace(payload_json, 'transport-v1', 'PRIVATE_MARKER')"
            )
    with pytest.raises(ConfigError, match="损坏") as error:
        load_config_snapshot(db, saved.snapshot_id)
    assert "PRIVATE_MARKER" not in str(error.value)


def test_adapter_identity_is_independent_of_directory_and_database(
    tmp_path: Path,
) -> None:
    settings, _, db = adapter_inputs(tmp_path)
    original = compile_config(settings, db)
    other_root = tmp_path / "moved"
    shutil.copytree(settings.parent, other_root / "config")
    shutil.copytree(tmp_path / "prompts", other_root / "prompts")
    shutil.copytree(tmp_path / "contracts", other_root / "contracts")
    other_db = other_root / "db.sqlite3"
    upgrade_database(other_db)
    assert compile_config(other_root / "config/settings.yaml", other_db) == original
