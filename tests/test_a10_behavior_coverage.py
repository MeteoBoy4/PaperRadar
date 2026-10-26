"""A10 需求补验:生产事实隔离、非类型线索与真实日期披露。"""

import sqlite3
from contextlib import closing
from pathlib import Path

import httpx
import pytest
from sqlalchemy import Engine, event

from paper_radar.config import load_config_snapshot, project_config
from paper_radar.papers import PaperFacts
from paper_radar.screening_tasks import ScreeningTasks
from tests.a7_registration_support import archive, request_for
from tests.a10_recovery_support import audit_service
from tests.audit_matrix_support import MatrixSources
from tests.audit_sampling_support import CODE, SamplingSources, sampling_service
from tests.feed_support import item
from tests.test_audit_reinterpret import SyntheticV2
from tests.test_paper_mapping import screening_fields

AIES_FEED = (
    "https://journals.ametsoc.org/journalissuetocrss/journals/aies/aies-overview.xml"
)
JGR_FEED = "https://agupubs.onlinelibrary.wiley.com/action/showFeed?jc=21698996&type=etoc&feed=rss"


def production_state(database: Path) -> dict[str, tuple[tuple[object, ...], ...]]:
    """SQLite 持久化边界;允许 A10/制品事实,独立比较其余实际表。"""
    with closing(sqlite3.connect(database)) as connection:
        tables = [
            name
            for (name,) in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            if not name.startswith(("audit_", "fixture_", "sqlite_"))
            and name not in {"content_objects", "artifacts", "artifact_members"}
        ]
        return {
            table: tuple(
                connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid').fetchall()
            )
            for table in tables
        }


def test_audit_operations_leave_existing_production_facts_untouched(
    tmp_path: Path,
) -> None:
    data = archive(tmp_path)
    papers = PaperFacts(data.database, data.data_root)
    feed = papers.register_feed(JGR_FEED)
    discovered = papers.submit(
        item(feed.feed_id, doi="10.1029/jgr.synthetic", fields=screening_fields())
    )
    assert discovered.paper_id is not None
    receipt = ScreeningTasks(data.database, data.data_root).register(
        request_for(data, paper_id=discovered.paper_id)
    )
    before = production_state(data.database)
    assert all(
        before[table]
        for table in (
            "papers",
            "paper_versions",
            "feeds",
            "feed_discoveries",
            "screening_requests",
            "screening_inputs",
            "runtime_config_snapshots",
        )
    )
    # No calibration batch/member/evaluation storage is delivered yet. Its actual
    # existing configuration and reconstructable semantic baseline are protected.
    baseline = project_config(
        load_config_snapshot(data.database, data.snapshot_id)
    ).baseline
    writes: list[tuple[int, str]] = []
    observed_writes: list[tuple[int, str]] = []
    protected = set(before)

    def authorize(
        action: int,
        table: str | None,
        _column: str | None,
        _database: str | None,
        _source: str | None,
    ) -> int:
        if (
            action
            in {
                sqlite3.SQLITE_INSERT,
                sqlite3.SQLITE_UPDATE,
                sqlite3.SQLITE_DELETE,
                sqlite3.SQLITE_DROP_TABLE,
                sqlite3.SQLITE_CREATE_TABLE,
            }
            and table is not None
        ):
            observed_writes.append((action, table))
            if table in protected:
                writes.append((action, table))
        return sqlite3.SQLITE_OK

    def observe(connection: object, _record: object) -> None:
        if isinstance(connection, sqlite3.Connection):
            connection.set_authorizer(authorize)

    class RecoveringSources(MatrixSources):
        recovered = False

        def __call__(self, request: httpx.Request) -> httpx.Response:
            if (
                request.url.host == "agupubs.onlinelibrary.wiley.com"
                and "/doi/" in request.url.path
                and not self.recovered
            ):
                self.calls.append(str(request.url))
                return httpx.Response(503)
            return super().__call__(request)

    sources = RecoveringSources()
    service = audit_service(data.database, data.data_root, sources)

    def unchanged() -> None:
        assert any(table.startswith("audit_") for _, table in observed_writes)
        assert writes == []
        assert production_state(data.database) == before
        assert (
            project_config(
                load_config_snapshot(data.database, data.snapshot_id)
            ).baseline
            == baseline
        )
        assert (
            ScreeningTasks(data.database, data.data_root).get_receipt(
                receipt.receipt_id
            )
            == receipt
        )

    event.listen(Engine, "connect", observe)
    try:
        original = service.run_audit(
            contact_email="audit@example.org", code_identity=CODE
        )
        unchanged()
        sources.recovered = True
        resumed = service.resume_audit(
            original.plan.plan_id, contact_email="audit@example.org", code_identity=CODE
        )
        assert len(resumed.matrix_history) > len(original.matrix_history)
        unchanged()
        interpreted = service.reinterpret_audit(
            original.plan.plan_id,
            parser=SyntheticV2(),
            request_key="production-isolation-v2",
        )
        assert interpreted.parser_version == "synthetic-abstract-v2"
        assert interpreted.rows
        unchanged()
    finally:
        event.remove(Engine, "connect", observe)
    service.validate_all()


