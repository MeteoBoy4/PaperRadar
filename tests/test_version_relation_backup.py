"""关系三态、尚无任何端点及非空历史的隔离恢复。"""

import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from paper_radar.backup import create_backup, verify_backup
from paper_radar.backup.manifest import BackupError
from paper_radar.backup.restore import restore_backup
from paper_radar.backup.restore_contract import RestoreError
from paper_radar.papers import PaperFacts
from paper_radar.storage.database import upgrade_database
from tests.config_test_support import run_cli
from tests.test_paper_service import observation
from tests.test_version_relations import relation


def populated(root: Path) -> tuple[PaperFacts, tuple[str, ...]]:
    root.mkdir()
    db = root / "facts.sqlite"
    upgrade_database(db)
    service = PaperFacts(db, root / "data")
    papers = []
    for name, state in (
        ("missing", "endpoint_missing"),
        ("effective", "effective"),
        ("merge", "requires_merge"),
    ):
        pre, journal = f"10.1/{name}-pre", f"10.1/{name}-journal"
        links = (
            {
                "kind": "is-preprint-of",
                "source_doi": pre,
                "target_doi": journal,
                "locator": "relation",
            },
        )
        first = service.submit(
            observation(
                doi=pre,
                version_kind="preprint",
                relations=links if state != "requires_merge" else (),
            )
        )
        assert first.paper_id
        papers.append(first.paper_id)
        if state != "endpoint_missing":
            second = service.submit(observation(doi=journal))
            if state == "requires_merge":
                assert second.paper_id
                papers.append(second.paper_id)
                assert (
                    service.submit(
                        observation(
                            doi=pre,
                            version_kind="preprint",
                            payload=b"relation",
                            relations=links,
                        )
                    ).reason
                    == "requires_merge"
                )
        assert service.trace(first.paper_id).relations[0].state == state
    assert (
        service.submit(
            observation(
                doi="10.1/pre", version_kind="preprint", fields={}, relations=relation()
            )
        ).version_id
        is None
    )
    return service, tuple(papers)


def test_wal_backup_moves_and_rebuilds_all_relation_states_in_new_process(
    tmp_path: Path,
) -> None:
    service, papers = populated(tmp_path / "source")
    assert service.data_root
    expected = {
        paper_id: service.trace(paper_id).model_dump(mode="json") for paper_id in papers
    }
    with closing(sqlite3.connect(service.database)) as wal:
        wal.execute("PRAGMA wal_autocheckpoint=0")
        wal.execute("SELECT count(*) FROM papers")
        assert (
            service.submit(
                observation(
                    doi="10.1/pre",
                    version_kind="preprint",
                    fields={},
                    relations=relation(),
                    payload=b"relation again",
                )
            ).status
            == "not_retained"
        )
        batch = create_backup(service.database, service.data_root, tmp_path / "backups")
        assert verify_backup(batch.batch_dir) == batch
    (tmp_path / "source").rename(tmp_path / "unavailable")
    restored = restore_backup(batch.batch_dir, tmp_path / "restored")
    moved = tmp_path / "moved"
    restored.target_dir.rename(moved)
    for paper_id in papers:
        query = run_cli(
            tmp_path,
            "paper",
            "trace",
            paper_id,
            "--database",
            str(moved / "database.sqlite3"),
            "--data-root",
            str(moved),
            "--verify-source-bytes",
            "--json",
            "--show-abstract",
        )
        assert query.returncode == 0, query.stderr
        assert json.loads(query.stdout) == expected[paper_id]
    PaperFacts(moved / "database.sqlite3", moved).validate_all()


@pytest.mark.parametrize(
    "damage", ["source", "raw_endpoint", "kind", "missing_reference", "locator"]
)
def test_rehashed_relation_damage_is_rejected_without_repair(
    tmp_path: Path, damage: str
) -> None:
    service, _ = populated(tmp_path / "source")
    assert service.data_root
    batch = create_backup(service.database, service.data_root, tmp_path / "backups")
    copied = batch.batch_dir / "database.sqlite3"
    with closing(sqlite3.connect(copied)) as connection:
        if damage == "source":
            connection.execute(
                "UPDATE paper_source_acquisitions SET source_kind='feed' "
                "WHERE version_id IS NULL"
            )
        elif damage == "raw_endpoint":
            connection.execute(
                "UPDATE paper_relation_references SET raw_target_doi='10.1/forged'"
            )
        elif damage == "kind":
            connection.execute(
                "UPDATE paper_versions SET version_kind='journal' "
                "WHERE version_kind='preprint'"
            )
        elif damage == "missing_reference":
            connection.execute(
                "DELETE FROM paper_relation_references WHERE acquisition_id IN "
                "(SELECT acquisition_id FROM paper_version_relations)"
            )
        else:
            connection.execute("UPDATE paper_version_relations SET locator='   '")
        connection.commit()
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()
    manifest_path = batch.batch_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    raw = copied.read_bytes()
    manifest["database"].update(
        sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw)
    )
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    )
    with pytest.raises(BackupError) as failure:
        verify_backup(batch.batch_dir)
    assert failure.value.reason == "registration_invalid"
    with pytest.raises(RestoreError) as restore_failure:
        restore_backup(batch.batch_dir, tmp_path / "restore")
    assert restore_failure.value.reason == "registration_invalid"
    assert not (tmp_path / "restore").exists()
