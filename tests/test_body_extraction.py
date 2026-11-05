"""Body D1:真实制品持久提取预算与质量。"""

from pathlib import Path

import pytest

from paper_radar.body import BodyService
from paper_radar.body.models import ParserResult
from paper_radar.config.extraction import ExtractionSemantics
from paper_radar.fulltext.artifacts import FulltextArtifacts
from tests.body_support import CHECKS, Parser, prepared


def test_extraction_reuses_one_success_and_requires_independent_layout_review(
    tmp_path: Path,
) -> None:
    saved, service, parser = prepared(tmp_path)
    result = service.extract(
        saved.paper_id, snapshot_id=saved.snapshot_id, parser=parser
    )
    assert result.artifact_id and result.identity
    assert result.quality.basis == "absent"
    assert result.remaining_attempts == 1
    assert parser.calls == 1
    loaded = FulltextArtifacts(service.store).load(
        result.artifact_id, expected_identity=result.identity
    )
    assert loaded.context.replay()[1].text == "Exact source α = 2."
    again = BodyService(saved.database, saved.data_root)
    assert (
        again.extract(saved.paper_id, snapshot_id=saved.snapshot_id, parser=parser)
        == result
    )
    assert parser.calls == 1
    reviewed = again.review_layout(
        result.identity,
        passed=True,
        checks=CHECKS,
        note="已核对合成材料",
        actor="researcher",
        request_id="review",
    )
    assert reviewed.quality.basis == "experiment_document_gate"
    assert again.extraction(result.fingerprint) == reviewed


def test_retry_budget_is_shared_across_papers_and_restarts(tmp_path: Path) -> None:
    from paper_radar.body.models import ParserFailure
    from paper_radar.papers import PaperFacts
    from tests.body_support import PDF
    from tests.test_paper_service import observation

    saved, service, parser = prepared(tmp_path)

    class Failing(Parser):
        def convert(self, pdf: bytes, semantics: ExtractionSemantics) -> ParserResult:
            self.calls += 1
            raise ParserFailure("timeout", peak_memory_bytes=512)

    failing = Failing()
    first = service.extract(
        saved.paper_id, snapshot_id=saved.snapshot_id, parser=failing
    )
    assert first.attempts[0].failure == "timeout"
    other = PaperFacts(saved.database, saved.data_root).submit(
        observation(doi="10.1000/other")
    )
    assert other.paper_id
    service.attach_pdf(other.paper_id, PDF, request_id="other")
    restarted = BodyService(saved.database, saved.data_root)
    second = restarted.extract(
        other.paper_id, snapshot_id=saved.snapshot_id, parser=failing
    )
    assert second.fingerprint == first.fingerprint
    assert second.remaining_attempts == 0
    assert [a.ordinal for a in second.attempts] == [1, 2]
    assert (
        restarted.extract(saved.paper_id, snapshot_id=saved.snapshot_id, parser=parser)
        == second
    )
    assert parser.calls == 0
    assert failing.calls == 2


def test_layout_rejection_is_permanent_and_bound_to_exact_content(
    tmp_path: Path,
) -> None:
    from dataclasses import replace

    import pytest

    from paper_radar.body import BodyError

    saved, service, parser = prepared(tmp_path)
    result = service.extract(
        saved.paper_id, snapshot_id=saved.snapshot_id, parser=parser
    )
    assert result.identity
    with pytest.raises(BodyError) as mismatch:
        service.review_layout(
            replace(result.identity, reading_sha256="f" * 64),
            passed=True,
            checks=CHECKS,
            note="yes",
            actor="human",
            request_id="wrong",
        )
    assert mismatch.value.reason == "corrupt_reference"
    checks = {**CHECKS, "reading_order": False}
    failed = service.review_layout(
        result.identity,
        passed=False,
        checks=checks,
        note="顺序不符",
        actor="human",
        request_id="no",
    )
    assert failed.quality.basis == "failed"
    assert failed.quality.failure == "layout_review"
    assert failed.permanent_failure
    with pytest.raises(BodyError) as conflict:
        service.review_layout(
            result.identity,
            passed=True,
            checks=CHECKS,
            note="又通过",
            actor="human",
            request_id="yes",
        )
    assert conflict.value.reason == "layout_conflict"
    assert (
        service.extract(saved.paper_id, snapshot_id=saved.snapshot_id, parser=parser)
        == failed
    )
    assert parser.calls == 1


