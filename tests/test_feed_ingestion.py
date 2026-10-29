"""JGR生产服务只替换HTTP transport。"""

import sqlite3
from contextlib import closing
from pathlib import Path

import httpx
import pytest

from paper_radar.backup import create_backup
from paper_radar.backup.restore import restore_backup
from paper_radar.feed_ingestion import JGRFeed
from paper_radar.fixture_audit.acquisition_policy import FEED_ENDPOINTS
from paper_radar.fixture_audit.source_http import SourceHTTPExecutor
from paper_radar.papers.errors import PaperError
from tests.feed_support import facts

URL = next(value.url for value in FEED_ENDPOINTS if value.journal == "jgr")
ITEM = (
    b'<item odd="unchanged"><guid>entry-1</guid><title>Original title</title>'
    b"<description>This is a complete synthetic abstract describing measurements, "
    b"methods and results with enough detail to avoid the short text flag."
    b"</description>"
    b"<category>Editorial</category></item>"
)
FEED = b'<rss version="2.0"><channel>' + ITEM + b"</channel></rss>"


def test_jgr_feed_preserves_item_bytes_and_conditional_check(tmp_path: Path) -> None:
    papers = facts(tmp_path)
    feed = papers.register_feed(URL)
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(
                200,
                content=FEED,
                headers={
                    "ETag": '"v1"',
                    "Last-Modified": "Mon, 01 Jan 2024 00:00:00 GMT",
                },
            )
        return httpx.Response(304)

    service = JGRFeed(
        papers.database,
        papers.data_root,
        http=SourceHTTPExecutor(transport=httpx.MockTransport(respond)),
    )
    check = service.check(
        feed.feed_id, request_id="first", contact_email="contact@example.org"
    )
    assert check.reason == "acquired"
    assert check.items[0].result.status == "retained"
    paper_id = check.items[0].result.paper_id
    assert paper_id
    assert papers.show(paper_id).fields["title"].value == "Original title"
    assert papers.show(paper_id).fields["abstract"].value.is_truncated is False
    trace = papers.trace(paper_id)
    assert trace.discoveries[0].item_fingerprint
    assert service.item_bytes(check.check_id, 1) == ITEM
    assert (
        service.check(
            feed.feed_id, request_id="first", contact_email="contact@example.org"
        )
        == check
    )
    assert len(requests) == 1
    second = service.check(
        feed.feed_id, request_id="second", contact_email="contact@example.org"
    )
    assert second.status_code == 304
    assert second.items == ()
    assert second.artifact_id == check.artifact_id
    assert requests[-1].headers["If-None-Match"] == '"v1"'
    assert requests[-1].headers["If-Modified-Since"] == "Mon, 01 Jan 2024 00:00:00 GMT"
    assert papers.trace(paper_id) == trace
    assert service.view(feed.feed_id).last_successful_check == second.checked_at
    service.validate_all()


def feed_service(tmp_path: Path, respond):
    papers = facts(tmp_path)
    feed = papers.register_feed(URL)
    assert papers.data_root is not None
    service = JGRFeed(
        papers.database,
        papers.data_root,
        http=SourceHTTPExecutor(transport=httpx.MockTransport(respond)),
    )
    return papers, feed, service


def run_check(service, feed, key="test"):
    return service.check(
        feed.feed_id, request_id=key, contact_email="contact@example.org"
    )


@pytest.mark.parametrize(
    "status,reason",
    [
        (403, "access_blocked_403"),
        (404, "not_found"),
        (429, "rate_limited"),
        (503, "transient_error"),
        (200, "invalid_feed"),
    ],
)
def test_failed_http_check_is_queryable_without_error_page_retention(
    tmp_path: Path, status: int, reason: str
) -> None:
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(status, content=b"<html>failure</html>")

    _papers, feed, service = feed_service(tmp_path, respond)
    check = run_check(service, feed)
    assert check.reason == reason
    assert check.artifact_id is None
    assert check.items == ()
    assert len(requests) == (2 if status in (429, 503) else 1)
    assert service.replay(check.check_id) == check
    assert service.view(feed.feed_id).last_successful_check is None
    service.validate_all()


