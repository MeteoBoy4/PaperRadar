"""#155 审查回归:外部 parser 拒绝仍须结算真实领取。"""

from pathlib import Path

from paper_radar.body import BodyService
from paper_radar.body.models import ParserResult
from paper_radar.config.extraction import ExtractionSemantics
from paper_radar.fulltext.models import FulltextError
from tests.body_support import Parser, prepared
from tests.test_fulltext_artifacts import document


def test_parser_fulltext_rejection_settles_permanent_failure_before_result(
    tmp_path: Path,
) -> None:
    saved, service, _ = prepared(tmp_path)

    class Refused(Parser):
        def convert(self, pdf: bytes, semantics: ExtractionSemantics) -> ParserResult:
            self.calls += 1
            raise FulltextError("conversion_incomplete")

    parser = Refused()
    view = service.extract(saved.paper_id, snapshot_id=saved.snapshot_id, parser=parser)
    assert view.attempts[-1].failure == "extraction_failed_quality_gate"
    assert view.attempts[-1].settled_at is not None
    assert view.attempts[-1].peak_memory_bytes == 0
    assert view.attempts[-1].elapsed_seconds is not None
    assert view.attempts[-1].elapsed_seconds >= 0
    assert view.permanent_failure and view.remaining_attempts == 1
    assert view.artifact_id is None and view.quality.basis == "absent"
    restarted = BodyService(saved.database, saved.data_root)
    assert (
        restarted.extract(saved.paper_id, snapshot_id=saved.snapshot_id, parser=parser)
        == view
    )
    assert parser.calls == 1
    restarted.validate_all()


def test_publish_rejection_retains_returned_peak_and_spent_attempt(
    tmp_path: Path,
) -> None:
    saved, service, _ = prepared(tmp_path)

    class Partial(Parser):
        def convert(self, pdf: bytes, semantics: ExtractionSemantics) -> ParserResult:
            self.calls += 1
            return ParserResult(
                document().model_copy(update={"conversion_status": "partial"}),
                peak_memory_bytes=4096,
            )

    view = service.extract(
        saved.paper_id, snapshot_id=saved.snapshot_id, parser=Partial()
    )
    assert view.attempts[-1].failure == "extraction_failed_quality_gate"
    assert view.attempts[-1].peak_memory_bytes == 4096
    assert view.attempts[-1].settled_at is not None
    assert view.remaining_attempts == 1 and view.permanent_failure
    assert view.artifact_id is None and view.quality.basis == "absent"
    service.validate_all()
