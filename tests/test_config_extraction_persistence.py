"""正文提取声明的真实 SQLite 版本登记、原子性和历史回放。"""

import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from paper_radar.config import (
    ConfigError,
    StageName,
    check_config,
    compile_config,
    load_config_snapshot,
    upgrade_database,
)
from tests.config_extraction_support import extraction_inputs
from tests.config_reuse_support import reuse_inputs
from tests.config_test_support import run_cli


def test_registered_extraction_bytes_require_new_version_after_restart(
    tmp_path: Path,
) -> None:
    settings, path, db = extraction_inputs(tmp_path)
    first = compile_config(settings, db)
    path.write_bytes(path.read_bytes() + b"# comment-only change\n")
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
    with pytest.raises(ConfigError, match="声明版本已登记不同字节"):
        check_config(settings, db)
    raw = path.read_text().replace("extraction-v1", "extraction-v2")
    (path.parent / "extraction-v2.yaml").write_text(raw)
    settings.write_text("extraction: extraction-v2\n")
    restarted = run_cli(
        tmp_path,
        "config",
        "compile",
        "--settings",
        str(settings),
        "--database",
        str(db),
    )
    assert restarted.returncode == 0, restarted.stderr
    second_id = restarted.stdout.splitlines()[0].split("：")[1]
    second = load_config_snapshot(db, second_id)
    assert second.snapshot_id != first.snapshot_id
    assert second.extraction == first.extraction
    assert load_config_snapshot(db, first.snapshot_id) == first
    assert load_config_snapshot(db, second.snapshot_id) == second


def test_history_replays_without_input_files_in_another_process(tmp_path: Path) -> None:
    settings, _, db = extraction_inputs(tmp_path)
    first = compile_config(settings, db)
    shutil.rmtree(tmp_path / "config")
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from pathlib import Path; import sys; "
            "from paper_radar.config import load_config_snapshot; "
            "s=load_config_snapshot(Path(sys.argv[1]),sys.argv[2]); "
            "print(s.snapshot_id,s.stages['extraction'].status,"
            "s.extraction.backend.backend_id,s.extraction.normalization_version)",
            str(db),
            first.snapshot_id,
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"{first.snapshot_id} ready docling v1"


def test_extraction_is_directory_independent_and_check_never_registers(
    tmp_path: Path,
) -> None:
    settings, path, db = extraction_inputs(tmp_path)
    before = {path: path.read_bytes(), settings: settings.read_bytes()}
    checked = check_config(settings, db)
    with sqlite3.connect(db) as connection:
        assert connection.execute(
            "SELECT count(*) FROM config_versions"
        ).fetchone() == (0,)
    saved = compile_config(settings, db)
    assert saved == checked
    assert {file: file.read_bytes() for file in before} == before
    other = tmp_path / "other"
    shutil.copytree(tmp_path / "config", other / "config")
    other_db = other / "db.sqlite3"
    upgrade_database(other_db)
    assert compile_config(other / "config/settings.yaml", other_db) == saved


def test_snapshot_failure_rolls_back_extraction_and_other_new_materials(
    tmp_path: Path,
) -> None:
    settings, db = reuse_inputs(tmp_path)
    other_settings, path, _ = extraction_inputs(tmp_path / "extraction-input")
    shutil.copytree(path.parent, settings.parent / "extraction")
    settings.write_text(settings.read_text() + other_settings.read_text())
    with sqlite3.connect(db) as connection:
        connection.execute(
            "CREATE TRIGGER fail_snapshot BEFORE INSERT ON runtime_config_snapshots "
            "BEGIN SELECT RAISE(ABORT, 'PRIVATE_MARKER'); END"
        )
    with pytest.raises(ConfigError, match="已回滚") as error:
        compile_config(settings, db)
    assert "PRIVATE_MARKER" not in str(error.value)
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
    assert load_config_snapshot(db, saved.snapshot_id) == saved


def test_extraction_does_not_embed_reuse_or_read_semantics(tmp_path: Path) -> None:
    settings, db = reuse_inputs(tmp_path)
    first = compile_config(settings, db)
    other_settings, path, _ = extraction_inputs(tmp_path / "extraction-input")
    shutil.copytree(path.parent, settings.parent / "extraction")
    settings.write_text(settings.read_text() + other_settings.read_text())
    second = compile_config(settings, db)
    assert first.snapshot_id != second.snapshot_id
    assert first.escalation == second.escalation
    assert first.stages[StageName.REUSE] == second.stages[StageName.REUSE]
    old = json.loads(first.payload_json)["materials"]
    new = json.loads(second.payload_json)["materials"]
    assert old == [material for material in new if material["kind"] != "extraction"]


@pytest.mark.parametrize("damage", ["bytes", "reference", "effective_config"])
def test_corrupted_history_never_falls_back_to_current_files(
    tmp_path: Path,
    damage: str,
) -> None:
    settings, _, db = extraction_inputs(tmp_path)
    saved = compile_config(settings, db)
    with sqlite3.connect(db) as connection:
        if damage == "bytes":
            connection.execute(
                "UPDATE config_versions SET raw_content = ? WHERE kind = 'extraction'",
                (b"PRIVATE_MARKER",),
            )
        elif damage == "reference":
            connection.execute(
                "DELETE FROM snapshot_version_refs WHERE kind = 'extraction'"
            )
        else:
            connection.execute(
                "UPDATE runtime_config_snapshots SET payload_json = "
                "replace(payload_json, 'float32', 'PRIVATE_MARKER')"
            )
    with pytest.raises(ConfigError, match="损坏") as error:
        load_config_snapshot(db, saved.snapshot_id)
    assert "PRIVATE_MARKER" not in str(error.value)
