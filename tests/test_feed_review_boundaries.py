"""审阅回归通过公共读面拒绝已重算外层哈希的未知状态。"""

import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import httpx
import pytest

from paper_radar.papers.errors import PaperError
from tests.test_feed_ingestion import FEED, feed_service, run_check
from tests.test_feed_metadata import setup_metadata


def test_unknown_item_reason_is_rejected_by_public_replay(tmp_path: Path) -> None:
    papers, feed, service = feed_service(
        tmp_path, lambda request: httpx.Response(200, content=FEED)
    )
    check = run_check(service, feed)
    with closing(sqlite3.connect(papers.database)) as connection:
        raw = connection.execute(
            "SELECT result_json FROM feed_production_items WHERE check_id=? "
            "AND position=1",
            (check.check_id,),
        ).fetchone()[0]
        value = json.loads(raw)
        value["reason"] = "unknown_reason"
        changed = json.dumps(value)
        checksum = hashlib.sha256((check.check_id + "1" + changed).encode()).hexdigest()
        connection.execute(
            "UPDATE feed_production_items SET result_json=?, result_sha256=? "
            "WHERE check_id=? "
            "AND position=1",
            (changed, checksum, check.check_id),
        )
        connection.commit()
    with pytest.raises(PaperError, match="corrupt_reference"):
        service.replay(check.check_id)


def test_unknown_metadata_reason_is_rejected_by_public_replay(tmp_path: Path) -> None:
    papers, paper_id, service = setup_metadata(
        tmp_path, lambda request: httpx.Response(404)
    )
    result = service.enrich(
        paper_id, request_id="one", contact_email="contact@example.org"
    )
    with closing(sqlite3.connect(papers.database)) as connection:
        raw = connection.execute(
            "SELECT view_json FROM feed_metadata_routes WHERE request_key=? "
            "AND route='publisher'",
            (result.request_key,),
        ).fetchone()[0]
        value = json.loads(raw)
        value["reason"] = "unknown_reason"
        changed = json.dumps(value)
        checksum = hashlib.sha256((result.request_key + changed).encode()).hexdigest()
        connection.execute(
            "UPDATE feed_metadata_routes SET view_json=?, view_sha256=? "
            "WHERE request_key=? "
            "AND route='publisher'",
            (changed, checksum, result.request_key),
        )
        connection.commit()
    with pytest.raises(PaperError, match="corrupt_reference"):
        service.replay(result.request_key)


def test_metadata_database_error_uses_metadata_path(tmp_path: Path) -> None:
    papers, paper_id, service = setup_metadata(
        tmp_path, lambda request: httpx.Response(404)
    )
    with closing(sqlite3.connect(papers.database)) as connection:
        connection.execute(
            "CREATE TRIGGER fail_route BEFORE INSERT ON feed_metadata_routes "
            "BEGIN SELECT RAISE(ABORT,'injected'); END"
        )
    with pytest.raises(PaperError, match="corrupt_reference") as error:
        service.enrich(paper_id, request_id="one", contact_email="contact@example.org")
    assert error.value.path == "metadata"


