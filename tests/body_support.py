"""Body 公共组合合成材料;唯一替身是外部 parser。"""

from pathlib import Path

from paper_radar.body import BodyService
from paper_radar.body.models import ParserResult
from paper_radar.config import compile_config
from paper_radar.config.extraction import ExtractionSemantics
from paper_radar.papers import PaperFacts
from tests.a7_registration_support import Archive
from tests.a8_call_support import Archive as RpcArchive
from tests.config_projection_support import full_inputs
from tests.test_fulltext_artifacts import document
from tests.test_paper_mapping import screening_fields
from tests.test_paper_service import observation

PDF = b"%PDF-1.7\n" + b"0" * 1024 + b"\n%%EOF\n"
CHECKS = {
    "body_boundary": True,
    "reading_order": True,
    "sections": True,
    "headers_footers": True,
    "provenance": True,
    "restricted_content": True,
}


def body_archive(root: Path) -> Archive:
    settings, database = full_inputs(root)
    snapshot = compile_config(settings, database)
    data_root = root / "data"
    saved = PaperFacts(database, data_root).submit(
        observation(fields=screening_fields())
    )
    assert saved.paper_id and saved.version_id
    return Archive(
        settings,
        database,
        data_root,
        snapshot.snapshot_id,
        saved.paper_id,
        saved.version_id,
    )


class Parser:
    def __init__(self) -> None:
        self.calls = 0
        self.preflights = 0

    def preflight(self, semantics: ExtractionSemantics) -> None:
        self.preflights += 1

    def convert(self, pdf: bytes, semantics: ExtractionSemantics) -> ParserResult:
        assert pdf.startswith(b"%PDF-")
        self.calls += 1
        return ParserResult(document(), peak_memory_bytes=4096)


def prepared(root: Path) -> tuple[Archive, BodyService, Parser]:
    saved = body_archive(root)
    service = BodyService(saved.database, saved.data_root)
    service.register_root("experiment")
    service.attach_pdf(saved.paper_id, PDF, request_id="pdf")
    return saved, service, Parser()


def add_feed(saved: Archive | "RpcArchive") -> str:
    from tests.feed_support import item

    papers = PaperFacts(saved.database, saved.data_root)
    feed = papers.register_feed("https://feeds.example/body")
    result = papers.submit(item(feed.feed_id, doi="10.1234/abc"))
    assert result.paper_id == saved.paper_id
    return feed.feed_id


def accepted(saved: Archive, service: BodyService) -> str:
    from datetime import UTC, datetime

    from paper_radar.screening.reasons import (
        DecisionReason,
        ScreeningReasonInput,
        ScreeningResult,
        ScreeningSource,
    )
    from paper_radar.screening_tasks import (
        ScreeningTasks,
        SuccessCandidate,
        SuccessReceipt,
    )
    from tests.a7_registration_support import request_for

    tasks = ScreeningTasks(
        saved.database, saved.data_root, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    receipt = tasks.register(request_for(saved))
    success = tasks.run_once(
        receipt.receipt_id,
        lambda *_: SuccessCandidate(
            b'{"boundary":"in_scope","reason_zh":"Synthetic weather study."}'
        ),
    )
    assert isinstance(success, SuccessReceipt)
    service.decide(
        saved.paper_id,
        ScreeningReasonInput(
            result=ScreeningResult("accepted"),
            source=ScreeningSource("direct_manual_decision"),
            reason=DecisionReason("user_judgment"),
        ),
        request_id="accept",
        actor="researcher",
        screening_references=(success.success_id,),
    )
    return success.success_id
