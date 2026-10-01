"""A2-04 新材料的原子登记、版本保护与重启回放。"""

from __future__ import annotations

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
from tests.config_reuse_support import reuse_inputs
from tests.config_test_support import run_cli


@pytest.mark.parametrize("material", ["escalation", "reuse_prompt"])
def test_registered_material_requires_new_version_after_restart(
    tmp_path: Path, material: str
) -> None:
    settings, db = reuse_inputs(tmp_path)
    saved = compile_config(settings, db)
    path = tmp_path / (
        "config/screening/reuse-escalation-v1.yaml"
        if material == "escalation"
        else "prompts/screening/reuse-v1.md"
    )
    path.write_bytes(path.read_bytes() + b"\n")
    args = ("--settings", str(settings), "--database", str(db))
    restarted = run_cli(tmp_path, "config", "compile", *args)
    assert restarted.returncode == 2
    assert "声明版本已登记不同字节" in restarted.stderr
    for operation in (check_config, compile_config):
        with pytest.raises(ConfigError, match="声明版本已登记不同字节"):
            operation(settings, db)
    assert load_config_snapshot(db, saved.snapshot_id) == saved
    if material == "escalation":
        (path.parent / "reuse-escalation-v2.yaml").write_bytes(
            path.read_bytes().replace(b"reuse-escalation-v1", b"reuse-escalation-v2")
        )
        settings.write_text(
            settings.read_text().replace("reuse-escalation-v1", "reuse-escalation-v2")
        )
    else:
        (path.parent / "reuse-v2.md").write_bytes(path.read_bytes())
        settings.write_text(settings.read_text().replace("  reuse: v1", "  reuse: v2"))
    newer = compile_config(settings, db)
    assert newer.snapshot_id != saved.snapshot_id
    assert load_config_snapshot(db, saved.snapshot_id) == saved
    assert load_config_snapshot(db, newer.snapshot_id) == newer


def test_all_reuse_materials_roll_back_when_snapshot_save_fails(tmp_path: Path) -> None:
    settings, db = reuse_inputs(tmp_path)
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
    assert load_config_snapshot(db, saved.snapshot_id) == saved


@pytest.mark.parametrize("contract", ["reuse-assessment", "decision-reasons"])
@pytest.mark.parametrize(
    "damage", ["missing", "manifest", "drift", "version", "unsupported"]
)
def test_contract_failure_preserves_inputs_and_never_partially_registers(
    tmp_path: Path, contract: str, damage: str
) -> None:
    settings, db = reuse_inputs(tmp_path)
    selector = contract.replace("-", "_")
    folder = tmp_path / "contracts/screening" / contract / "v1"
    if damage == "missing":
        (folder / "schema.json").unlink()
    elif damage == "manifest":
        (folder / "manifest.json").write_bytes(b"{}")
    elif damage == "unsupported":
        settings.write_text(
            settings.read_text().replace(f"{selector}: v1", f"{selector}: v2")
        )
    else:
        schema_path = folder / "schema.json"
        schema = json.loads(schema_path.read_bytes())
        if damage == "drift":
            schema["description"] = "secret-marker"
        else:
            schema["x-paper-radar-contract"]["version"] = "v2"
        schema_path.write_text(json.dumps(schema))
    before = {
        p: p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file() and p.suffix != ".sqlite3"
    }
    for operation in (check_config, compile_config):
        with pytest.raises(ConfigError, match=rf"contracts\.{selector}") as error:
            operation(settings, db)
        assert "secret-marker" not in str(error.value)
    assert {p: p.read_bytes() for p in before} == before
    with sqlite3.connect(db) as connection:
        assert connection.execute(
            "SELECT count(*) FROM config_versions"
        ).fetchone() == (0,)


def test_historical_reuse_snapshot_replays_in_new_process_without_input_files(
    tmp_path: Path,
) -> None:
    settings, db = reuse_inputs(tmp_path)
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
            "print(s.snapshot_id,s.stages['reuse'].status,"
            "s.stages['suggestion'].status,s.escalation.reuse_escalation_research_values)",
            str(db),
            saved.snapshot_id,
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"{saved.snapshot_id} ready ready (3,)"


@pytest.mark.parametrize(
    "kind", ["escalation", "prompt", "contract_schema", "contract_manifest"]
)
def test_corrupt_registered_reuse_bytes_do_not_fall_back_to_current_files(
    tmp_path: Path, kind: str
) -> None:
    settings, db = reuse_inputs(tmp_path)
    saved = compile_config(settings, db)
    with sqlite3.connect(db) as connection:
        connection.execute(
            "UPDATE config_versions SET raw_content = ? WHERE kind = ?",
            (b"secret-marker", kind),
        )
    with pytest.raises(ConfigError, match="损坏") as error:
        load_config_snapshot(db, saved.snapshot_id)
    assert "secret-marker" not in str(error.value)


def test_reuse_snapshot_is_independent_of_directory_and_does_not_rewrite_inputs(
    tmp_path: Path,
) -> None:
    settings, db = reuse_inputs(tmp_path)
    before = {
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
    saved = compile_config(settings, db)
    assert saved == checked
    assert {p: p.read_bytes() for p in before} == before
    moved = tmp_path / "moved"
    for folder in ("config", "prompts", "contracts"):
        shutil.copytree(tmp_path / folder, moved / folder)
    other_db = moved / "other.sqlite3"
    upgrade_database(other_db)
    assert compile_config(moved / "config/settings.yaml", other_db) == saved
