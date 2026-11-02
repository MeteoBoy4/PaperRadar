"""Issue #146 production parser migration preserves nonempty historical checks."""

from pathlib import Path

import httpx
from alembic import command
from alembic.config import Config

from paper_radar.feed_ingestion import JGRFeed
from paper_radar.fixture_audit.source_http import SourceHTTPExecutor
from paper_radar.sources.feeds import endpoint
from paper_radar.storage import database as database_module
from paper_radar.storage.database import DatabaseMode, open_database, upgrade_database
from tests.feed_support import facts
from tests.test_wiley_abstract_v2 import NOTE, feed


def test_previous_revision_check_keeps_identity_after_upgrade(tmp_path: Path) -> None:
    papers = facts(tmp_path)
    registered = papers.register_feed(endpoint("jgr"))
    assert papers.data_root
    service = JGRFeed(
        papers.database,
        papers.data_root,
        http=SourceHTTPExecutor(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    200, content=feed(f"<description>{NOTE}</description>")
                )
            )
        ),
    )
    original = service.check(
        registered.feed_id, request_id="v1", contact_email="audit@example.org"
    )
    assert original.complete and original.items[0].result
    config = Config()
    config.set_main_option(
        "script_location", str(Path(database_module.__file__).parent / "migrations")
    )
    engine = open_database(papers.database, mode=DatabaseMode.READ_WRITE)
    try:
        with engine.connect() as connection:
            config.attributes["connection"] = connection
            command.downgrade(config, "feed06_language_provenance")
            connection.commit()
    finally:
        engine.dispose()
    upgrade_database(papers.database)
    assert service.replay(original.check_id) == original
    service.validate_all()
