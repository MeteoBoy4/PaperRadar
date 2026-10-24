"""Read 冻结契约的显式配置准入及历史回放。"""

import hashlib
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
    compare_config_snapshots,
    compile_config,
    diff_config_snapshots,
    list_config_snapshots,
    load_config_snapshot,
    project_config,
)
from tests.contract_snapshot_support import canonical_json_bytes
from tests.read_config_support import read_contract_inputs


def test_explicit_read_contract_makes_complete_configuration_ready(
    tmp_path: Path,
) -> None:
    settings, database = read_contract_inputs(tmp_path)

    checked = check_config(settings, database)
    assert checked.stages[StageName.READ].status == "ready"
    assert checked.stages[StageName.READ].missing == ()
    saved = compile_config(settings, database)
    assert saved == checked
    assert compile_config(settings, database) == saved
    assert load_config_snapshot(database, saved.snapshot_id) == saved


def test_read_contract_only_changes_read_projection_and_contract_identities(
    tmp_path: Path,
) -> None:
    settings, database = read_contract_inputs(tmp_path)
    selected = settings.read_text()
    settings.write_text(selected.replace("  read: v1\n", ""))
    old = compile_config(settings, database)
    settings.write_text(selected)
    new = compile_config(settings, database)

    before, after = project_config(old), project_config(new)
    assert old.stages[StageName.READ].missing == ("read_contract",)
    assert new.stages[StageName.READ].missing == ()
    assert before.baseline == after.baseline
    assert [
        stage
        for stage in StageName
        if before.projections[stage] != after.projections[stage]
    ] == [StageName.READ]
    result = compare_config_snapshots(old, new)
    assert [item.category.value for item in result.identity_changes] == [
        "contract_manifest.read",
        "contract_schema.read",
    ]
    assert [item.stage for item in result.projection_changes] == [StageName.READ]
    assert not result.calibration_changed
    assert diff_config_snapshots(database, old.snapshot_id, new.snapshot_id) == result


@pytest.mark.parametrize("selection", ["missing", "null"])
def test_unselected_read_contract_does_not_change_old_snapshot_identity(
    tmp_path: Path, selection: str
) -> None:
    settings, database = read_contract_inputs(tmp_path)
    settings.write_text(settings.read_text().replace("  read: v1\n", ""))
    old = compile_config(settings, database)
    if selection == "null":
        settings.write_text(
            settings.read_text().replace("contracts:\n", "contracts:\n  read: null\n")
        )
    current = compile_config(settings, database)
    assert current == old
    assert project_config(current) == project_config(old)
    assert current.stages[StageName.READ].missing == ("read_contract",)
    assert (
        json.loads(project_config(current).projections[StageName.READ].payload_json)[
            "components"
        ]["contract"]
        is None
    )


@pytest.mark.parametrize(
    ("damage", "reason"),
    [
        ("missing_schema", "missing_snapshot"),
        ("missing_manifest", "missing_snapshot"),
        ("bad_hash", "damaged_snapshot"),
        ("bad_pair", "version_mismatch"),
        ("schema_drift", "content_drift"),
        ("handwritten", "content_drift"),
        ("wrong_version", "所选版本尚无权威契约"),
        ("invalid_version", "settings.contracts.read"),
    ],
)
def test_read_contract_damage_is_controlled_and_never_partly_registered(
    tmp_path: Path, damage: str, reason: str
) -> None:
    settings, database = read_contract_inputs(tmp_path)
    folder = tmp_path / "contracts/read/read/v1"
    if damage.startswith("missing_"):
        (folder / f"{damage.removeprefix('missing_')}.json").unlink()
    elif damage in ("wrong_version", "invalid_version"):
        settings.write_text(
            settings.read_text().replace(
                "  read: v1",
                "  read: v2"
                if damage == "wrong_version"
                else "  read: ../PRIVATE_MARKER",
            )
        )
    else:
        manifest = json.loads((folder / "manifest.json").read_bytes())
        if damage == "bad_hash":
            manifest["schema_sha256"] = "0" * 64
        elif damage == "bad_pair":
            manifest["contract"] = "boundary"
        else:
            schema = json.loads((folder / "schema.json").read_bytes())
            if damage == "handwritten":
                schema = {
                    "type": "object",
                    "title": "PRIVATE_MARKER",
                    "x-paper-radar-contract": {"name": "read", "version": "v1"},
                }
            else:
                schema["description"] = "PRIVATE_MARKER"
            raw = canonical_json_bytes(schema)
            (folder / "schema.json").write_bytes(raw)
            manifest["schema_sha256"] = hashlib.sha256(raw).hexdigest()
        (folder / "manifest.json").write_bytes(canonical_json_bytes(manifest))
    for operation in (check_config, compile_config):
        with pytest.raises(ConfigError, match=reason) as captured:
            operation(settings, database)
        assert "PRIVATE_MARKER" not in str(captured.value)
    assert list_config_snapshots(database) == ()
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT count(*) FROM config_versions"
        ).fetchone() == (0,)


