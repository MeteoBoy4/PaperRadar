"""完整组合库上 FK 合法且外层重哈希的代表性业务矛盾,拒绝且不修复。"""

import hashlib
import json
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from paper_radar.backup import create_backup, verify_backup
from paper_radar.backup.manifest import BackupError
from paper_radar.backup.restore import restore_backup
from paper_radar.backup.restore_contract import RestoreError
from paper_radar.storage.artifacts import ArtifactStore
from tests.paper_recovery_reader import digest
from tests.paper_recovery_support import RecoveryFacts, populated, tree_hash


@pytest.fixture(scope="module")
def original(tmp_path_factory: pytest.TempPathFactory) -> tuple[RecoveryFacts, Path]:
    root = tmp_path_factory.mktemp("complete-recovery-damage")
    facts = populated(root / "source")
    assert facts.service.data_root
    ArtifactStore(facts.service.database, facts.service.data_root).publish_single(
        "original_pdf", (b"formal material",)
    )
    batch = create_backup(
        facts.service.database, facts.service.data_root, root / "batches"
    )
    return facts, batch.batch_dir


def rehash(batch: Path) -> None:
    path = batch / "manifest.json"
    manifest = json.loads(path.read_bytes())
    raw = (batch / "database.sqlite3").read_bytes()
    manifest["database"].update(
        sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw)
    )
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    )


@pytest.mark.parametrize(
    "damage",
    [
        "item_payload",
        "provenance_version",
        "doi_ownership",
        "selected_candidate",
        "revision_closure",
        "selection",
        "relation_evidence",
        "wrong_kind",
        "future_revision",
        "missing_blob",
        "corrupt_blob",
    ],
)
def test_combined_rehashed_damage_never_restores_or_repairs(
    tmp_path: Path,
    original: tuple[RecoveryFacts, Path],
    damage: str,
) -> None:
    facts, source = original
    batch = tmp_path / source.name
    shutil.copytree(source, batch)
    copied = batch / "database.sqlite3"
    reason = "registration_invalid"
    with closing(sqlite3.connect(copied)) as connection:
        if damage == "item_payload":
            connection.execute(
                "UPDATE feed_discoveries SET item_fingerprint=? WHERE discovery_id=?",
                ("0" * 64, facts.feed_version.discovery_id),
            )
        elif damage == "provenance_version":
            connection.execute(
                "UPDATE paper_observations SET version_id=? WHERE observation_id=?",
                (facts.never.version_id, facts.journal.observation_id),
            )
        elif damage == "doi_ownership":
            # Both identifiers still reference legal composite
            # Paper/Version foreign keys.
            connection.execute(
                "DELETE FROM external_identifiers WHERE "
                "normalized_value='10.74/ambiguous'"
            )
            connection.execute(
                (
                    "UPDATE external_identifiers SET paper_id=?, version_id=? WHERE "
                    "normalized_value='10.74/journal'"
                ),
                (facts.never.paper_id, facts.never.version_id),
            )
        elif damage == "selected_candidate":
            old_candidate = connection.execute(
                (
                    "SELECT candidate_id FROM paper_field_candidates WHERE "
                    "observation_id=? AND field_name='title'"
                ),
                (facts.pre.observation_id,),
            ).fetchone()[0]
            connection.execute(
                (
                    "UPDATE paper_revision_fields SET candidate_id=?, acquisition_id=?"
                    " WHERE version_id=? AND field_name='title' AND "
                    "revision_no=(SELECT max(revision_no) FROM paper_version_revisions"
                    " WHERE version_id=?)"
                ),
                (
                    old_candidate,
                    facts.pre.acquisition_id,
                    facts.pre.version_id,
                    facts.pre.version_id,
                ),
            )
        elif damage == "revision_closure":
            connection.execute(
                (
                    "DELETE FROM paper_revision_fields WHERE version_id=? AND "
                    "field_name='abstract'"
                ),
                (facts.journal.version_id,),
            )
        elif damage == "selection":
            connection.execute(
                "UPDATE paper_selection_events SET reason='initial' WHERE version_id=?",
                (facts.journal.version_id,),
            )
        elif damage == "relation_evidence":
            connection.execute(
                (
                    "UPDATE paper_relation_references SET "
                    "raw_target_doi='10.74/forged' WHERE acquisition_id=?"
                ),
                (facts.pre.acquisition_id,),
            )
        elif damage == "wrong_kind":
            wrong = connection.execute(
                "SELECT artifact_id FROM artifacts WHERE kind='original_pdf'"
            ).fetchone()[0]
            connection.execute(
                "UPDATE paper_observations SET artifact_id=? WHERE observation_id=?",
                (wrong, facts.journal.observation_id),
            )
        elif damage == "future_revision":
            connection.execute("UPDATE alembic_version SET version_num='a999_future'")
            reason = "unsupported_revision"
        connection.commit()
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()
    if damage == "future_revision":
        manifest_path = batch / "manifest.json"
        manifest = json.loads(manifest_path.read_bytes())
        manifest["database_revision"] = manifest["code"]["migration_revision"] = (
            "a999_future"
        )
        manifest_path.write_text(
            json.dumps(
                manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            + "\n"
        )
    if damage in {"missing_blob", "corrupt_blob"}:
        blob = next((batch / "blobs").rglob("*/*/*"))
        assert blob.is_file()
        if damage == "missing_blob":
            blob.unlink()
            reason = "file_missing"
        else:
            blob.chmod(0o600)
            blob.write_bytes(b"PRIVATE-RECOVERY corrupt bytes")
            blob.chmod(0o400)
            reason = "file_corrupt"
    rehash(batch)
    before = tree_hash(batch)
    with pytest.raises(BackupError) as verify_failure:
        verify_backup(batch)
    assert verify_failure.value.reason == reason
    with pytest.raises(RestoreError) as restore_failure:
        restore_backup(batch, tmp_path / "restore")
    assert restore_failure.value.reason == reason
    assert tree_hash(batch) == before
    assert not (tmp_path / "restore").exists()
    assert not list(tmp_path.glob(".restore-*"))


def test_create_rejects_semantic_contradiction_without_changing_source(
    tmp_path: Path,
) -> None:
    facts = populated(tmp_path / "source")
    service = facts.service
    assert service.data_root
    with closing(sqlite3.connect(service.database)) as connection:
        connection.execute(
            (
                "UPDATE paper_relation_references SET "
                "raw_target_doi='10.74/forged' WHERE acquisition_id=?"
            ),
            (facts.pre.acquisition_id,),
        )
        connection.commit()
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()
    before = tree_hash(tmp_path / "source", ignore_sqlite_sidecars=True)
    with closing(sqlite3.connect(service.database)) as connection:
        logical_before = digest(tuple(connection.iterdump()))
    with pytest.raises(BackupError) as failure:
        create_backup(service.database, service.data_root, tmp_path / "batches")
    assert failure.value.reason == "registration_invalid"
    assert tree_hash(tmp_path / "source", ignore_sqlite_sidecars=True) == before
    with closing(sqlite3.connect(service.database)) as connection:
        assert digest(tuple(connection.iterdump())) == logical_before
    assert not tuple((tmp_path / "batches").iterdir())