def test_validate_all_checks_the_actual_pdf_and_persisted_input(tmp_path: Path) -> None:
    saved, service, parser = prepared(tmp_path)
    result = service.extract(
        saved.paper_id, snapshot_id=saved.snapshot_id, parser=parser
    )
    service.validate_all()
    assert result.artifact_id


def test_missing_text_layer_records_exact_permanent_failure(tmp_path: Path) -> None:
    from paper_radar.body.models import ParserResult
    from tests.test_fulltext_artifacts import document

    saved, service, parser = prepared(tmp_path)

    class NoText(Parser):
        def convert(self, pdf: bytes, semantics: ExtractionSemantics) -> ParserResult:
            self.calls += 1
            return ParserResult(document().model_copy(update={"has_text_layer": False}))

    parser = NoText()
    view = service.extract(saved.paper_id, snapshot_id=saved.snapshot_id, parser=parser)
    assert view.attempts[-1].failure == "extraction_failed_no_text_layer"
    assert view.permanent_failure
    assert (
        service.extract(saved.paper_id, snapshot_id=saved.snapshot_id, parser=parser)
        == view
    )
    assert parser.calls == 1


def test_partial_conversion_has_no_assessed_quality_and_is_permanent(
    tmp_path: Path,
) -> None:
    from paper_radar.body.models import ParserResult
    from tests.test_fulltext_artifacts import document

    saved, service, parser = prepared(tmp_path)

    class Partial(Parser):
        def convert(self, pdf: bytes, semantics: ExtractionSemantics) -> ParserResult:
            self.calls += 1
            return ParserResult(
                document().model_copy(update={"conversion_status": "partial"})
            )

    parser = Partial()
    view = service.extract(saved.paper_id, snapshot_id=saved.snapshot_id, parser=parser)
    assert view.attempts[-1].failure == "extraction_failed_quality_gate"
    assert view.quality.basis == "absent" and view.quality.failure is None
    assert view.artifact_id is None
    assert view.permanent_failure
    service.validate_all()


@pytest.mark.parametrize("failure", ["timeout", "resource_exhausted", "executor_error"])
def test_transient_failures_preserve_two_attempt_budget(
    tmp_path: Path, failure: str
) -> None:
    from paper_radar.body.models import ParserFailure

    saved, service, _ = prepared(tmp_path)

    class Failing(Parser):
        def convert(self, pdf: bytes, semantics: ExtractionSemantics) -> ParserResult:
            self.calls += 1
            raise ParserFailure(failure, peak_memory_bytes=1024)

    parser = Failing()
    first = service.extract(
        saved.paper_id, snapshot_id=saved.snapshot_id, parser=parser
    )
    assert not first.permanent_failure and first.quality.basis == "absent"
    second = BodyService(saved.database, saved.data_root).extract(
        saved.paper_id, snapshot_id=saved.snapshot_id, parser=parser
    )
    assert second.remaining_attempts == 0 and parser.calls == 2
    assert second.attempts[-1].peak_memory_bytes == 1024
    assert second.attempts[-1].failure == failure
    service.validate_all()


def test_preflight_failure_never_registers_input_or_attempt(tmp_path: Path) -> None:
    from paper_radar.body.models import ParserFailure
    from paper_radar.config import StageName, load_config_snapshot
    from paper_radar.stage_inputs import ExtractionFacts, build_stage_input

    saved, service, _ = prepared(tmp_path)

    class Refused(Parser):
        def preflight(self, semantics: ExtractionSemantics) -> None:
            raise ParserFailure("executor_error")

    parser = Refused()
    with pytest.raises(ParserFailure) as error:
        service.extract(saved.paper_id, snapshot_id=saved.snapshot_id, parser=parser)
    assert error.value.failure == "executor_error"
    pdf = service.current_pdf(saved.paper_id)
    assert pdf
    stage = build_stage_input(
        load_config_snapshot(saved.database, saved.snapshot_id),
        StageName.EXTRACTION,
        ExtractionFacts(pdf_sha256=pdf.pdf_sha256),
    )
    assert service.extraction(stage.fingerprint) is None and parser.calls == 0


