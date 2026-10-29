"""强冲突保留证据但不改变论文事实。"""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path

import pytest

from paper_radar.backup import create_backup
from paper_radar.backup.restore import restore_backup
from paper_radar.papers import PaperFacts
from paper_radar.papers.errors import PaperError
from tests.feed_support import facts, item
from tests.test_paper_service import observation


def test_rejected_feed_conflict_retains_queryable_original_bytes(
    tmp_path: Path,
) -> None:
    service = facts(tmp_path)
    feed = service.register_feed("https://feeds.example/f")
    first = service.submit(item(feed.feed_id, doi="10.1/a"))
    assert first.paper_id
    before = service.trace(first.paper_id)
    request = item(feed.feed_id, doi="10.1/b", payload=b"<item>conflict</item>")
    result = service.submit(request)
    assert result.status == "rejected"
    assert result.conflict_id
    records = service.conflicts(feed_id=feed.feed_id, entry_id="entry-1")
    assert len(records) == 1
    assert records[0].conflict == "entry_doi_changed"
    assert records[0].raw_doi == "10.1/b"
    assert service.conflict_bytes(result.conflict_id) == b"<item>conflict</item>"
    assert service.submit(request) == result
    assert service.trace(first.paper_id) == before
    service.validate_all()


@pytest.mark.parametrize(
    "category",
    [
        "doi_owner_conflict",
        "target_mismatch",
        "version_kind_conflict",
        "entry_doi_changed",
        "explicit_cannot_supplement",
    ],
)
def test_each_rejection_is_independent_queryable_evidence(
    tmp_path: Path, category: str
) -> None:
    service = facts(tmp_path)
    feed = service.register_feed("https://feeds.example/f")
    first = service.submit(
        item(feed.feed_id, doi="10.1/a" if category == "entry_doi_changed" else None)
    )
    owner = service.submit(observation(doi="10.1/b"))
    assert first.paper_id and owner.paper_id
    changes: dict[str, object] = {"payload": b"<item>rejected</item>"}
    if category == "doi_owner_conflict":
        changes["doi"] = "10.1/b"
    elif category == "target_mismatch":
        changes.update(
            target_paper_id=owner.paper_id, target_version_id=owner.version_id
        )
    elif category == "version_kind_conflict":
        changes["version_kind"] = "preprint"
    elif category == "entry_doi_changed":
        changes["doi"] = "10.1/c"
    else:
        changes.update(
            doi="10.1/c",
            target_paper_id=first.paper_id,
            target_version_id=first.version_id,
        )
    before = service.trace(first.paper_id)
    request = item(feed.feed_id, **changes)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(service.submit, [request, request]))
    assert results[0] == results[1]
    assert results[0].conflict_id
    (record,) = service.conflicts(paper_id=first.paper_id)
    assert record.conflict == (
        "target_mismatch" if category == "explicit_cannot_supplement" else category
    )
    assert service.conflict_assertion(record.conflict_id)["entry_id"] == "entry-1"
    assert service.trace(first.paper_id) == before
    changed = service.submit(item(feed.feed_id, **{**changes, "parser_version": 2}))
    assert changed.conflict_id != record.conflict_id
    assert len(service.conflicts(feed_id=feed.feed_id)) == 2


def test_unassociated_rejection_and_restore_retain_bytes_and_receipt(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    root.mkdir()
    service = facts(root)
    feed = service.register_feed("https://feeds.example/f")
    request = item(
        feed.feed_id,
        target_version_id="00000000-0000-0000-0000-000000000001",
        target_paper_id="00000000-0000-0000-0000-000000000002",
    )
    result = service.submit(request)
    assert result.conflict_id
    (record,) = service.conflicts(conflict_id=result.conflict_id)
    assert record.version_ids == ()
    assert service.data_root is not None
    batch = create_backup(service.database, service.data_root, tmp_path / "backups")
    root.rename(tmp_path / "unavailable")
    restored = restore_backup(batch.batch_dir, tmp_path / "restored")
    service = PaperFacts(restored.target_dir / "database.sqlite3", restored.target_dir)
    assert service.conflicts() == (record,)
    assert service.conflict_bytes(record.conflict_id) == request["payload"]
    assert service.submit(request) == result
    service.validate_all()


def test_failed_conflict_transaction_has_no_record_and_replay_can_succeed(
    tmp_path: Path,
) -> None:
    service = facts(tmp_path)
    feed = service.register_feed("https://feeds.example/f")
    service.submit(item(feed.feed_id, doi="10.1/a"))
    request = item(feed.feed_id, doi="10.1/b", payload=b"failed conflict commit")
    with closing(sqlite3.connect(service.database)) as connection:
        connection.execute(
            "CREATE TRIGGER reject_conflict BEFORE INSERT ON "
            "paper_identity_conflicts BEGIN SELECT RAISE(ABORT, 'injected'); END"
        )
    result = service.submit(request)
    assert result.reason == "corrupt_reference"
    assert result.conflict_id is None
    assert service.conflicts() == ()
    with closing(sqlite3.connect(service.database)) as connection:
        connection.execute("DROP TRIGGER reject_conflict")
    assert service.submit(request).conflict_id


def test_conflict_reference_corruption_is_controlled(tmp_path: Path) -> None:
    service = facts(tmp_path)
    feed = service.register_feed("https://feeds.example/f")
    service.submit(item(feed.feed_id, doi="10.1/a"))
    service.submit(item(feed.feed_id, doi="10.1/b", payload=b"conflict"))
    with closing(sqlite3.connect(service.database)) as connection:
        connection.execute(
            "UPDATE paper_identity_conflicts SET payload_sha256 = ?", ("0" * 64,)
        )
        connection.commit()
    with pytest.raises(PaperError, match="corrupt_reference"):
        service.conflicts()
    with pytest.raises(PaperError, match="corrupt_reference"):
        service.validate_all()


def test_previous_revision_upgrade_preserves_nonempty_receipts(tmp_path: Path) -> None:
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine

    from paper_radar.storage import database as database_module
    from paper_radar.storage.database import upgrade_database

    service = facts(tmp_path)
    feed = service.register_feed("https://feeds.example/f")
    request = item(feed.feed_id, doi="10.1/a")
    receipt = service.submit(request)
    assert receipt.paper_id
    trace = service.trace(receipt.paper_id)
    config = Config()
    config.set_main_option(
        "script_location", str(Path(database_module.__file__).parent / "migrations")
    )
    engine = create_engine(f"sqlite:///{service.database}")
    try:
        with engine.connect() as connection:
            config.attributes["connection"] = connection
            command.downgrade(config, "a1001_fixture_audit")
            connection.commit()
    finally:
        engine.dispose()
    upgrade_database(service.database)
    assert service.submit(request) == receipt
    assert service.trace(receipt.paper_id) == trace
    assert service.conflicts() == ()
