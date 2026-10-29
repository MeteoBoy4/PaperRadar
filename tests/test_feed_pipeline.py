"""Feed生产组合只替换HTTP transport;模型前置显式由调用方提供。"""

import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from paper_radar.backup import create_backup
from paper_radar.backup.restore import restore_backup
from paper_radar.config import compile_config
from paper_radar.feed_pipeline import FeedPipeline, PipelineError
from paper_radar.fixture_audit.acquisition_policy import FEED_ENDPOINTS
from paper_radar.fixture_audit.source_http import SourceHTTPExecutor
from paper_radar.papers import PaperFacts
from paper_radar.screening_tasks import (
    ScreeningTasks,
    SuccessCandidate,
    SuccessReceipt,
    TaskError,
)
from tests.config_test_support import value_inputs
from tests.feed_support import item as feed_item
from tests.test_audit_http import FakeClock

DOI = "10.1029/2025jd043927"
FULL = (
    "This complete synthetic abstract describes atmospheric obser"
    "vations and a reproducible methodology with detailed scienti"
    "fic results."
)


def setup_pipeline(root: Path):
    settings, database = value_inputs(root)
    snapshot = compile_config(settings, database)
    data_root = root / "data"
    feed = PaperFacts(database, data_root).register_feed(
        next(value.url for value in FEED_ENDPOINTS if value.journal == "jgr")
    )
    calls = []

    def respond(request):
        calls.append(str(request.url))
        if "showFeed" in str(request.url):
            return httpx.Response(
                200,
                text=(
                    f"<rss><channel><item><guid>entry-1</guid><doi>{DOI}</doi>"
                    "<title>Feed title</title></item></channel></rss>"
                ),
            )
        if "doiRA" in str(request.url):
            return httpx.Response(200, json=[{"DOI": DOI, "RA": "Crossref"}])
        if request.url.host == "api.crossref.org":
            return httpx.Response(
                200,
                json={
                    "message": {
                        "DOI": DOI,
                        "title": ["Registry title"],
                        "abstract": FULL,
                        "type": "journal-article",
                    }
                },
            )
        return httpx.Response(
            200,
            text=(
                f'<meta name="citation_doi" content="{DOI}">'
                '<meta name="citation_title" content="Publisher title">'
                f'<div class="abstract">{FULL}</div>'
            ),
        )

    clock = FakeClock()
    pipeline = FeedPipeline(
        database,
        data_root,
        http=SourceHTTPExecutor(
            transport=httpx.MockTransport(respond),
            monotonic=clock.monotonic,
            sleep=clock.sleep,
        ),
    )
    return pipeline, feed.feed_id, snapshot.snapshot_id, calls


def boundary(pipeline, paper_id, snapshot_id, value="in_scope"):
    tasks = ScreeningTasks(
        pipeline.database, pipeline.data_root, clock=lambda: datetime.now(UTC)
    )
    request = dict(
        paper_id=paper_id,
        snapshot_id=snapshot_id,
        stage="boundary",
        source="scheduled",
        scheduled_day="2026-01-01",
    )
    receipt = tasks.register(request)
    claim = tasks.claim(receipt.receipt_id)
    success = tasks.submit(
        claim,
        SuccessCandidate(
            (
                f'{{"boundary":"{value}",'
                '"reason_zh":"Atmospheric observations are studied."}'
            ).encode()
        ),
    )
    assert isinstance(success, SuccessReceipt)
    return success.success_id


def test_complete_feed_test_path_freezes_language_and_value_registration(
    tmp_path: Path,
) -> None:
    pipeline, feed_id, snapshot_id, calls = setup_pipeline(tmp_path)
    prepared = pipeline.prepare(
        feed_id, request_id="one", contact_email="contact@example.org"
    )
    (item,) = prepared.items
    assert item.paper_id and item.metadata_request_key
    assert item.metadata.minimum_complete
    success_id = boundary(pipeline, item.paper_id, snapshot_id)
    request = dict(
        paper_id=item.paper_id,
        snapshot_id=snapshot_id,
        stage="value",
        source="scheduled",
        scheduled_day="2026-01-01",
    )
    registered = pipeline.register_test_value(
        request,
        metadata_request_key=item.metadata_request_key,
        boundary_success_id=success_id,
    )
    assert registered.purpose == "test"
    assert registered.language_basis["original_title_is_zh"] is False
    assert (
        pipeline.register_test_value(
            request,
            metadata_request_key=item.metadata_request_key,
            boundary_success_id=success_id,
        )
        == registered
    )
    assert (
        pipeline.prepare(feed_id, request_id="one", contact_email="contact@example.org")
        == prepared
    )
    assert len(calls) == 4
    assert "Publisher title" not in repr(prepared)
    assert FULL not in repr(prepared)


def prepared_request(root):
    pipeline, feed_id, snapshot_id, calls = setup_pipeline(root)
    prepared = pipeline.prepare(
        feed_id, request_id="one", contact_email="contact@example.org"
    )
    (item,) = prepared.items
    request = dict(
        paper_id=item.paper_id,
        snapshot_id=snapshot_id,
        stage="value",
        source="scheduled",
        scheduled_day="2026-01-01",
    )
    return pipeline, item, request, calls


