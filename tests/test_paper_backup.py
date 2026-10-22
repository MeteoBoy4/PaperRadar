"""真实非空论文备份/语义校验/隔离恢复。"""

import json
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

import pytest

from paper_radar.backup import create_backup, verify_backup
from paper_radar.backup.manifest import BackupError
from paper_radar.backup.restore import restore_backup
from paper_radar.papers import PaperFacts
from paper_radar.storage.database import upgrade_database
from tests.config_test_support import run_cli
from tests.test_paper_service import observation


def test_backup_restores_paper_identity_and_candidates_in_new_process(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    root.mkdir()
    database, data_root = root / "facts.sqlite", root / "data"
    upgrade_database(database)
    service = PaperFacts(database, data_root)
    result = service.submit(observation())
    assert result.paper_id
    with closing(sqlite3.connect(database)) as wal:
        wal.execute("PRAGMA wal_autocheckpoint=0")
        wal.execute("SELECT count(*) FROM papers")
        from datetime import UTC, datetime

        repeated = service.submit(
            observation(
                observed_at=datetime(2026, 1, 2, tzinfo=UTC),
                payload=b"same candidates, unrelated bytes changed",
            )
        )
        assert repeated.status == "not_retained"
        expected = service.trace(result.paper_id).model_dump(mode="json")
        assert len(expected["acquisitions"]) == 2
        assert database.with_name(database.name + "-wal").stat().st_size > 0
        batch = create_backup(database, data_root, tmp_path / "backups")
        assert verify_backup(batch.batch_dir) == batch
    root.rename(tmp_path / "unavailable")
    restored = restore_backup(batch.batch_dir, tmp_path / "restored")
    moved = tmp_path / "moved"
    restored.target_dir.rename(moved)
    query = run_cli(
        tmp_path,
        "paper",
        "trace",
        result.paper_id,
        "--database",
        str(moved / "database.sqlite3"),
        "--data-root",
        str(moved),
        "--verify-source-bytes",
        "--json",
        "--show-abstract",
    )
    assert query.returncode == 0, query.stderr
    assert json.loads(query.stdout) == expected
    retry = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from pathlib import Path; from paper_radar.papers import Pap"
                "erFacts; from tests.test_paper_service import observation; i"
                "mport sys; print(PaperFacts(Path(sys.argv[1]),Path(sys.argv["
                "2])).submit(observation()).model_dump_json())"
            ),
            str(moved / "database.sqlite3"),
            str(moved),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert retry.returncode == 0, retry.stderr
    assert json.loads(retry.stdout)["paper_id"] == result.paper_id


def test_backup_rejects_cross_version_provenance_even_when_foreign_keys_are_valid(
    tmp_path: Path,
) -> None:
    database = tmp_path / "facts.sqlite"
    upgrade_database(database)
    service = PaperFacts(database, tmp_path / "data")
    first = service.submit(observation())
    second = service.submit(observation(doi="10.1/other"))
    assert first.version_id and second.version_id
    with closing(sqlite3.connect(database)) as connection:
        other = connection.execute(
            (
                "SELECT candidate_id FROM paper_field_candidates JOIN paper_o"
                "bservations USING(observation_id) WHERE version_id=?"
            ),
            (second.version_id,),
        ).fetchone()[0]
        connection.execute(
            "UPDATE paper_revision_fields SET candidate_id=? WHERE version_id=?",
            (other, first.version_id),
        )
        connection.commit()
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()
    with pytest.raises(BackupError) as failure:
        create_backup(database, tmp_path / "data", tmp_path / "backup")
    assert failure.value.reason == "registration_invalid"


