from pathlib import Path

import pytest

from paper_radar.papers import PaperFacts
from paper_radar.screening_tasks import ScreeningTasks, TaskError
from tests.a7_registration_support import Archive, request_for
from tests.a7_value_support import value_archive
from tests.feed_support import item


def test_language_freezes_discoveries_with_value_budget(tmp_path: Path) -> None:
    data = value_archive(tmp_path)
    papers = PaperFacts(data.database, data.data_root)
    feed = papers.register_feed("https://www.iapjournals.ac.cn/dqkx/rss/current.xml")
    papers.submit(item(feed.feed_id, doi="10.1234/abc"))
    service = ScreeningTasks(data.database, data.data_root)
    request = request_for(data, stage="value")
    receipt = service.register_feed_value(request)
    assert service.load_input(receipt.receipt_id).original_title_is_zh is True
    basis = service.language_basis(receipt.receipt_id)
    assert basis["status"] == "frozen"
    assert basis["policy_version"] == "v1"
    assert basis["sources"][0]["feed_id"] == feed.feed_id
    assert service.register_feed_value(request) == receipt
    service.validate_all()


def test_missing_language_refuses_without_creating_budget(tmp_path: Path) -> None:
    data = value_archive(tmp_path)
    service = ScreeningTasks(data.database, data.data_root)
    with pytest.raises(TaskError, match="language_missing"):
        service.register_feed_value(request_for(data, stage="value"))
    assert service.receipts(data.paper_id) == ()


@pytest.mark.parametrize(
    ("journal", "expected"),
    [("dqkx", True), ("aies", False), ("jgr", False), ("qjrms", False)],
)
def test_explicit_database_feed_binding_and_same_journal_multiple_feeds(
    tmp_path: Path, journal: str, expected: bool
) -> None:
    data = value_archive(tmp_path)
    papers = PaperFacts(data.database, data.data_root)
    service = ScreeningTasks(data.database, data.data_root)
    for number in range(2):
        feed = papers.register_feed(f"https://example.test/feed/{number}")
        service.bind_feed_journal(feed.feed_id, journal)
        papers.submit(
            item(feed.feed_id, doi="10.1234/abc", payload=f"item-{number}".encode())
        )
    receipt = service.register_feed_value(request_for(data, stage="value"))
    assert service.load_input(receipt.receipt_id).original_title_is_zh is expected
    assert len(service.language_basis(receipt.receipt_id)["sources"]) == 2
    service.validate_all()


def test_later_ambiguous_sources_keep_frozen_value_and_reject_new_budget(
    tmp_path: Path,
) -> None:
    data = value_archive(tmp_path)
    papers = PaperFacts(data.database, data.data_root)
    service = ScreeningTasks(data.database, data.data_root)
    for journal in ("aies", "jgr"):
        feed = papers.register_feed(f"https://example.test/{journal}")
        service.bind_feed_journal(feed.feed_id, journal)
        papers.submit(item(feed.feed_id, doi="10.1234/abc", payload=journal.encode()))
    request = request_for(data, stage="value")
    receipt = service.register_feed_value(request)
    before = service.language_basis(receipt.receipt_id)
    feed = papers.register_feed("https://www.iapjournals.ac.cn/dqkx/rss/current.xml")
    papers.submit(item(feed.feed_id, doi="10.1234/abc", payload=b"dqkx"))
    assert service.language_status(data.paper_id)["status"] == "ambiguous"
    assert {row["status"] for row in service.language_observations(data.paper_id)} == {
        "resolved",
        "ambiguous",
    }
    assert (
        service.register_feed_value(request, policy_version="future-policy") == receipt
    )
    assert service.language_basis(receipt.receipt_id) == before
    from tests.test_paper_mapping import screening_fields
    from tests.test_paper_service import observation

    fields = screening_fields()
    fields["title"] = {"value": "Changed canonical title", "locator": "title"}
    papers.submit(observation(payload=b"changed-title", fields=fields))
    with pytest.raises(TaskError, match="language_ambiguous"):
        service.register_feed_value(
            request_for(data, stage="value", scheduled_day="2026-01-02")
        )
    assert len(service.receipts(data.paper_id)) == 1


def test_historical_explicit_bool_does_not_acquire_false_provenance(
    tmp_path: Path,
) -> None:
    data = value_archive(tmp_path)
    service = ScreeningTasks(data.database, data.data_root)
    receipt = service.register(
        request_for(data, stage="value", original_title_is_zh=True)
    )
    assert service.register_feed_value(request_for(data, stage="value")) == receipt
    assert service.language_basis(receipt.receipt_id) == {
        "status": "historical_unrecorded",
        "sources": [],
        "original_title_is_zh": True,
    }