def test_production_entry_refuses_test_source_without_value_budget(
    tmp_path: Path,
) -> None:
    pipeline, item, request, _calls = prepared_request(tmp_path)
    success = boundary(pipeline, item.paper_id, request["snapshot_id"])
    with pytest.raises(PipelineError, match="test_source"):
        pipeline.register_value(
            request,
            metadata_request_key=item.metadata_request_key,
            boundary_success_id=success,
        )
    assert all(
        value.stage == "boundary" for value in pipeline.tasks.receipts(item.paper_id)
    )


@pytest.mark.parametrize("value", ["in_scope", "out_of_scope"])
def test_no_current_boundary_or_out_of_scope_cannot_register_even_test(
    tmp_path: Path, value: str
) -> None:
    pipeline, item, request, _calls = prepared_request(tmp_path)
    success = boundary(pipeline, item.paper_id, request["snapshot_id"], value)
    reason = "out_of_scope" if value == "out_of_scope" else "boundary_missing"
    with pytest.raises(PipelineError, match=reason):
        pipeline.register_test_value(
            request,
            metadata_request_key=item.metadata_request_key,
            boundary_success_id=success if value == "out_of_scope" else "missing",
        )


def test_value_and_language_and_composition_proof_commit_together(
    tmp_path: Path,
) -> None:
    pipeline, item, request, _calls = prepared_request(tmp_path)
    success = boundary(pipeline, item.paper_id, request["snapshot_id"])
    with closing(sqlite3.connect(pipeline.database)) as connection:
        connection.execute(
            "CREATE TRIGGER fail_proof BEFORE INSERT ON feed_value_regist"
            "rations BEGIN SELECT RAISE(ABORT,'injected'); END"
        )
    with pytest.raises(TaskError, match="corrupt_reference"):
        pipeline.register_test_value(
            request,
            metadata_request_key=item.metadata_request_key,
            boundary_success_id=success,
        )
    assert all(
        value.stage == "boundary" for value in pipeline.tasks.receipts(item.paper_id)
    )
    with closing(sqlite3.connect(pipeline.database)) as connection:
        connection.execute("DROP TRIGGER fail_proof")
    registered = pipeline.register_test_value(
        request,
        metadata_request_key=item.metadata_request_key,
        boundary_success_id=success,
    )
    assert registered.language_basis["status"] == "frozen"
    pipeline.validate_all()


def test_later_language_conflict_does_not_rewrite_exact_registration(
    tmp_path: Path,
) -> None:
    pipeline, item, request, _calls = prepared_request(tmp_path)
    success = boundary(pipeline, item.paper_id, request["snapshot_id"])
    registered = pipeline.register_test_value(
        request,
        metadata_request_key=item.metadata_request_key,
        boundary_success_id=success,
    )
    feed = pipeline.papers.register_feed(
        "https://www.iapjournals.ac.cn/dqkx/rss/current.xml"
    )
    pipeline.papers.submit(
        feed_item(feed.feed_id, doi=DOI, payload=b"later cross journal source")
    )
    assert pipeline.tasks.language_status(item.paper_id)["status"] == "ambiguous"
    assert (
        pipeline.register_test_value(
            request,
            metadata_request_key=item.metadata_request_key,
            boundary_success_id=success,
        )
        == registered
    )
    pipeline.validate_all()