def test_unsafe_redirect_is_recorded_without_contact_or_credentials(
    tmp_path: Path,
) -> None:
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(302, headers={"Location": "https://127.0.0.1/private"})

    _papers, feed, service = feed_service(tmp_path, respond)
    check = run_check(service, feed)
    assert check.reason == "disallowed_destination"
    assert len(requests) == 1
    assert "contact@example.org" not in check.model_dump_json()
    assert "127.0.0.1" not in check.model_dump_json()


def test_bad_item_isolated_raw_namespaces_empty_tags_and_all_items_retained(
    tmp_path: Path,
) -> None:
    bad = b"<item><title>Missing entry id</title></item>"
    odd = (
        b'<item attr="a > b"><guid>odd</guid><title>Exact &amp; title<'
        b"/title><prism:section>Letter</prism:section><description/></"
        b"item>"
    )
    body = (
        b'<rss xmlns:prism="http://prismstandard.org/namespaces/basic/2.0/"><channel>'
        + bad
        + odd
        + b"".join(
            f"<item><guid>entry-{n}</guid><title>Title {n}</title></item>".encode()
            for n in range(51)
        )
        + b"</channel></rss>"
    )
    _papers, feed, service = feed_service(
        tmp_path, lambda request: httpx.Response(200, content=body)
    )
    check = run_check(service, feed)
    assert check.complete
    assert len(check.items) == 53
    assert check.items[0].reason == "missing_entry_id"
    assert check.items[0].result is None
    assert service.item_bytes(check.check_id, 2) == odd
    assert check.items[1].raw_categories[0].value == "Letter"
    assert all(
        value.result and value.result.status == "retained" for value in check.items[1:]
    )
    assert check.items[-1].entry_id == "entry-50"
    service.validate_all()


def test_doi_path_extraction_is_separate_from_strict_doi_query_handling(
    tmp_path: Path,
) -> None:
    body = (
        b"<rss><channel><item><guid>entry-1</guid><title>Path DOI</tit"
        b"le><link>https://agupubs.onlinelibrary.wiley.com/doi/abs/10."
        b"1029/2025JD043927</link></item><item><guid>entry-2</guid><ti"
        b"tle>Query ignored</title><link>https://agupubs.onlinelibrary"
        b".wiley.com/doi/?doi=10.1029/hidden</link></item></channel></"
        b"rss>"
    )
    papers, feed, service = feed_service(
        tmp_path, lambda request: httpx.Response(200, content=body)
    )
    check = run_check(service, feed)
    assert check.items[0].doi == "10.1029/2025jd043927"
    assert check.items[1].doi is None
    assert check.items[0].result
    assert (
        papers.show(check.items[0].result.paper_id).fields["source_url"].value
        == "https://agupubs.onlinelibrary.wiley.com/doi/abs/10.1029/2025JD043927"
    )


def test_isolated_restore_can_replay_original_checks_and_item_bytes(
    tmp_path: Path,
) -> None:
    root = tmp_path / "source"
    root.mkdir()
    papers, feed, service = feed_service(
        root,
        lambda request: httpx.Response(200, content=FEED, headers={"ETag": '"v1"'}),
    )
    check = run_check(service, feed)
    expected = service.view(feed.feed_id)
    assert papers.data_root
    batch = create_backup(papers.database, papers.data_root, tmp_path / "backups")
    root.rename(tmp_path / "unavailable")
    restored = restore_backup(batch.batch_dir, tmp_path / "restored")

    def deny(request):
        raise AssertionError("replay must not access HTTP")

    service = JGRFeed(
        restored.target_dir / "database.sqlite3",
        restored.target_dir,
        http=SourceHTTPExecutor(transport=httpx.MockTransport(deny)),
    )
    assert service.view(feed.feed_id) == expected
    assert service.item_bytes(check.check_id, 1) == ITEM
    assert run_check(service, feed) == check
    service.validate_all()