def test_language_basis_survives_isolated_restore(tmp_path: Path) -> None:
    from paper_radar.backup import create_backup
    from paper_radar.backup.restore import restore_backup

    original = tmp_path / "original"
    original.mkdir()
    data = value_archive(original)
    papers = PaperFacts(data.database, data.data_root)
    feed = papers.register_feed("https://www.iapjournals.ac.cn/dqkx/rss/current.xml")
    papers.submit(item(feed.feed_id, doi="10.1234/abc"))
    service = ScreeningTasks(data.database, data.data_root)
    request = request_for(data, stage="value")
    receipt = service.register_feed_value(request)
    basis = service.language_basis(receipt.receipt_id)
    batch = create_backup(data.database, data.data_root, tmp_path / "backups")
    original.rename(tmp_path / "unavailable")
    copied = restore_backup(batch.batch_dir, tmp_path / "restored")
    restored = ScreeningTasks(copied.target_dir / "database.sqlite3", copied.target_dir)
    assert restored.language_basis(receipt.receipt_id) == basis
    assert restored.register_feed_value(request) == receipt
    restored.validate_all()


def discovered(data: Archive, journal: str = "dqkx") -> ScreeningTasks:
    papers = PaperFacts(data.database, data.data_root)
    feed = papers.register_feed(f"https://example.test/{journal}")
    service = ScreeningTasks(data.database, data.data_root)
    service.bind_feed_journal(feed.feed_id, journal)
    papers.submit(item(feed.feed_id, doi="10.1234/abc"))
    return service


def test_policy_identity_and_feed_binding_are_immutable(tmp_path: Path) -> None:
    data = value_archive(tmp_path)
    service = discovered(data)
    request = request_for(data, stage="value")
    service.register_language_policy("v2")
    service.register_language_policy("v2")
    receipt = service.register_feed_value(request, policy_version="v2")
    basis = service.language_basis(receipt.receipt_id)
    assert basis["status"] == "frozen"
    assert basis["policy_version"] == "v2"
    assert service.register_feed_value(request, policy_version="v1") == receipt
    feed = PaperFacts(data.database).register_feed("https://example.test/dqkx")
    with pytest.raises(TaskError, match="context_conflict"):
        service.bind_feed_journal(feed.feed_id, "jgr")
    service.validate_all()


def test_provenance_commit_failure_rolls_back_budget_and_replay_is_atomic(
    tmp_path: Path,
) -> None:
    from tests.artifact_support import fail_sql

    data = value_archive(tmp_path)
    service = discovered(data)
    request = request_for(data, stage="value")
    with (
        fail_sql("INSERT INTO screening_language_basis"),
        pytest.raises(TaskError, match="corrupt_reference"),
    ):
        service.register_feed_value(request)
    assert service.receipts(data.paper_id) == ()
    receipt = service.register_feed_value(request)
    assert service.language_basis(receipt.receipt_id)["status"] == "frozen"


def test_concurrent_production_requests_share_one_frozen_budget(tmp_path: Path) -> None:
    from concurrent.futures import ThreadPoolExecutor

    data = value_archive(tmp_path)
    service = discovered(data)
    request = request_for(data, stage="value")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(service.register_feed_value, [request, request]))
    assert results[0] == results[1]
    assert len(service.receipts(data.paper_id)) == 1
    service.validate_all()


def test_corrupted_language_basis_is_refused_in_query_and_backup(
    tmp_path: Path,
) -> None:
    import sqlite3
    from contextlib import closing

    from paper_radar.backup import BackupError, create_backup

    data = value_archive(tmp_path)
    service = discovered(data)
    receipt = service.register_feed_value(request_for(data, stage="value"))
    with closing(sqlite3.connect(data.database)) as connection:
        connection.execute("UPDATE title_language_resolutions SET basis_json='{}'")
        connection.commit()
    with pytest.raises(TaskError, match="corrupt_reference"):
        service.language_basis(receipt.receipt_id)
    with pytest.raises(BackupError, match="制品登记闭包损坏"):
        create_backup(data.database, data.data_root, tmp_path / "backups")