def test_isolated_combination_restore_preserves_metadata_language_budget_and_proof(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    root.mkdir()
    pipeline, item, request, _calls = prepared_request(root)
    success = boundary(pipeline, item.paper_id, request["snapshot_id"])
    registered = pipeline.register_test_value(
        request,
        metadata_request_key=item.metadata_request_key,
        boundary_success_id=success,
    )
    feed_id = pipeline.papers.trace(item.paper_id).discoveries[0].feed_id
    rejected_bytes = b"<item>unassociated rejected original</item>"
    rejected = pipeline.papers.submit(
        feed_item(
            feed_id,
            entry_id="orphan",
            payload=rejected_bytes,
            target_version_id="00000000-0000-0000-0000-000000000001",
            target_paper_id="00000000-0000-0000-0000-000000000002",
        )
    )
    assert rejected.conflict_id
    expected = pipeline.trace(item.paper_id)
    raw = pipeline.metadata.source_bytes(item.metadata_request_key, "publisher")
    batch = create_backup(pipeline.database, pipeline.data_root, tmp_path / "backups")
    root.rename(tmp_path / "unavailable")
    restored = restore_backup(batch.batch_dir, tmp_path / "restored")
    restored_pipeline = FeedPipeline(
        restored.target_dir / "database.sqlite3",
        restored.target_dir,
        http=SourceHTTPExecutor(
            transport=httpx.MockTransport(
                lambda request: (_ for _ in ()).throw(
                    AssertionError("no HTTP on replay")
                )
            )
        ),
    )
    assert restored_pipeline.trace(item.paper_id) == expected
    assert (
        restored_pipeline.papers.conflict_bytes(rejected.conflict_id) == rejected_bytes
    )
    assert (
        restored_pipeline.metadata.source_bytes(item.metadata_request_key, "publisher")
        == raw
    )
    assert (
        restored_pipeline.register_test_value(
            request,
            metadata_request_key=item.metadata_request_key,
            boundary_success_id=success,
        )
        == registered
    )
    restored_pipeline.validate_all()


def test_stale_metadata_is_not_a_new_value_registration_authority(
    tmp_path: Path,
) -> None:
    pipeline, item, request, _calls = prepared_request(tmp_path)
    success = boundary(pipeline, item.paper_id, request["snapshot_id"])
    from tests.test_paper_service import observation

    pipeline.papers.submit(
        observation(
            doi=DOI,
            payload=b"later publisher",
            observed_at=datetime.now(UTC),
            fields={"title": {"value": "Changed title", "locator": "title"}},
        )
    )
    with pytest.raises(PipelineError, match="metadata_stale"):
        pipeline.register_test_value(
            request,
            metadata_request_key=item.metadata_request_key,
            boundary_success_id=success,
        )


def test_missing_metadata_cannot_register_test_value(tmp_path: Path) -> None:
    pipeline, feed_id, snapshot_id, _calls = setup_pipeline(tmp_path)
    saved = pipeline.papers.submit(feed_item(feed_id, payload=b"no DOI no abstract"))
    metadata = pipeline.metadata.enrich(
        saved.paper_id, request_id="missing", contact_email="contact@example.org"
    )
    request = dict(
        paper_id=saved.paper_id,
        snapshot_id=snapshot_id,
        stage="value",
        source="scheduled",
        scheduled_day="2026-01-01",
    )
    with pytest.raises(PipelineError, match="metadata_incomplete"):
        pipeline.register_test_value(
            request,
            metadata_request_key=metadata.request_key,
            boundary_success_id="missing",
        )
    assert pipeline.tasks.receipts(saved.paper_id) == ()


def test_concurrent_combination_registration_replays_one_frozen_basis(
    tmp_path: Path,
) -> None:
    from concurrent.futures import ThreadPoolExecutor

    pipeline, item, request, _calls = prepared_request(tmp_path)
    success = boundary(pipeline, item.paper_id, request["snapshot_id"])

    def register(_):
        return pipeline.register_test_value(
            request,
            metadata_request_key=item.metadata_request_key,
            boundary_success_id=success,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(register, range(2)))
    assert results[0] == results[1]
    assert (
        sum(value.stage == "value" for value in pipeline.tasks.receipts(item.paper_id))
        == 1
    )
    pipeline.validate_all()


def test_nonempty_metadata_revision_upgrades_to_composition_without_rewriting_facts(
    tmp_path: Path,
) -> None:
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine

    from paper_radar.storage import database as database_module
    from paper_radar.storage.database import upgrade_database

    pipeline, item, request, _calls = prepared_request(tmp_path)
    expected = pipeline.papers.trace(item.paper_id)
    config = Config()
    config.set_main_option(
        "script_location", str(Path(database_module.__file__).parent / "migrations")
    )
    engine = create_engine(f"sqlite:///{pipeline.database}")
    try:
        with engine.connect() as connection:
            config.attributes["connection"] = connection
            command.downgrade(config, "feed04_metadata")
            connection.commit()
    finally:
        engine.dispose()
    upgrade_database(pipeline.database)
    assert pipeline.papers.trace(item.paper_id) == expected
    assert pipeline.metadata.replay(item.metadata_request_key).minimum_complete
    success = boundary(pipeline, item.paper_id, request["snapshot_id"])
    assert (
        pipeline.register_test_value(
            request,
            metadata_request_key=item.metadata_request_key,
            boundary_success_id=success,
        ).language_basis["status"]
        == "frozen"
    )


def test_corrupt_combination_proof_refuses_replay_and_backup(tmp_path: Path) -> None:
    from paper_radar.backup.manifest import BackupError

    pipeline, item, request, _calls = prepared_request(tmp_path)
    success = boundary(pipeline, item.paper_id, request["snapshot_id"])
    pipeline.register_test_value(
        request,
        metadata_request_key=item.metadata_request_key,
        boundary_success_id=success,
    )
    with closing(sqlite3.connect(pipeline.database)) as connection:
        connection.execute(
            "UPDATE feed_value_registrations SET basis_sha256=?", ("0" * 64,)
        )
        connection.commit()
    with pytest.raises(TaskError, match="corrupt_reference"):
        pipeline.register_test_value(
            request,
            metadata_request_key=item.metadata_request_key,
            boundary_success_id=success,
        )
    with pytest.raises(BackupError) as error:
        create_backup(pipeline.database, pipeline.data_root, tmp_path / "backups")
    assert error.value.reason == "registration_invalid"
