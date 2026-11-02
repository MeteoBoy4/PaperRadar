"""Issue #146:生产 Feed/最低元数据版本与原历史共存。"""

from pathlib import Path

import httpx

from paper_radar.feed_ingestion import JGRFeed
from paper_radar.feed_metadata import JGRMetadata
from paper_radar.fixture_audit.source_http import SourceHTTPExecutor
from paper_radar.papers.models import AbstractValue
from paper_radar.sources.feeds import endpoint
from tests.feed_support import facts
from tests.test_wiley_abstract_v2 import MAIN, NOTE, feed


def test_feed_upgrade_and_metadata_use_versioned_main_without_rewriting_history(
    tmp_path: Path,
) -> None:
    raw = feed(
        "<dc:identifier>10.1029/synthetic</dc:identifier>"
        f"<description>{NOTE}</description>"
        "<content:encoded><![CDATA[<h2>Abstract</h2>"
        f"<p>{MAIN}</p>]]></content:encoded>"
    )
    original_root = tmp_path / "original"
    original_root.mkdir()
    papers = facts(original_root)
    source = papers.register_feed(endpoint("jgr"))
    assert papers.data_root
    service = JGRFeed(
        papers.database,
        papers.data_root,
        http=SourceHTTPExecutor(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, content=raw)
            )
        ),
    )
    old = service.check(
        source.feed_id, request_id="old", contact_email="audit@example.org"
    )
    assert old.items[0].result and old.items[0].result.paper_id
    paper_id = old.items[0].result.paper_id
    before = papers.show(paper_id)
    old_value = before.fields["abstract"].value
    assert isinstance(old_value, AbstractValue) and old_value.text == NOTE
    new = service.check(
        source.feed_id,
        request_id="new",
        contact_email="audit@example.org",
        parser_version=2,
    )
    assert new.parser_version == 2 and new.parser_identity == "jgr-feed-parser-v2"
    value = papers.show(paper_id).fields["abstract"].value
    assert isinstance(value, AbstractValue)
    assert value.text == MAIN and value.rule == "audit-abstract-v2/audit-truncation-v1"
    assert service.replay(old.check_id) == old
    assert (
        papers.revision(before.version_id, before.revision_no).fields == before.fields
    )

    def respond(request: httpx.Request) -> httpx.Response:
        if "doiRA" in str(request.url):
            return httpx.Response(
                200, json=[{"DOI": "10.1029/synthetic", "RA": "Crossref"}]
            )
        if request.url.host == "api.crossref.org":
            return httpx.Response(
                200,
                json={
                    "message": {
                        "DOI": "10.1029/synthetic",
                        "type": "journal-article",
                        "title": ["Registry title"],
                        "abstract": MAIN,
                    }
                },
            )
        return httpx.Response(403)

    metadata = JGRMetadata(
        papers.database,
        papers.data_root,
        http=SourceHTTPExecutor(transport=httpx.MockTransport(respond)),
    )
    result = metadata.enrich(
        paper_id,
        request_id="v2",
        contact_email="audit@example.org",
        abstract_rules_version="audit-abstract-v2",
    )
    assert result.nontruncated_complete
    assert {route.abstract_rules_version for route in result.routes} == {
        "audit-abstract-v2"
    }
    content = metadata.content(result.request_key)
    assert content.abstract == MAIN and content.abstract_source_kind == "registry"
    service.validate_all()
    metadata.validate_all()

    from paper_radar.backup import create_backup
    from paper_radar.backup.restore import restore_backup

    batch = create_backup(papers.database, papers.data_root, tmp_path / "backups")
    original_root.rename(tmp_path / "unavailable")
    restored = restore_backup(batch.batch_dir, tmp_path / "restored")
    copied_feed = JGRFeed(restored.target_dir / "database.sqlite3", restored.target_dir)
    copied_metadata = JGRMetadata(
        restored.target_dir / "database.sqlite3", restored.target_dir
    )
    assert copied_feed.replay(old.check_id) == old
    assert copied_feed.replay(new.check_id) == new
    assert copied_metadata.replay(result.request_key) == result
    assert copied_metadata.content(result.request_key) == content


def test_v2_checkpoint_resume_keeps_version_and_avoids_old_etag(tmp_path: Path) -> None:
    import pytest

    from paper_radar.papers.errors import PaperError
    from tests.artifact_support import fail_sql

    papers = facts(tmp_path)
    registered = papers.register_feed(endpoint("jgr"))
    assert papers.data_root
    requests: list[httpx.Request] = []
    raw = feed(
        f"<description>{NOTE}</description>"
        f"<dc:description>Abstract: {MAIN}</dc:description>"
    )

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, content=raw, headers={"ETag": '"unchanged"'})

    service = JGRFeed(
        papers.database,
        papers.data_root,
        http=SourceHTTPExecutor(transport=httpx.MockTransport(respond)),
    )
    service.check(
        registered.feed_id, request_id="old", contact_email="audit@example.org"
    )
    with (
        fail_sql("INSERT INTO feed_production_items"),
        pytest.raises(PaperError, match="corrupt_reference"),
    ):
        service.check(
            registered.feed_id,
            request_id="v2",
            contact_email="audit@example.org",
            parser_version=2,
        )
    pending = service.view(registered.feed_id).checks[-1]
    assert not pending.complete and pending.parser_version == 2
    assert "If-None-Match" not in requests[-1].headers
    count = len(requests)
    resumed = service.resume(pending.check_id, contact_email="audit@example.org")
    assert resumed.complete and resumed.parser_version == 2
    assert len(requests) == count
    assert resumed.items[0].result and resumed.items[0].result.paper_id
    value = papers.show(resumed.items[0].result.paper_id).fields["abstract"].value
    assert isinstance(value, AbstractValue) and value.text == MAIN


def test_metadata_replay_rejects_rules_mislabeled_against_acquisition(
    tmp_path: Path,
) -> None:
    import hashlib
    import json
    import sqlite3
    from contextlib import closing

    import pytest

    from paper_radar.papers.errors import PaperError
    from tests.test_feed_metadata import enrich, setup_metadata
    from tests.test_feed_metadata_recovery import response

    papers, paper_id, metadata = setup_metadata(tmp_path, response)
    result = enrich(metadata, paper_id)
    with closing(sqlite3.connect(papers.database)) as connection:
        basis = json.loads(
            connection.execute(
                "SELECT basis_json FROM feed_metadata_requests"
            ).fetchone()[0]
        )
        basis["abstract_rules_version"] = "audit-abstract-v2"
        payload = json.dumps(
            basis, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        connection.execute(
            "UPDATE feed_metadata_requests SET basis_json=?, basis_sha256=?",
            (payload, hashlib.sha256(payload.encode()).hexdigest()),
        )
        for route, raw in connection.execute(
            "SELECT route,view_json FROM feed_metadata_routes"
        ).fetchall():
            value = json.loads(raw)
            value["abstract_rules_version"] = "audit-abstract-v2"
            changed = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            connection.execute(
                "UPDATE feed_metadata_routes SET view_json=?,view_sha256=? "
                "WHERE route=?",
                (
                    changed,
                    hashlib.sha256((result.request_key + changed).encode()).hexdigest(),
                    route,
                ),
            )
        connection.commit()
    with pytest.raises(PaperError) as corrupt:
        metadata.replay(result.request_key)
    assert corrupt.value.reason == "corrupt_reference"
    assert corrupt.value.path == "metadata"