def test_item_commit_fault_resumes_without_duplicate_identity_or_acquisition(
    tmp_path: Path,
) -> None:
    papers, feed, service = feed_service(
        tmp_path, lambda request: httpx.Response(200, content=FEED)
    )
    with closing(sqlite3.connect(papers.database)) as connection:
        connection.execute(
            "CREATE TRIGGER fail_item BEFORE INSERT ON feed_production_it"
            "ems BEGIN SELECT RAISE(ABORT,'injected'); END"
        )
    with pytest.raises(PaperError, match="corrupt_reference"):
        run_check(service, feed)
    (pending,) = service.view(feed.feed_id).checks
    assert not pending.complete
    assert pending.artifact_id
    with closing(sqlite3.connect(papers.database)) as connection:
        connection.execute("DROP TRIGGER fail_item")
    recovered = run_check(service, feed)
    assert recovered.complete
    assert recovered.items[0].result
    paper_id = recovered.items[0].result.paper_id
    assert paper_id
    trace = papers.trace(paper_id)
    assert len(trace.discoveries) == len(trace.acquisitions) == 1
    assert run_check(service, feed) == recovered


def test_wrong_database_feed_identity_is_refused_before_http(tmp_path: Path) -> None:
    papers, _feed, service = feed_service(
        tmp_path,
        lambda request: (_ for _ in ()).throw(AssertionError("must not fetch")),
    )
    other = papers.register_feed(URL + "&extra=unapproved")
    with pytest.raises(PaperError, match="invalid_observation"):
        run_check(service, other)


def test_repeated_changes_supplement_doi_and_conflicts_keep_batch_progress(
    tmp_path: Path,
) -> None:
    materials = iter(
        [
            (
                b"<rss><channel><item><guid>entry-1</guid><title>A</title></it"
                b"em></channel></rss>"
            ),
            (
                b"<rss><channel><item><guid>entry-1</guid><doi>10.1/a</doi><ti"
                b"tle>B</title></item></channel></rss>"
            ),
            (
                b"<rss><channel><item><guid>entry-1</guid><title>A</title></it"
                b"em></channel></rss>"
            ),
            (
                b"<rss><channel><item><guid>entry-1</guid><doi>10.1/b</doi><ti"
                b"tle>Conflict</title></item><item><guid>entry-2</guid><title>"
                b"Survivor</title></item></channel></rss>"
            ),
        ]
    )
    papers, feed, service = feed_service(
        tmp_path, lambda request: httpx.Response(200, content=next(materials))
    )
    first = run_check(service, feed, "a")
    second = run_check(service, feed, "b")
    third = run_check(service, feed, "a-again")
    assert first.items[0].result and second.items[0].result and third.items[0].result
    paper_id = first.items[0].result.paper_id
    assert paper_id == second.items[0].result.paper_id == third.items[0].result.paper_id
    assert papers.show(paper_id).doi == "10.1/a"
    assert papers.show(paper_id).fields["title"].value == "B"
    conflict = run_check(service, feed, "conflict")
    assert conflict.items[0].result and conflict.items[0].result.conflict_id
    assert conflict.items[1].result and conflict.items[1].result.status == "retained"
    assert papers.conflicts(feed_id=feed.feed_id)[0].conflict == "entry_doi_changed"
    service.validate_all()


