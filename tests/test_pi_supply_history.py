"""非空旧库升级和供给材料的备份/隔离恢复。"""

import json
import shutil
import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine

from paper_radar.backup import create_backup, restore_backup, verify_backup
from paper_radar.config import load_config_snapshot
from paper_radar.config.identity import sha256
from paper_radar.pi_supply import SupplyError, list_supplies, show_supply
from paper_radar.storage import database as database_module
from paper_radar.storage.artifacts import ArtifactStore
from paper_radar.storage.database import upgrade_database
from tests.backup_support import populated
from tests.pi_supply_support import encoded, inputs, prepare


def test_real_a302_nonempty_upgrade_preserves_all_old_bytes(tmp_path: Path) -> None:
    source, data, snapshot_id = populated(tmp_path / "seed")
    # 使用真实 a302 schema 和已验证的历史行, 不把当前库改 stamp 冒充旧库。
    old = tmp_path / "a302.sqlite3"
    config = Config()
    config.set_main_option(
        "script_location", str(Path(database_module.__file__).parent / "migrations")
    )
    engine = create_engine(f"sqlite:///{old}")
    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "a302_artifact_store")
        connection.commit()
    engine.dispose()
    with sqlite3.connect(source) as original, sqlite3.connect(old) as previous:
        tables = [
            row[0]
            for row in previous.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name != 'alembic_version' ORDER BY name"
            )
        ]
        expected = {}
        for table in tables:
            values = original.execute(f"SELECT * FROM {table}").fetchall()
            expected[table] = values
            if values:
                placeholders = ",".join("?" for _ in values[0])
                previous.executemany(
                    f"INSERT INTO {table} VALUES ({placeholders})", values
                )
    assert upgrade_database(old) == "a601_paper_facts"
    assert load_config_snapshot(old, snapshot_id).snapshot_id == snapshot_id
    assert (
        ArtifactStore(old, data).list_artifacts()
        == ArtifactStore(source, data).list_artifacts()
    )
    with sqlite3.connect(old) as connection:
        assert {
            table: connection.execute(f"SELECT * FROM {table}").fetchall()
            for table in tables
        } == expected
    assert list_supplies(old) == ()


def test_nonempty_supply_restore_keeps_materials_without_installing(
    tmp_path: Path,
) -> None:
    source = inputs(tmp_path / "source")
    prepared = prepare(tmp_path / "source", source)
    data = tmp_path / "source/data"
    ArtifactStore(source[0], data).publish_single("source_snapshot", [b"source bytes"])
    record = show_supply(source[0], prepared.supply_id)
    batch = create_backup(source[0], data, tmp_path / "backups")
    assert verify_backup(batch.batch_dir).manifest.format_version == 1
    shutil.rmtree(tmp_path / "source/config")
    result = restore_backup(batch.batch_dir, tmp_path / "restored")
    restored = show_supply(result.target_dir / "database.sqlite3", prepared.supply_id)
    assert restored.manifest == record.manifest
    assert restored.materials == record.materials
    assert restored.installs == record.installs
    assert not (result.target_dir / ".tools").exists()
    assert not (result.target_dir / "pi-supply.lock").exists()


def test_real_pi130_materials_match_spike_derived_lock_vector(tmp_path: Path) -> None:
    source = inputs(tmp_path)
    fixture = Path(__file__).parent / "fixtures/pi_supply/1.3.0"
    base = "https://pi.dev/api/installer/releases/1.3.0"
    for role, suffix in (
        ("package.json", "/package.json"),
        ("package-lock.json", "/package-lock.json"),
        ("release.json", ""),
    ):
        source[3].content[base + suffix] = (fixture / role).read_bytes()
    prepared = prepare(tmp_path, source)
    record = show_supply(source[0], prepared.supply_id)
    assert (
        record.manifest.materials["derived-lock.json"]
        == "a342ed1baea205543bdcaf82ec4aed2bfc771a5c2c47b2bacb8238d06513e7c6"
    )
    original = json.loads(record.materials["package-lock.json"])
    derived = json.loads(record.materials["derived-lock.json"])
    supplements = json.loads(record.materials["integrity-supplements.json"])["packages"]
    assert len(supplements) == 7
    for entry in supplements:
        del derived["packages"][entry["path"]]["integrity"]
    assert derived == original
    assert json.loads(record.materials["package.json"])["overrides"] == {
        "protobufjs": "7.6.6"
    }