def test_previous_nonempty_revision_upgrade_keeps_old_receipts(tmp_path: Path) -> None:
    import sqlite3
    from contextlib import closing

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine

    from paper_radar.storage import database as database_module
    from paper_radar.storage.database import upgrade_database

    data = value_archive(tmp_path)
    service = ScreeningTasks(data.database, data.data_root)
    receipt = service.register(
        request_for(data, stage="value", original_title_is_zh=False)
    )
    target = tmp_path / "previous.sqlite"
    config = Config()
    config.set_main_option(
        "script_location", str(Path(database_module.__file__).parent / "migrations")
    )
    engine = create_engine(f"sqlite:///{target}")
    with engine.connect() as connection:
        config.attributes["connection"] = connection
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        command.upgrade(config, "feed01_identity_conflicts")
        connection.commit()
    engine.dispose()
    with (
        closing(sqlite3.connect(data.database)) as source,
        closing(sqlite3.connect(target)) as previous,
    ):
        names = [
            row[0]
            for row in previous.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT IN ('alembic_version','sqlite_sequence')"
            )
        ]
        for name in names:
            previous.execute(f"DELETE FROM {name}")
            rows = source.execute(f"SELECT * FROM {name}").fetchall()
            if rows:
                previous.executemany(
                    f"INSERT INTO {name} VALUES ({','.join('?' for _ in rows[0])})",
                    rows,
                )
        previous.commit()
    upgrade_database(target)
    copied = ScreeningTasks(target, data.data_root)
    assert copied.get_receipt(receipt.receipt_id) == receipt
    assert (
        copied.language_basis(receipt.receipt_id)["status"] == "historical_unrecorded"
    )
    copied.validate_all()


def test_manual_replay_and_retry_inherit_language_after_new_ambiguity(
    tmp_path: Path,
) -> None:
    from datetime import UTC, datetime

    from paper_radar.screening_tasks import FailureKind, FailureReport

    data = value_archive(tmp_path)
    discovered(data)
    service = ScreeningTasks(
        data.database, data.data_root, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    request = request_for(
        data,
        stage="value",
        source="manual",
        scheduled_day=None,
        request_id="manual-language",
        actor="user",
        reason="read",
    )
    receipt = service.register_feed_value(request)
    for _ in range(2):
        claim = service.claim(receipt.receipt_id)
        service.fail(claim, FailureReport(FailureKind.EXECUTOR_ERROR))
    feed = PaperFacts(data.database, data.data_root).register_feed(
        "https://example.test/jgr"
    )
    service.bind_feed_journal(feed.feed_id, "jgr")
    PaperFacts(data.database, data.data_root).submit(
        item(feed.feed_id, doi="10.1234/abc", payload=b"jgr")
    )
    assert service.register_feed_value(request) == receipt
    retry = service.retry(
        {
            "parent_task_id": receipt.task_id,
            "paper_id": data.paper_id,
            "stage": "value",
            "snapshot_id": data.snapshot_id,
            "request_id": "retry-language",
            "actor": "user",
            "reason": "retry",
        }
    )
    assert service.load_input(retry.receipt_id).original_title_is_zh is True
    assert service.language_basis(retry.receipt_id) == service.language_basis(
        receipt.receipt_id
    )


def test_deleted_production_language_link_is_corruption_not_legacy(
    tmp_path: Path,
) -> None:
    import sqlite3
    from contextlib import closing

    from paper_radar.backup import create_backup
    from paper_radar.backup.manifest import BackupError

    data = value_archive(tmp_path)
    papers = PaperFacts(data.database, data.data_root)
    feed = papers.register_feed("https://www.iapjournals.ac.cn/dqkx/rss/current.xml")
    papers.submit(item(feed.feed_id, doi="10.1234/abc"))
    service = ScreeningTasks(data.database, data.data_root)
    receipt = service.register_feed_value(request_for(data, stage="value"))
    with closing(sqlite3.connect(data.database)) as connection:
        connection.execute(
            "DELETE FROM screening_language_basis WHERE budget_id=?",
            (receipt.budget_id,),
        )
        connection.commit()
    with pytest.raises(TaskError, match="corrupt_reference"):
        service.language_basis(receipt.receipt_id)
    with pytest.raises(TaskError, match="corrupt_reference"):
        service.validate_all()
    with pytest.raises(BackupError) as error:
        create_backup(data.database, data.data_root, tmp_path / "backups")
    assert error.value.reason == "registration_invalid"


@pytest.mark.parametrize(
    ("journal", "expected"),
    [("dqkx", True), ("aies", False), ("jgr", False), ("qjrms", False)],
)
def test_shared_default_endpoint_declaration_drives_language(
    tmp_path: Path, journal: str, expected: bool
) -> None:
    from paper_radar.fixture_audit.acquisition_policy import FEED_ENDPOINTS

    data = value_archive(tmp_path)
    papers = PaperFacts(data.database, data.data_root)
    feed = papers.register_feed(
        next(value.url for value in FEED_ENDPOINTS if value.journal == journal)
    )
    papers.submit(item(feed.feed_id, doi="10.1234/abc"))
    tasks = ScreeningTasks(data.database, data.data_root)
    receipt = tasks.register_feed_value(request_for(data, stage="value"))
    assert tasks.language_basis(receipt.receipt_id)["original_title_is_zh"] is expected
