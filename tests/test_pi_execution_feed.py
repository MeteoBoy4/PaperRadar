"""真实本机合成RPC→Feed生产value登记→隔离恢复。"""

from pathlib import Path

import httpx
import pytest

from paper_radar.backup import create_backup
from paper_radar.backup.restore import restore_backup
from paper_radar.feed_pipeline import FeedPipeline
from paper_radar.fixture_audit.source_http import SourceHTTPExecutor
from paper_radar.pi_execution import ExecutionError
from paper_radar.pi_execution.admission import load_admission_evidence
from paper_radar.pi_execution.service import PiExecution
from paper_radar.screening_tasks import SuccessReceipt
from paper_radar.sources.feeds import endpoint
from tests.pi_execution_service_support import allow_synthetic, service_inputs
from tests.test_feed_pipeline import DOI, FULL


def test_local_execution_composes_feed_value_and_restore_still_needs_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "original"
    root.mkdir()
    service, initial, credentials = service_inputs(root, monkeypatch)

    def respond(request: httpx.Request) -> httpx.Response:
        if "showFeed" in str(request.url):
            return httpx.Response(
                200,
                text=(
                    f"<rss><channel><item><guid>entry</guid><doi>{DOI}</doi>"
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

    pipeline = FeedPipeline(
        service.tasks.database,
        service.data_root,
        http=SourceHTTPExecutor(transport=httpx.MockTransport(respond)),
    )
    feed = pipeline.papers.register_feed(endpoint("jgr"))
    (item,) = pipeline.prepare(
        feed.feed_id, request_id="feed", contact_email="contact@example.org"
    ).items
    assert item.paper_id and item.metadata_request_key
    request = dict(
        paper_id=item.paper_id,
        snapshot_id=initial.snapshot_id,
        source="scheduled",
        scheduled_day="2026-01-01",
    )
    boundary = service.tasks.register({**request, "stage": "boundary"})
    allow_synthetic(monkeypatch)
    result = service.run_attempt(boundary.receipt_id)
    assert isinstance(result, SuccessReceipt) and result.executor_kind == "pi_rpc"
    registered = pipeline.register_value(
        {**request, "stage": "value"},
        metadata_request_key=item.metadata_request_key,
        boundary_success_id=result.success_id,
    )
    assert registered.purpose == "production"
    assert registered.language_basis["original_title_is_zh"] is False
    value = service.run_attempt(registered.receipt.receipt_id)
    assert isinstance(value, SuccessReceipt) and value.stage == "value"
    pipeline.validate_all()
    batch = create_backup(
        service.tasks.database, service.data_root, tmp_path / "backups"
    )
    root.rename(tmp_path / "unavailable")
    restored = restore_backup(batch.batch_dir, tmp_path / "restored")
    database = restored.target_dir / "database.sqlite3"
    recovered = FeedPipeline(database, restored.target_dir)
    assert (
        recovered.register_value(
            {**request, "stage": "value"},
            metadata_request_key=item.metadata_request_key,
            boundary_success_id=result.success_id,
        )
        == registered
    )
    assert (
        recovered.tasks.load_success(value.success_id).receipt.executor_kind == "pi_rpc"
    )
    recovered.validate_all()
    resumed = PiExecution(
        database,
        restored.target_dir,
        roots=service.roots,
        credentials_dir=credentials,
        auth_mode="chatgpt_subscription",
    )
    pending = resumed.tasks.register(
        {
            **request,
            "paper_id": initial.paper_id,
            "stage": "boundary",
            "scheduled_day": "2026-01-02",
        }
    )
    allow_synthetic(monkeypatch, load_admission_evidence)
    with pytest.raises(ExecutionError, match="evidence_missing"):
        resumed.run_attempt(pending.receipt_id)
    assert resumed.tasks.status(pending.receipt_id).used_attempts == 0