def test_read_check_is_read_only_and_new_materials_are_visible_in_summary(
    tmp_path: Path,
) -> None:
    settings, database = read_contract_inputs(tmp_path)
    files = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    checked = check_config(settings, database)
    assert list_config_snapshots(database) == ()
    assert {path: path.read_bytes() for path in files} == files
    saved = compile_config(settings, database)
    assert checked == saved
    (summary,) = list_config_snapshots(database)
    assert {
        (version.kind.value, version.name, version.version)
        for version in summary.versions
        if version.name == "read"
    } == {
        ("read", "read", "read-v1"),
        ("contract_schema", "read", "v1"),
        ("contract_manifest", "read", "v1"),
    }
    read_materials = [
        material for material in saved.materials.values() if material.name == "read"
    ]
    assert len(read_materials) == 3
    assert len({material.raw_sha256 for material in read_materials}) == 3


def test_read_contract_registration_rolls_back_with_snapshot_failure(
    tmp_path: Path,
) -> None:
    settings, database = read_contract_inputs(tmp_path)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TRIGGER fail_read_snapshot BEFORE INSERT "
            "ON runtime_config_snapshots "
            "BEGIN SELECT RAISE(ABORT, 'PRIVATE_MARKER'); END"
        )
    with pytest.raises(ConfigError, match="已回滚") as captured:
        compile_config(settings, database)
    assert "PRIVATE_MARKER" not in str(captured.value)
    with sqlite3.connect(database) as connection:
        for table in (
            "config_versions",
            "runtime_config_snapshots",
            "snapshot_version_refs",
        ):
            assert connection.execute(f"SELECT count(*) FROM {table}").fetchone() == (
                0,
            )
        connection.execute("DROP TRIGGER fail_read_snapshot")
    saved = compile_config(settings, database)
    assert compile_config(settings, database) == saved


def test_read_contract_history_loads_without_current_files_in_new_process(
    tmp_path: Path,
) -> None:
    settings, database = read_contract_inputs(tmp_path)
    saved = compile_config(settings, database)
    semantics = project_config(saved)
    for name in ("config", "contracts", "prompts"):
        shutil.rmtree(tmp_path / name)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from pathlib import Path; import json,sys; "
            "from paper_radar.config import load_config_snapshot,project_config; "
            "s=load_config_snapshot(Path(sys.argv[1]),sys.argv[2]); "
            "p=project_config(s); "
            "print(json.dumps([s.snapshot_id,s.stages['read'].status,"
            "p.projections['read'].projection_id,p.baseline.baseline_id]))",
            str(database),
            saved.snapshot_id,
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [
        saved.snapshot_id,
        "ready",
        semantics.projections[StageName.READ].projection_id,
        semantics.baseline.baseline_id,
    ]
    assert load_config_snapshot(database, saved.snapshot_id) == saved


@pytest.mark.parametrize("kind", ["contract_schema", "contract_manifest"])
@pytest.mark.parametrize("damage", ["raw", "missing_reference"])
def test_read_contract_history_rejects_damage_without_current_file_fallback(
    tmp_path: Path, kind: str, damage: str
) -> None:
    settings, database = read_contract_inputs(tmp_path)
    saved = compile_config(settings, database)
    with sqlite3.connect(database) as connection:
        if damage == "raw":
            connection.execute(
                "UPDATE config_versions SET raw_content=? WHERE kind=? AND name='read'",
                (b"PRIVATE_MARKER", kind),
            )
        else:
            connection.execute(
                "DELETE FROM snapshot_version_refs WHERE kind=? AND name='read'",
                (kind,),
            )
    with pytest.raises(ConfigError, match="损坏") as captured:
        load_config_snapshot(database, saved.snapshot_id)
    assert "PRIVATE_MARKER" not in str(captured.value)


