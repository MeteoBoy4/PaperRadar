"""完整来源/人工历史的备份恢复与语义闭包。"""

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
from tests.backup_support import tree
from tests.feed_support import facts, item
from tests.test_manual_corrections import correction
from tests.test_paper_service import observation


def populated(root: Path) -> tuple[PaperFacts, str, str]:
    root.mkdir(exist_ok=True)
    service = facts(root)
    feed = service.register_feed("https://example.org/feed")
    first = service.submit(item(feed.feed_id, doi="10.1234/abc"))
    assert first.paper_id and first.version_id
    assert (
        service.submit(
            observation(
                source_kind="registry",
                provider="crossref",
                query_key="10.1234/abc",
                target_paper_id=first.paper_id,
                target_version_id=first.version_id,
            )
        ).status
        == "retained"
    )
    assert service.submit(observation(payload=b"publisher")).status == "retained"
    assert service.correct(correction(first.version_id)).status == "retained"
    return service, first.paper_id, first.version_id


@pytest.mark.parametrize(
    "damage", ["manual_reason", "registry_query", "cross_version", "manual_missing"]
)
def test_rehashed_semantic_damage_is_rejected_without_repair(
    tmp_path: Path, damage: str
) -> None:
    service, _paper_id, version_id = populated(tmp_path / "source")
    other = service.submit(observation(doi="10.1234/other"))
    assert other.version_id and service.data_root
    batch = create_backup(service.database, service.data_root, tmp_path / "backups")
    copied = batch.batch_dir / "database.sqlite3"
    with closing(sqlite3.connect(copied)) as connection:
        if damage == "manual_reason":
            connection.execute("UPDATE paper_manual_corrections SET reason='forged'")
        elif damage == "registry_query":
            connection.execute(
                "UPDATE paper_source_acquisitions SET query_key='10.1234/wrong' "
                "WHERE source_kind='registry'"
            )
            connection.execute(
                "UPDATE paper_observations SET query_key='10.1234/wrong' WHERE "
                "source_kind='registry'"
            )
        elif damage == "cross_version":
            candidate, acquired = connection.execute(
                "SELECT candidate_id, acquisition_id FROM paper_revision_fields "
                "WHERE version_id=?",
                (other.version_id,),
            ).fetchone()
            connection.execute(
                "UPDATE paper_revision_fields SET candidate_id=?, "
                "acquisition_id=? WHERE version_id=? AND revision_no=4",
                (candidate, acquired, version_id),
            )
        else:
            connection.execute("DELETE FROM paper_manual_corrections")
        connection.commit()
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()
    manifest_path = batch.batch_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    raw = copied.read_bytes()
    manifest["database"].update(
        sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw)
    )
    manifest_path.write_bytes(
        (
            json.dumps(
                manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            + "\n"
        ).encode()
    )
    before = tree(batch.batch_dir)
    with pytest.raises(BackupError) as verify_failure:
        verify_backup(batch.batch_dir)
    assert verify_failure.value.reason == "registration_invalid"
    with pytest.raises(RestoreError) as restore_failure:
        restore_backup(batch.batch_dir, tmp_path / "restored")
    assert restore_failure.value.reason == "registration_invalid"
    assert tree(batch.batch_dir) == before
    assert not (tmp_path / "restored").exists()


def test_nonempty_wal_backup_restores_all_source_history_in_new_process_after_move(
    tmp_path: Path,
) -> None:
    from paper_radar.storage.database import upgrade_database
    from tests.config_test_support import run_cli
    from tests.pi_supply_support import inputs, prepare
    from tests.restore_support import history_view

    root = tmp_path / "source"
    source = inputs(root)
    prepare(root, source)
    service = PaperFacts(source[0], root / "data")
    feed = service.register_feed("https://example.org/feed")
    first = service.submit(item(feed.feed_id, doi="10.1234/abc"))
    assert first.paper_id and first.version_id and service.data_root
    registry = observation(
        source_kind="registry",
        provider="crossref",
        query_key="10.1234/abc",
        target_paper_id=first.paper_id,
        target_version_id=first.version_id,
    )
    assert service.submit(registry).status == "retained"
    request = correction(first.version_id)
    result = service.correct(request)
    assert result.status == "retained"
    expected = service.trace(first.paper_id).model_dump(mode="json")
    expected_history = history_view(service.database, service.data_root)
    with closing(sqlite3.connect(service.database)) as wal:
        wal.execute("PRAGMA wal_autocheckpoint=0")
        wal.execute("SELECT count(*) FROM papers")
        assert service.submit(observation(payload=b"latest")).status == "retained"
        expected = service.trace(first.paper_id).model_dump(mode="json")
        expected_history = history_view(service.database, service.data_root)
        assert (
            service.database.with_name(service.database.name + "-wal").stat().st_size
            > 0
        )
        batch = create_backup(service.database, service.data_root, tmp_path / "backups")
        assert verify_backup(batch.batch_dir) == batch
    root.rename(tmp_path / "unavailable")
    restored = restore_backup(batch.batch_dir, tmp_path / "restored")
    moved = tmp_path / "moved"
    restored.target_dir.rename(moved)
    query = run_cli(
        tmp_path,
        "paper",
        "trace",
        first.paper_id,
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
    recovered = PaperFacts(moved / "database.sqlite3", moved)
    assert recovered.correct(request) == result
    assert recovered.revision(first.version_id, 1).fields["title"].value == "A"
    assert history_view(recovered.database, moved) == expected_history
    assert upgrade_database(recovered.database) == "a701_screening_registration"
