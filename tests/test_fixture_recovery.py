"""声明与既有事实在固定副本和上一 revision 升级后的公开读取。"""

import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine

from paper_radar.backup import create_backup, verify_backup
from paper_radar.backup.manifest import BackupError
from paper_radar.backup.restore import restore_backup
from paper_radar.fixture_audit import FixtureAudit
from paper_radar.papers import PaperFacts
from paper_radar.storage import database as database_module
from paper_radar.storage.database import upgrade_database
from tests.fixture_registry_support import declaration_bytes


def registered(root: Path) -> tuple[FixtureAudit, str]:
    root.mkdir()
    database = root / "facts.sqlite3"
    upgrade_database(database)
    registry = FixtureAudit(database, root / "data")
    source = root / "declaration.json"
    source.write_bytes(declaration_bytes())
    result = registry.register(source)
    source.unlink()
    return registry, result.entries[0].record_id


def test_backup_restore_reconstructs_registered_bytes_without_source_file(
    tmp_path: Path,
) -> None:
    registry, record_id = registered(tmp_path / "source")
    assert registry.data_root is not None
    batch = create_backup(registry.database, registry.data_root, tmp_path / "backups")
    restored = restore_backup(batch.batch_dir, tmp_path / "restored")
    recovered = FixtureAudit(
        restored.target_dir / "database.sqlite3", restored.target_dir
    )
    assert recovered.show(record_id) == registry.show(record_id)
    assert (
        recovered.read_declaration(recovered.show(record_id).declaration_id)
        == declaration_bytes()
    )
    recovered.validate_all()
    PaperFacts(
        restored.target_dir / "database.sqlite3", restored.target_dir
    ).validate_all()


@pytest.mark.parametrize("damage", ["entry", "forged_acquired"])
def test_rehashed_entry_tampering_is_rejected_by_backup_semantic_validation(
    tmp_path: Path,
    damage: str,
) -> None:
    registry, _ = registered(tmp_path / "source")
    assert registry.data_root is not None
    batch = create_backup(registry.database, registry.data_root, tmp_path / "backups")
    copied = batch.batch_dir / "database.sqlite3"
    with closing(sqlite3.connect(copied)) as connection:
        content = json.loads(
            connection.execute("SELECT entry_json FROM fixture_records").fetchone()[0]
        )
        if damage == "entry":
            content["expectations"]["publisher_count"] = 0
        else:
            # Independent fixed vector: rehash every outer identity to present a
            # structurally consistent acquired claim without acquisition evidence.
            forged_raw = declaration_bytes().replace(
                b'"basis": "historical_declaration"', b'"basis": "acquired"'
            )
            forged_id = (
                "d96ba1e7f9df3241b8e1e380925ed758d13c2e4aebfd2d5811cbd7399c7fe0ef"
            )
            record_id = (
                "a50afa43e680638297e87b6a88a6a9628398d47f7c54961c14895c01cd977f25"
            )
            connection.execute(
                "UPDATE fixture_declarations "
                "SET declaration_id=?,raw_sha256=?,raw_content=?",
                (forged_id, forged_id, forged_raw),
            )
            connection.execute(
                "UPDATE fixture_records SET declaration_id=?,record_id=?",
                (forged_id, record_id),
            )
            content["basis"] = "acquired"
        connection.execute(
            "UPDATE fixture_records SET entry_json=?",
            (json.dumps(content, ensure_ascii=False, separators=(",", ":")),),
        )
        connection.commit()
    manifest_path = batch.batch_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    raw = copied.read_bytes()
    manifest["database"].update(
        sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw)
    )
    manifest_path.write_bytes(
        (
            json.dumps(
                manifest, sort_keys=True, ensure_ascii=False, separators=(",", ":")
            )
            + "\n"
        ).encode()
    )
    with pytest.raises(BackupError) as caught:
        verify_backup(batch.batch_dir)
    assert caught.value.reason == "registration_invalid"


def test_nonempty_a704_upgrade_preserves_existing_tables_and_foreign_keys(
    tmp_path: Path,
) -> None:
    database = tmp_path / "a704.sqlite3"
    config = Config()
    config.set_main_option(
        "script_location", str(Path(database_module.__file__).parent / "migrations")
    )
    engine = create_engine(f"sqlite:///{database}")
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            config.attributes["connection"] = connection
            command.upgrade(config, "a704_screening_retry")
            connection.commit()
    finally:
        engine.dispose()
    with closing(sqlite3.connect(database)) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(
            "INSERT INTO config_versions VALUES (?,?,?,?,?)",
            ("profile", "legacy", "v1", "a" * 64, b"old bytes"),
        )
        connection.execute(
            "INSERT INTO feeds VALUES (?,?)",
            ("12345678-1234-4234-8234-123456789abc", "https://example.org/feed"),
        )
        connection.commit()
        names = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name!='alembic_version'"
            )
        ]
        before = {
            name: connection.execute(f"SELECT * FROM {name}").fetchall()
            for name in names
        }
    assert upgrade_database(database) == "feed05_composition"
    assert upgrade_database(database) == "feed05_composition"
    with closing(sqlite3.connect(database)) as connection:
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()
        assert {
            name: connection.execute(f"SELECT * FROM {name}").fetchall()
            for name in names
        } == before
        connection.execute("PRAGMA foreign_keys=ON")
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
            connection.execute(
                "INSERT INTO fixture_records(record_id,declaration_id,purpose,"
                "journal,sample_key,entry_json) VALUES (?,?,?,?,?,?)",
                ("b" * 64, "a" * 64, "pdf", "jgr", "missing", "{}"),
            )