class NonTypeHints(SamplingSources):
    def __init__(self, hint: str, doi: str) -> None:
        super().__init__()
        self.hint, self.doi = hint, doi
        link = (
            "https://journals.ametsoc.org/view/journals/aies/journal-article/1/synthetic.xml"
            if hint == "url_path"
            else "https://journals.ametsoc.org/view/journals/aies/5/1/journal-article.xml"
            if hint == "file_name"
            else "https://journals.ametsoc.org/view/journals/aies/5/1/synthetic.xml"
        )
        guid = f"<guid>{doi}</guid>" if hint in {"doi_prefix", "feed_position"} else ""
        title = (
            "Journal Article: Research Article"
            if hint == "title"
            else "Synthetic title"
        )
        prism = (
            "<prism:url>https://journals.ametsoc.org/view/journals/aies/5/1/research-article.xml</prism:url>"
            if hint == "prism_url"
            else ""
        )
        self.feeds[AIES_FEED] = (
            '<rss xmlns:prism="http://prismstandard.org/namespaces/basic/2.0/">'
            f"<channel><item>{guid}<title>{title}</title><link>{link}</link>{prism}</item></channel></rss>"
        ).encode()

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/works/" + self.doi:
            self.calls.append(str(request.url))
            return httpx.Response(200, json={"message": {"DOI": self.doi}})
        if request.url.host == "journals.ametsoc.org" and request.url.path.startswith(
            "/view/"
        ):
            self.calls.append(str(request.url))
            og_type = (
                '<meta property="og:type" content="article">'
                if self.hint == "og_type"
                else ""
            )
            return httpx.Response(
                200,
                text=(
                    f'<html><meta name="citation_doi" content="{self.doi}">'
                    + og_type
                    + "</html>"
                ),
            )
        return super().__call__(request)


@pytest.mark.parametrize(
    "hint,doi",
    [
        ("feed_position", "10.9999/synthetic-neutral"),
        ("doi_prefix", "10.1175/aies.synthetic"),
        ("url_path", "10.1175/aies.synthetic"),
        ("file_name", "10.1175/aies.synthetic"),
        ("prism_url", "10.1175/aies.synthetic"),
        ("title", "10.1175/aies.synthetic"),
        ("og_type", "10.1175/aies.synthetic"),
        ("citation_doi", "10.1175/aies.synthetic"),
    ],
)
def test_non_type_hints_do_not_create_category_evidence(
    tmp_path: Path, hint: str, doi: str
) -> None:
    sources = NonTypeHints(hint, doi)
    service = sampling_service(tmp_path, sources)
    plan = service.create_audit_plan(
        contact_email="audit@example.org", code_identity=CODE
    )
    view = service.select_audit_samples(
        plan.plan_id, contact_email="audit@example.org", code_identity=CODE
    )
    aies = view.sampling[0]
    assert aies.status == "complete" and aies.members == ()
    assert aies.shortfall == 5
    outcome = aies.entries[0]
    assert outcome.position == 1 and outcome.doi == doi
    assert outcome.result == "excluded_deterministic"
    assert outcome.reason == "category_unknown" and outcome.category_bases == ()
    assert any(
        route.route == "registry_crossref" and route.reason == "acquired"
        for route in outcome.routes
    )
    if hint not in {"feed_position", "doi_prefix"}:
        assert any(
            route.route == "publisher" and route.reason == "acquired"
            for route in outcome.routes
        )
    service.validate_all()


def test_journal_summaries_report_literal_date_spans_and_unknown_counts(
    tmp_path: Path,
) -> None:
    class DateSources(MatrixSources):
        def __call__(self, request: httpx.Request) -> httpx.Response:
            if request.url.path == "/works/10.1029/excluded.synthetic":
                self.calls.append(str(request.url))
                return httpx.Response(
                    200,
                    json={
                        "message": {
                            "DOI": "10.1029/excluded.synthetic",
                            "type": "peer-review",
                        }
                    },
                )
            return super().__call__(request)

    sources = DateSources()
    sources.feeds[AIES_FEED] = (
        b"<rss><channel><item><title>No date</title>"
        b"<link>https://journals.ametsoc.org/view/journals/aies/5/1/synthetic.xml</link>"
        b"</item></channel></rss>"
    )
    sources.feeds[JGR_FEED] = (
        b"<rss><channel>"
        b"<item><guid>10.1029/late.synthetic</guid><pubDate>2026-09-30</pubDate></item>"
        b"<item><guid>10.1029/early.synthetic</guid><pubDate>2025-12-02</pubDate></item>"
        b"<item><guid>10.1029/unknown.synthetic</guid></item>"
        b"<item><guid>10.1029/excluded.synthetic</guid><pubDate>1990-01-01</pubDate></item>"
        b"</channel></rss>"
    )
    service = sampling_service(tmp_path, sources)
    view = service.run_audit(contact_email="audit@example.org", code_identity=CODE)
    assert [
        (value.journal, value.date_start, value.date_end, value.unknown_dates)
        for value in view.journal_summaries
    ] == [
        ("aies", None, None, 1),
        ("jgr", "2025-12-02", "2026-09-30", 1),
        ("qjrms", "2026-10-24T12:00:00+00:00", "2026-10-24T12:00:00+00:00", 0),
        ("dqkx", "2026-10-23", "2026-10-23", 0),
    ]
    assert (
        view.journal_summaries[1].considered,
        view.journal_summaries[1].selected,
    ) == (4, 3)
    assert [member.doi for member in view.sampling[1].members] == [
        "10.1029/late.synthetic",
        "10.1029/early.synthetic",
        "10.1029/unknown.synthetic",
    ]
    service.validate_all()