def test_three_d5_evidence_kinds_survive_nonempty_restore(tmp_path: Path) -> None:
    source = inputs(tmp_path / "source")
    first = prepare(tmp_path / "source", source)
    previous = show_supply(source[0], first.supply_id)
    payload = json.loads(source[2].read_bytes())
    payload["d5"] = {
        "decision": "no_change",
        "basis": "Only upstream material formatting changed",
        "baseline_supply_id": first.supply_id,
        "evidence": [
            {"kind": "evidence_file", "path": "evidence.txt"},
            {
                "kind": "supply_material",
                "supply_id": first.supply_id,
                "material": "release.json",
            },
            {
                "kind": "supply_record",
                "supply_id": first.supply_id,
                "check_id": previous.installs[0].checks[0].check_id,
            },
        ],
    }
    source[2].write_bytes(encoded(payload))
    source[3].content["https://pi.dev/api/installer/releases/1.3.0/package.json"] += (
        b"\n"
    )
    second = prepare(tmp_path / "source", source)
    data = tmp_path / "source/data"
    ArtifactStore(source[0], data).publish_single("source_snapshot", [b"evidence"])
    batch = create_backup(source[0], data, tmp_path / "backups")
    restored = restore_backup(batch.batch_dir, tmp_path / "restored")
    record = show_supply(restored.target_dir / "database.sqlite3", second.supply_id)
    assert record.manifest.d5.baseline_supply_id == first.supply_id
    assert tuple(e.kind for e in record.manifest.d5.evidence) == (
        "evidence_file",
        "supply_material",
        "supply_record",
    )


@pytest.mark.parametrize(
    "corruption",
    ["empty_basis", "baseline", "bad_evidence_shape", "entry", "format_bool"],
)
def test_semantically_bad_manifest_is_rejected_even_after_consistent_rehash(
    tmp_path: Path, corruption: str
) -> None:
    from paper_radar.config.identity import canonical_json

    source = inputs(tmp_path)
    prepared = prepare(tmp_path, source)
    record = show_supply(source[0], prepared.supply_id)
    payload = record.manifest.model_dump(mode="json")
    if corruption == "empty_basis":
        payload["d5"]["basis"] = " "
    elif corruption == "baseline":
        payload["d5"]["baseline_supply_id"] = "f" * 64
    elif corruption == "bad_evidence_shape":
        payload["d5"]["evidence"][0]["kind"] = "supply_record"
    elif corruption == "entry":
        payload["pi_entry"] = "/SECRET/entry"
    else:
        payload["format_version"] = True
    raw = canonical_json(payload)
    new_id = sha256(raw)
    # 故意修正内容寻址引用, 不能仅凭哈希自洽逃过语义回放。
    with sqlite3.connect(source[0]) as connection:
        connection.execute(
            "UPDATE pi_supplies SET manifest=?,supply_id=?", (raw, new_id)
        )
        connection.execute("UPDATE pi_supply_materials SET supply_id=?", (new_id,))
        connection.execute("UPDATE pi_install_instances SET supply_id=?", (new_id,))
    with pytest.raises(SupplyError):
        list_supplies(source[0])


def test_future_evidence_rejected_even_with_equal_audit_timestamps(
    tmp_path: Path,
) -> None:
    from paper_radar.config.identity import canonical_json

    source = inputs(tmp_path)
    first = prepare(tmp_path, source)
    original = show_supply(source[0], first.supply_id)
    source[3].content["https://pi.dev/api/installer/releases/1.3.0/package.json"] += (
        b"\n"
    )
    second = prepare(tmp_path, source)
    later = show_supply(source[0], second.supply_id)
    payload = original.manifest.model_dump(mode="json")
    payload["d5"]["evidence"].append(
        {
            "kind": "supply_record",
            "supply_id": second.supply_id,
            "check_id": later.installs[0].checks[0].check_id,
            "sha256": None,
            "material": None,
            "note": None,
        }
    )
    raw = canonical_json(payload)
    new_id = sha256(raw)
    with sqlite3.connect(source[0]) as connection:
        connection.execute(
            "UPDATE pi_supplies SET supply_id=?,manifest=?,created_at=? "
            "WHERE supply_id=?",
            (new_id, raw, later.created_at, first.supply_id),
        )
        connection.execute(
            "UPDATE pi_supply_materials SET supply_id=? WHERE supply_id=?",
            (new_id, first.supply_id),
        )
        connection.execute(
            "UPDATE pi_install_instances SET supply_id=? WHERE supply_id=?",
            (new_id, first.supply_id),
        )
    with pytest.raises(SupplyError, match="evidence_unresolved"):
        list_supplies(source[0])