def test_provenance_requirement_migration_preserves_production_and_legacy_budgets(
    tmp_path: Path,
) -> None:
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine

    from paper_radar.papers import PaperFacts
    from paper_radar.screening_tasks import ScreeningTasks
    from paper_radar.storage import database as database_module
    from paper_radar.storage.database import upgrade_database
    from tests.a7_registration_support import request_for
    from tests.a7_value_support import value_archive
    from tests.feed_support import item
    from tests.test_paper_mapping import screening_fields
    from tests.test_paper_service import observation

    data = value_archive(tmp_path)
    papers = PaperFacts(data.database, data.data_root)
    feed = papers.register_feed("https://www.iapjournals.ac.cn/dqkx/rss/current.xml")
    papers.submit(item(feed.feed_id, doi="10.1234/abc"))
    tasks = ScreeningTasks(data.database, data.data_root)
    produced = tasks.register_feed_value(request_for(data, stage="value"))
    other = papers.submit(observation(doi="10.1234/legacy", fields=screening_fields()))
    legacy = tasks.register(
        request_for(
            data, stage="value", paper_id=other.paper_id, original_title_is_zh=False
        )
    )
    expected = tasks.language_basis(produced.receipt_id)
    config = Config()
    config.set_main_option(
        "script_location", str(Path(database_module.__file__).parent / "migrations")
    )
    engine = create_engine(f"sqlite:///{data.database}")
    try:
        with engine.connect() as connection:
            config.attributes["connection"] = connection
            command.downgrade(config, "feed05_composition")
            connection.commit()
    finally:
        engine.dispose()
    upgrade_database(data.database)
    assert tasks.get_receipt(produced.receipt_id) == produced
    assert tasks.language_basis(produced.receipt_id) == expected
    assert tasks.language_basis(legacy.receipt_id)["status"] == "historical_unrecorded"
    with closing(sqlite3.connect(data.database)) as connection:
        connection.execute(
            "DELETE FROM screening_language_basis WHERE budget_id=?",
            (produced.budget_id,),
        )
        connection.commit()
    from paper_radar.screening_tasks import TaskError

    with pytest.raises(TaskError, match="corrupt_reference"):
        tasks.language_basis(produced.receipt_id)


def test_historical_audit_feed_container_stays_distinct_from_production(
    tmp_path: Path,
) -> None:
    from paper_radar.sources.feeds import FEED_SUBSCRIPTIONS
    from tests.audit_matrix_support import MAIN, MatrixSources
    from tests.audit_sampling_support import CODE, sampling_service

    endpoint = next(value.url for value in FEED_SUBSCRIPTIONS if value.journal == "jgr")
    legacy = "Historical audit entry abstract with sufficient detail. " * 3
    raw = (
        '<rss xmlns:dc="http://purl.org/dc/elements/1.1/"><channel>'
        "<entry><title>Historical entry</title>"
        f"<description>{legacy}</description></entry>"
        "<item><guid>10.1029/jgr.synthetic</guid><dc:type>article</dc:type>"
        "<title>Physical item</title>"
        f"<description>{MAIN.replace('<', '&lt;')}</description></item>"
        "</channel></rss>"
    ).encode()
    sources = MatrixSources()
    sources.feeds[endpoint] = raw
    (tmp_path / "audit").mkdir()
    (tmp_path / "production").mkdir()
    audit = sampling_service(tmp_path / "audit", sources)
    view = audit.run_audit(contact_email="audit@example.org", code_identity=CODE)
    row = next(
        value
        for value in view.matrix
        if value.request.journal == "jgr" and value.request.route == "feed"
    )
    candidate = next(value for value in row.candidates if value.field == "abstract")
    assert (
        audit.read_audit_text(view.plan.plan_id, candidate.candidate_id)
        == legacy.strip()
    )
    papers, feed, production = feed_service(
        tmp_path / "production", lambda request: httpx.Response(200, content=raw)
    )
    result = run_check(production, feed)
    paper_id = result.items[0].result.paper_id if result.items[0].result else None
    assert paper_id
    assert papers.show(paper_id).fields["title"].value == "Physical item"
    abstract = papers.show(paper_id).fields["abstract"].value
    from paper_radar.papers.models import AbstractValue

    assert isinstance(abstract, AbstractValue)
    assert abstract.text == MAIN
    audit.validate_all()
    production.validate_all()


@pytest.mark.parametrize(
    "raw",
    [
        b"<rss><item><guid>root-item</guid></item></rss>",
        b"<rss><channel><item><guid>first</guid></item></channel><channel><item><guid>second</guid></item></channel></rss>",
    ],
)
def test_production_rejects_nonunique_or_missing_rss_channel(
    tmp_path: Path, raw: bytes
) -> None:
    papers, feed, service = feed_service(
        tmp_path, lambda request: httpx.Response(200, content=raw)
    )
    result = run_check(service, feed)
    assert result.reason == "invalid_feed"
    assert result.items == () and result.artifact_id is None
    assert papers.conflicts() == ()
    service.validate_all()