@pytest.mark.parametrize(
    "damage", ["wrong_winner", "missing_field", "candidate_text", "source_kind"]
)
def test_semantic_backup_validation_rejects_forged_revision_or_source(
    tmp_path: Path, damage: str
) -> None:
    from datetime import UTC, datetime

    from paper_radar.storage.artifacts import ArtifactStore

    database = tmp_path / "facts.sqlite"
    upgrade_database(database)
    service = PaperFacts(database, tmp_path / "data")
    first = service.submit(
        observation(
            fields={
                "title": {"value": "Old title", "locator": "title"},
                "journal": {"value": "Journal", "locator": "journal"},
            }
        )
    )
    second = service.submit(
        observation(
            observed_at=datetime(2026, 2, 1, tzinfo=UTC),
            payload=b"new material",
            fields={"title": {"value": "New title", "locator": "title"}},
        )
    )
    wrong = ArtifactStore(database, tmp_path / "data").publish_single(
        "original_pdf", (b"wrong kind",)
    )
    assert first.observation_id and second.observation_id
    with closing(sqlite3.connect(database)) as connection:
        if damage == "wrong_winner":
            old = connection.execute(
                (
                    "SELECT candidate_id FROM paper_field_candidates WHERE ob"
                    "servation_id=? AND field_name='title'"
                ),
                (first.observation_id,),
            ).fetchone()[0]
            connection.execute(
                (
                    "UPDATE paper_revision_fields SET candidate_id=? WHERE re"
                    "vision_no=2 AND field_name='title'"
                ),
                (old,),
            )
        elif damage == "missing_field":
            connection.execute(
                "DELETE FROM paper_revision_fields WHERE revision_no=2 AN"
                "D field_name='journal'"
            )
        elif damage == "candidate_text":
            connection.execute(
                "UPDATE paper_field_candidates SET text_value='Forged' WH"
                "ERE field_name='title'"
            )
        else:
            connection.execute(
                "UPDATE paper_observations SET artifact_id=?, payload_sha256=?",
                (wrong.artifact_id, wrong.members[0].sha256),
            )
        connection.commit()
    with pytest.raises(BackupError) as failure:
        create_backup(database, tmp_path / "data", tmp_path / "backup")
    assert failure.value.reason == "registration_invalid"


@pytest.mark.parametrize("old_revision", [False, True])
def test_verify_and_restore_reject_rehashed_semantic_damage_or_a405_batch(
    tmp_path: Path, old_revision: bool
) -> None:
    import hashlib

    from paper_radar.backup.restore_contract import RestoreError
    from tests.backup_support import tree

    database = tmp_path / "facts.sqlite"
    upgrade_database(database)
    service = PaperFacts(database, tmp_path / "data")
    service.submit(observation())
    batch = create_backup(database, tmp_path / "data", tmp_path / "batches")
    copied = batch.batch_dir / "database.sqlite3"
    if old_revision:
        import shutil

        from tests.test_paper_migrations import previous_database

        old = tmp_path / "real-a405.sqlite3"
        previous_database(old)
        with (
            closing(sqlite3.connect(copied)) as original,
            closing(sqlite3.connect(old)) as legacy,
        ):
            names = [
                row[0]
                for row in legacy.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name!='alembic_version'"
                )
            ]
            for table in names:
                values = original.execute(f"SELECT * FROM {table}").fetchall()
                legacy.execute(f"DELETE FROM {table}")
                if values:
                    marks = ",".join("?" for _ in values[0])
                    legacy.executemany(f"INSERT INTO {table} VALUES ({marks})", values)
            legacy.commit()
        shutil.copyfile(old, copied)
    else:
        with closing(sqlite3.connect(copied)) as connection:
            connection.execute("UPDATE paper_field_candidates SET text_value='Forged'")
            connection.commit()
    value = json.loads((batch.batch_dir / "manifest.json").read_bytes())
    raw = copied.read_bytes()
    value["database"].update(
        sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw)
    )
    if old_revision:
        value["database_revision"] = value["code"]["migration_revision"] = (
            "a405_pi_cleanup_execution"
        )
    (batch.batch_dir / "manifest.json").write_bytes(
        (
            json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
        ).encode()
    )
    before = tree(batch.batch_dir)
    reason = "unsupported_revision" if old_revision else "registration_invalid"
    with pytest.raises(BackupError) as verify_failure:
        verify_backup(batch.batch_dir)
    assert verify_failure.value.reason == reason
    with pytest.raises(RestoreError) as restore_failure:
        restore_backup(batch.batch_dir, tmp_path / "restored")
    assert restore_failure.value.reason == reason
    assert tree(batch.batch_dir) == before
    assert not (tmp_path / "restored").exists()


def test_backup_rejects_same_parser_receipts_with_different_parsed_content(
    tmp_path: Path,
) -> None:
    from datetime import UTC, datetime

    database = tmp_path / "facts.sqlite"
    upgrade_database(database)
    service = PaperFacts(database, tmp_path / "data")
    service.submit(observation())
    repeated = service.submit(observation(observed_at=datetime(2026, 1, 2, tzinfo=UTC)))
    assert repeated.acquisition_id
    with closing(sqlite3.connect(database)) as connection:
        connection.execute(
            "UPDATE paper_source_acquisitions SET parsed_sha256=? "
            "WHERE acquisition_id=?",
            ("0" * 64, repeated.acquisition_id),
        )
        connection.commit()
    with pytest.raises(BackupError) as failure:
        create_backup(database, tmp_path / "data", tmp_path / "backup")
    assert failure.value.reason == "registration_invalid"
