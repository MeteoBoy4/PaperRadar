"""元数据取得的故障重放、隔离恢复和引用闭包。"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import pytest

from paper_radar.backup import BackupError, create_backup
from paper_radar.backup.restore import restore_backup
from paper_radar.feed_metadata import JGRMetadata
from paper_radar.papers import PaperFacts
from paper_radar.papers.errors import PaperError
from tests.artifact_support import fail_sql
from tests.test_feed_metadata import DOI, FULL, enrich, setup_metadata


def response(request: httpx.Request) -> httpx.Response:
    if "doiRA" in str(request.url):
        return httpx.Response(200, json=[{"DOI": DOI, "RA": "Crossref"}])
    if request.url.host == "api.crossref.org":
        return httpx.Response(
            200,
            json={"message": {"DOI": DOI, "title": ["Stable title"], "abstract": FULL}},
        )
    return httpx.Response(404)


def test_metadata_restore_replays_bytes_and_frozen_result_without_original(
    tmp_path: Path,
) -> None:
    original = tmp_path / "original"
    original.mkdir()
    papers, paper_id, service = setup_metadata(original, response)
    result = enrich(service, paper_id)
    content = service.content(result.request_key)
    raw = service.source_bytes(result.request_key, "registry_crossref")
    assert papers.data_root
    batch = create_backup(papers.database, papers.data_root, tmp_path / "backups")
    original.rename(tmp_path / "unavailable")
    restored = restore_backup(batch.batch_dir, tmp_path / "restored")
    copied = JGRMetadata(restored.target_dir / "database.sqlite3", restored.target_dir)
    assert copied.replay(result.request_key) == result
    assert copied.content(result.request_key) == content
    assert copied.source_bytes(result.request_key, "registry_crossref") == raw
    assert enrich(copied, paper_id) == result
    copied.validate_all()


def test_fact_commit_then_route_failure_reuses_source_and_identity(
    tmp_path: Path,
) -> None:
    papers, paper_id, service = setup_metadata(tmp_path, response)
    with (
        fail_sql("UPDATE feed_metadata_routes"),
        pytest.raises(PaperError, match="corrupt_reference"),
    ):
        enrich(service, paper_id)
    before = papers.trace(paper_id)
    result = enrich(service, paper_id)
    after = papers.trace(paper_id)
    assert after.acquisitions == before.acquisitions
    assert after.versions == before.versions
    assert result.minimum_complete
    service.validate_all()


def test_concurrent_same_request_keeps_one_route_observation(tmp_path: Path) -> None:
    papers, paper_id, service = setup_metadata(tmp_path, response)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: enrich(service, paper_id), range(2)))
    assert results[0] == results[1]
    trace = papers.trace(paper_id)
    assert (
        len([value for value in trace.acquisitions if value.source_kind == "registry"])
        == 1
    )
    service.validate_all()


def test_metadata_corruption_is_controlled_in_read_and_backup(tmp_path: Path) -> None:
    import sqlite3
    from contextlib import closing

    papers, paper_id, service = setup_metadata(tmp_path, response)
    result = enrich(service, paper_id)
    with closing(sqlite3.connect(papers.database)) as connection:
        connection.execute("UPDATE feed_metadata_routes SET view_sha256='bad'")
        connection.commit()
    with pytest.raises(PaperError, match="corrupt_reference"):
        service.replay(result.request_key)
    assert papers.data_root
    with pytest.raises(BackupError, match="制品登记闭包损坏"):
        create_backup(papers.database, papers.data_root, tmp_path / "backups")


def test_nonempty_previous_revision_migrates_and_preserves_facts(
    tmp_path: Path,
) -> None:
    import sqlite3
    from contextlib import closing

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine

    from paper_radar.storage import database as database_module
    from paper_radar.storage.database import upgrade_database

    papers, paper_id, _service = setup_metadata(tmp_path, response)
    before = papers.trace(paper_id)
    target = tmp_path / "previous.sqlite"
    config = Config()
    config.set_main_option(
        "script_location", str(Path(database_module.__file__).parent / "migrations")
    )
    engine = create_engine(f"sqlite:///{target}")
    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        config.attributes["connection"] = connection
        command.upgrade(config, "feed03_feed_acquisition")
        connection.commit()
    engine.dispose()
    with (
        closing(sqlite3.connect(papers.database)) as source,
        closing(sqlite3.connect(target)) as previous,
    ):
        names = [
            row[0]
            for row in previous.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT IN ('sqlite_sequence','alembic_version')"
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
    assert upgrade_database(target) == "feed04_metadata"
    assert PaperFacts(target, papers.data_root).trace(paper_id) == before
    assert papers.data_root
    JGRMetadata(target, papers.data_root).validate_all()