@pytest.mark.parametrize(
    "damage,expected",
    [
        ("generated", "source_generated_separation"),
        ("binary", "embedded_binary"),
        ("encoding", "text_integrity"),
        ("provenance", "evidence_replay"),
    ],
)
def test_automatic_failures_remain_exact_after_restart(
    tmp_path: Path, damage: str, expected: str
) -> None:
    from tests.test_fulltext_artifacts import document

    saved, service, _ = prepared(tmp_path)

    class Invalid(Parser):
        def convert(self, pdf: bytes, semantics: ExtractionSemantics) -> ParserResult:
            doc = document()
            audit = None
            if damage == "generated":
                doc = doc.model_copy(
                    update={
                        "blocks": (
                            doc.blocks[0],
                            doc.blocks[1].model_copy(update={"role": "generated"}),
                        )
                    }
                )
            elif damage == "provenance":
                doc = doc.model_copy(
                    update={
                        "blocks": (
                            doc.blocks[0],
                            doc.blocks[1].model_copy(update={"provenance": ()}),
                        )
                    }
                )
            else:
                audit = (
                    b'{"audit":"data:image/png;base64,AAAA"}'
                    if damage == "binary"
                    else b'{"audit":"\\ufffd"}'
                )
            return ParserResult(doc, document_json=audit)

    view = service.extract(
        saved.paper_id, snapshot_id=saved.snapshot_id, parser=Invalid()
    )
    assert view.quality.basis == "failed" and view.quality.failure == expected
    assert view.permanent_failure
    assert (
        BodyService(saved.database, saved.data_root).extraction(view.fingerprint)
        == view
    )
    service.validate_all()


@pytest.mark.parametrize(
    "basis,failure",
    [
        ("failed", None),
        ("absent", "layout_review"),
        ("unknown", "layout_review"),
        ("experiment_document_gate", "layout_review"),
        ("formal_gate", "layout_review"),
    ],
)
def test_public_extraction_dto_rejects_contradictory_quality(
    tmp_path: Path, basis: str, failure: str | None
) -> None:
    from dataclasses import replace

    from paper_radar.body import BodyError
    from paper_radar.eligibility import QualityBasis, QualityFact, QualityFailure

    saved, service, parser = prepared(tmp_path)
    view = service.extract(saved.paper_id, snapshot_id=saved.snapshot_id, parser=parser)
    with pytest.raises(BodyError) as error:
        replace(
            view,
            quality=QualityFact(
                QualityBasis(basis),
                failure=QualityFailure(failure) if failure else None,
            ),
        )
    assert error.value.reason == "corrupt_reference"


def test_new_backend_fingerprint_has_separate_budget(tmp_path: Path) -> None:
    from paper_radar.config import compile_config
    from tests.config_projection_support import new_yaml_version

    saved, service, parser = prepared(tmp_path)
    original = service.extract(
        saved.paper_id, snapshot_id=saved.snapshot_id, parser=parser
    )
    new_yaml_version(
        saved.settings,
        "extraction",
        lambda c: c.update(pdf_backend="threaded_docling_parse"),
    )
    snapshot = compile_config(saved.settings, saved.database)
    changed = service.extract(
        saved.paper_id, snapshot_id=snapshot.snapshot_id, parser=parser
    )
    assert changed.fingerprint != original.fingerprint
    assert len(changed.attempts) == 1 and parser.calls == 2
    assert service.extraction(original.fingerprint) == original


def test_registered_pdf_identity_is_checked_before_claim_or_parser(
    tmp_path: Path,
) -> None:
    import sqlite3

    from paper_radar.body import BodyError

    saved, service, parser = prepared(tmp_path)
    with sqlite3.connect(saved.database) as connection:
        connection.execute("UPDATE body_pdfs SET pdf_sha256=?", ("f" * 64,))
    with pytest.raises(BodyError) as error:
        service.extract(saved.paper_id, snapshot_id=saved.snapshot_id, parser=parser)
    assert error.value.reason == "corrupt_reference"
    assert parser.calls == 0 and parser.preflights == 0