def test_concurrent_same_request_has_one_check_and_stable_discovery(
    tmp_path: Path,
) -> None:
    from concurrent.futures import ThreadPoolExecutor

    papers, feed, service = feed_service(
        tmp_path, lambda request: httpx.Response(200, content=FEED)
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        values = list(pool.map(lambda _: run_check(service, feed), range(2)))
    assert values[0] == values[1]
    assert len(service.view(feed.feed_id).checks) == 1
    assert values[0].items[0].result
    assert len(papers.trace(values[0].items[0].result.paper_id).discoveries) == 1


def test_nonempty_previous_revision_upgrade_preserves_paper_and_language_schema(
    tmp_path: Path,
) -> None:
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine

    from paper_radar.storage import database as database_module
    from paper_radar.storage.database import upgrade_database
    from tests.feed_support import item

    papers = facts(tmp_path)
    feed = papers.register_feed(URL)
    receipt = papers.submit(item(feed.feed_id))
    assert receipt.paper_id
    expected = papers.trace(receipt.paper_id)
    config = Config()
    config.set_main_option(
        "script_location", str(Path(database_module.__file__).parent / "migrations")
    )
    engine = create_engine(f"sqlite:///{papers.database}")
    try:
        with engine.connect() as connection:
            config.attributes["connection"] = connection
            command.downgrade(config, "feed02_title_language")
            connection.commit()
    finally:
        engine.dispose()
    upgrade_database(papers.database)
    assert papers.trace(receipt.paper_id) == expected
    assert papers.submit(item(feed.feed_id)) == receipt
    assert JGRFeed(papers.database, papers.data_root).view(feed.feed_id).checks == ()


def test_damaged_check_references_are_controlled_and_backup_rejected(
    tmp_path: Path,
) -> None:
    from paper_radar.backup.manifest import BackupError

    papers, feed, service = feed_service(
        tmp_path, lambda request: httpx.Response(200, content=FEED)
    )
    check = run_check(service, feed)
    with closing(sqlite3.connect(papers.database)) as connection:
        connection.execute(
            "UPDATE feed_production_checks SET settlement_sha256=?", ("0" * 64,)
        )
        connection.commit()
    with pytest.raises(PaperError, match="corrupt_reference"):
        service.replay(check.check_id)
    with pytest.raises(BackupError) as error:
        create_backup(papers.database, papers.data_root, tmp_path / "backups")
    assert error.value.reason == "registration_invalid"


@pytest.mark.parametrize(
    "body,item_bytes",
    [
        (
            (
                b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>atom-id'
                b"</id><title>Atom</title><summary/></entry></feed>"
            ),
            b"<entry><id>atom-id</id><title>Atom</title><summary/></entry>",
        ),
        (
            (
                b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-'
                b'ns#" xmlns="http://purl.org/rss/1.0/"><channel><rdf:Seq><rdf'
                b':li rdf:resource="rdf-id"/></rdf:Seq></channel><item rdf:abo'
                b'ut="rdf-id"><title>RDF</title><description/></item></rdf:RDF'
                b">"
            ),
            b'<item rdf:about="rdf-id"><title>RDF</title><description/></item>',
        ),
    ],
)
def test_atom_and_rdf_preserve_original_item_namespace_bytes(
    tmp_path: Path, body: bytes, item_bytes: bytes
) -> None:
    _papers, feed, service = feed_service(
        tmp_path, lambda request: httpx.Response(200, content=body)
    )
    check = run_check(service, feed)
    assert check.complete and check.items[0].result
    assert check.items[0].result.status == "retained"
    assert service.item_bytes(check.check_id, 1) == item_bytes


def test_conditional_304_inherits_original_content_decoding(tmp_path: Path) -> None:
    requests = []
    body = (
        b"<rss><channel><item><guid>entry-1</guid><title>Caf\xe9</title><"
        b"/item></channel></rss>"
    )

    def respond(request):
        requests.append(request)
        return (
            httpx.Response(
                200,
                content=body,
                headers={
                    "Content-Type": "application/rss+xml; charset=iso-8859-1",
                    "ETag": '"v1"',
                },
            )
            if len(requests) == 1
            else httpx.Response(304)
        )

    papers, feed, service = feed_service(tmp_path, respond)
    first = run_check(service, feed, "first")
    second = run_check(service, feed, "second")
    assert first.items[0].result
    assert papers.show(first.items[0].result.paper_id).fields["title"].value == "Café"
    assert second.complete
    assert second.content_decoding == first.content_decoding
    assert (
        service.item_bytes(second.check_id, 1)
        == b"<item><guid>entry-1</guid><title>Caf\xe9</title></item>"
    )