@pytest.mark.parametrize(
    ("slot", "reason"),
    [
        ("profile", "profile"),
        ("model", "read_model"),
        ("model_placeholder", "read_model_placeholder"),
        ("prompt", "read_prompt"),
        ("prompt_placeholder", "read_prompt_placeholder"),
        ("chunking", "chunking_version"),
        ("adapter_placeholder", "read_adapter_prompt_placeholder"),
    ],
)
def test_selected_read_contract_preserves_other_slot_requirements(
    tmp_path: Path, slot: str, reason: str
) -> None:
    settings, database = read_contract_inputs(tmp_path)
    text = settings.read_text()
    if slot == "profile":
        settings.write_text(text.replace("profile: profile-v1\n", ""))
    elif slot in ("model", "model_placeholder"):
        models = settings.parent / "models/models-v1.yaml"
        content = models.read_text()
        models.write_text(
            content.split("reading:")[0] + "reading: null\n"
            if slot == "model"
            else content.replace("read-model", "REQUIRED_FOR_READ")
        )
    elif slot == "prompt":
        settings.write_text(text.replace("  reading: v1\n", ""))
    elif slot == "prompt_placeholder":
        (tmp_path / "prompts/reading/v1.md").write_text("...\n")
    elif slot == "chunking":
        settings.write_text(text.replace("read: read-v1\n", ""))
    else:
        (settings.parent / "adapters").mkdir()
        (settings.parent / "prompts").mkdir()
        prompt = b"...\n"
        (settings.parent / "prompts/pi-system-v1.md").write_bytes(prompt)
        (settings.parent / "adapters/pi-v1.yaml").write_text(
            "version: pi-v1\npi_version: 1.1.0\nadapter_version: transport-v1\n"
            "thinking_level: low\nresources:\n  - version: v1\n"
            f"    sha256: {hashlib.sha256(prompt).hexdigest()}\n"
        )
        settings.write_text(text + "adapters:\n  reading: pi-v1\n")
    snapshot = check_config(settings, database)
    assert snapshot.stages[StageName.READ].status == "not_ready"
    assert snapshot.stages[StageName.READ].missing == (reason,)


@pytest.mark.parametrize("filename", ["schema.json", "manifest.json"])
def test_changed_current_contract_cannot_replace_registered_read_history(
    tmp_path: Path, filename: str
) -> None:
    settings, database = read_contract_inputs(tmp_path)
    saved = compile_config(settings, database)
    path = tmp_path / "contracts/read/read/v1" / filename
    path.write_bytes(path.read_bytes() + b"\n")
    for operation in (check_config, compile_config):
        with pytest.raises(ConfigError, match=r"contracts\.read：damaged_snapshot"):
            operation(settings, database)
    assert load_config_snapshot(database, saved.snapshot_id) == saved
    assert len(list_config_snapshots(database)) == 1


def test_registered_read_contract_survives_future_authority_in_isolated_process(
    tmp_path: Path,
) -> None:
    settings, database = read_contract_inputs(tmp_path)
    saved = compile_config(settings, database)
    # 在独立进程重建一次演进后的真实 Pydantic 权威模型,不 mock load 的协作者。
    script = """
import importlib
import sys
from pathlib import Path
from pydantic import create_model
from paper_radar.config import ConfigError, check_config, load_config_snapshot
import paper_radar.contracts.schema as contracts
import paper_radar.reading.schema as reading

reading.ReadAnalysisOutput = create_model(
    "FutureReadAnalysisOutput",
    __base__=reading.ReadAnalysisOutput,
    future_required_field=(str, ...),
)
importlib.reload(contracts)
contract = contracts.build_selected_contract("read", "v1")
assert b"future_required_field" in contract.schema_bytes
try:
    check_config(Path(sys.argv[1]), Path(sys.argv[2]))
except ConfigError as error:
    assert "contracts.read：content_drift" in str(error)
else:
    raise AssertionError("current authority unexpectedly accepted historical bytes")
snapshot = load_config_snapshot(Path(sys.argv[2]), sys.argv[3])
assert snapshot.stages["read"].status == "ready"
print(snapshot.snapshot_id)
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(settings), str(database), saved.snapshot_id],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == saved.snapshot_id
