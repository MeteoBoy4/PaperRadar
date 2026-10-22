"""真实 Feed 业务闭包、WAL 隔离恢复与语义损坏拒绝。"""

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
from tests.backup_support import tree
from tests.config_test_support import run_cli
from tests.feed_support import facts, item
from tests.test_paper_service import observation


def test_feed_backup_restores_originals_and_interpretations_after_move(
    tmp_path: Path,
) -> None:
    from datetime import UTC, datetime

    root = tmp_path / "source"
    root.mkdir()
    service = facts(root)
    feed = service.register_feed("https://feeds.example/f?edition=1")
    first = service.submit(item(feed.feed_id, fields={}))
    assert first.paper_id and service.data_root
    with closing(sqlite3.connect(service.database)) as wal:
        wal.execute("PRAGMA wal_autocheckpoint=0")
        wal.execute("SELECT count(*) FROM papers")
        second = service.submit(
            item(feed.feed_id, payload=b"changed with DOI", doi="DOI:10.1234/AbC")
        )
        assert second.paper_id == first.paper_id
        service.submit(
            item(
                feed.feed_id,
                payload=b"changed with DOI",
                doi="DOI:10.1234/AbC",
                parser_version=2,
                fields={},
            )
        )
        third = service.submit(
            item(feed.feed_id, entry_id="still-no-doi", payload=b"no-doi unchanged")
        )
        assert third.paper_id
        publisher = service.submit(
            observation(fields={"title": {"value": "Publisher", "locator": "title"}})
        )
        assert publisher.paper_id == first.paper_id
        service.submit(
            item(
                feed.feed_id,
                payload=b"changed with DOI",
                doi="DOI:10.1234/AbC",
                observed_at=datetime(2026, 2, 1, tzinfo=UTC),
            )
        )
        # A conflict can leave complete unreferenced bytes and is still a valid closure.
        assert (
            service.submit(
                item(feed.feed_id, payload=b"conflict raw", doi="10.1/conflict")
            ).reason
            == "identity_conflict"
        )
        expected = {
            paper_id: service.trace(paper_id, verify_source_bytes=True).model_dump(
                mode="json"
            )
            for paper_id in (first.paper_id, third.paper_id)
        }
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
    for paper_id, trace in expected.items():
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
        assert json.loads(query.stdout) == trace
    assert any(
        event["raw_doi"] == "DOI:10.1234/AbC"
        for event in expected[first.paper_id]["acquisitions"]
    )


@pytest.mark.parametrize(
    "damage",
    [
        "fingerprint",
        "payload",
        "entry_target",
        "interpretation",
        "raw_doi",
        "unused_feed_url",
    ],
)
def test_verify_restore_reject_rehashed_semantic_feed_damage_without_repair(
    tmp_path: Path, damage: str
) -> None:
    service = facts(tmp_path)
    feed = service.register_feed("https://feeds.example/f?edition=1")
    unused = service.register_feed("https://feeds.example/unused")
    first = service.submit(item(feed.feed_id, doi="10.1/x"))
    second = service.submit(observation(doi="10.1/y"))
    assert first.version_id and second.version_id and service.data_root
    batch = create_backup(service.database, service.data_root, tmp_path / "backups")
    copied = batch.batch_dir / "database.sqlite3"
    with closing(sqlite3.connect(copied)) as connection:
        if damage == "fingerprint":
            connection.execute(
                "UPDATE feed_discoveries SET item_fingerprint=?", ("0" * 64,)
            )
        elif damage == "payload":
            other = connection.execute(
                "SELECT artifact_id FROM paper_observations WHERE version_id=?",
                (second.version_id,),
            ).fetchone()[0]
            connection.execute("UPDATE feed_discoveries SET artifact_id=?", (other,))
        elif damage == "entry_target":
            connection.execute(
                "UPDATE feed_entries SET version_id=?", (second.version_id,)
            )
        elif damage == "interpretation":
            connection.execute(
                "UPDATE feed_interpretations SET acquisition_id=?",
                (second.acquisition_id,),
            )
        elif damage == "raw_doi":
            connection.execute(
                "UPDATE paper_source_acquisitions SET raw_doi='10.1/other' "
                "WHERE acquisition_id=?",
                (first.acquisition_id,),
            )
        else:
            connection.execute(
                "UPDATE feeds SET url='HTTPS://Feeds.Example:443/invalid' "
                "WHERE feed_id=?",
                (unused.feed_id,),
            )
        connection.commit()
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()
    manifest = json.loads((batch.batch_dir / "manifest.json").read_bytes())
    raw = copied.read_bytes()
    manifest["database"].update(
        sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw)
    )
    (batch.batch_dir / "manifest.json").write_bytes(
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
