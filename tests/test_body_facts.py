"""Body D1: 持久前置事实的公共服务,不扩 A1-A10 分母。"""

from pathlib import Path

import pytest

from paper_radar.body import BodyError, BodyService
from paper_radar.eligibility import RootPurpose
from tests.a7_registration_support import archive

PDF = b"%PDF-1.7\n" + b"0" * 1024 + b"\n%%EOF\n"


def test_root_is_immutable_and_pdf_selection_survives_restart(tmp_path: Path) -> None:
    saved = archive(tmp_path)
    service = BodyService(saved.database, saved.data_root)
    assert service.root().purpose is RootPurpose.UNKNOWN
    root = service.register_root("experiment")
    assert service.register_root("experiment") == root
    with pytest.raises(BodyError) as conflict:
        service.register_root("production")
    assert conflict.value.reason == "root_conflict"
    first = service.attach_pdf(saved.paper_id, PDF, request_id="first")
    second = service.attach_pdf(saved.paper_id, PDF + b"different", request_id="second")
    again = BodyService(saved.database, saved.data_root)
    assert again.root() == root
    assert again.pdfs(saved.paper_id) == (first, second)
    assert again.current_pdf(saved.paper_id) == second
    assert first.version_id == saved.version_id
    assert first.access_basis == "manual"
    assert again.attach_pdf(saved.paper_id, PDF, request_id="first") == first


def test_manual_decision_uses_referenced_success_and_exposes_read_rejections(
    tmp_path: Path,
) -> None:
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
    from tests.body_support import prepared

    saved, service, parser = prepared(tmp_path)
    result = service.extract(
        saved.paper_id, snapshot_id=saved.snapshot_id, parser=parser
    )
    assert result.identity
    before = service.facts(saved.paper_id, identity=result.identity)
    assert "decision_not_accepted" in before.reasons
    assert "execution_source_unknown" in before.reasons
    assert "sample_mismatch" in before.reasons
    from datetime import UTC, datetime

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
    decision = service.decide(
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
    after = service.facts(saved.paper_id, identity=result.identity)
    assert after.decision == decision
    assert after.execution_source == "test"
    assert "test_execution_source" in after.reasons
    assert "decision_not_accepted" not in after.reasons
    assert after.decision.fact.applicability == "current"


@pytest.mark.parametrize(
    "source,result,reason",
    [
        ("blind_calibration", "accepted", "user_judgment"),
        ("regular_review", "accepted", "user_judgment"),
        ("metadata_abandonment", "denied", "insufficient_metadata"),
        ("manual_read_request", "accepted", "manual_read_request"),
    ],
)
def test_dedicated_decision_sources_do_not_create_manual_read_requests(
    tmp_path: Path, source: str, result: str, reason: str
) -> None:
    from paper_radar.screening.reasons import (
        DecisionReason,
        ScreeningReasonInput,
        ScreeningResult,
        ScreeningSource,
    )

    saved = archive(tmp_path)
    service = BodyService(saved.database, saved.data_root)
    with pytest.raises(BodyError) as error:
        service.decide(
            saved.paper_id,
            ScreeningReasonInput(
                result=ScreeningResult(result),
                source=ScreeningSource(source),
                reason=DecisionReason(reason),
            ),
            request_id="wrong",
            actor="human",
        )
    assert error.value.reason == "source_requires_dedicated_path"
    assert "专用流程" in str(error.value)
    assert service.decisions(saved.paper_id) == ()


def test_pure_manual_accepted_preserves_unknown_upstream_and_stale_effect(
    tmp_path: Path,
) -> None:
    from paper_radar.papers import PaperFacts
    from paper_radar.screening.reasons import (
        DecisionReason,
        ScreeningReasonInput,
        ScreeningResult,
        ScreeningSource,
    )

    saved = archive(tmp_path)
    service = BodyService(saved.database, saved.data_root)
    event = service.decide(
        saved.paper_id,
        ScreeningReasonInput(
            result=ScreeningResult("accepted"),
            source=ScreeningSource("direct_manual_decision"),
            reason=DecisionReason("user_judgment"),
        ),
        request_id="manual",
        actor="human",
    )
    assert event.screening_references == ()
    PaperFacts(saved.database, saved.data_root).correct(
        {
            "version_id": saved.version_id,
            "request_id": "correction",
            "actor": "human",
            "reason": "revise title",
            "fields": {"title": {"value": "Revised title", "locator": "manual.title"}},
        }
    )
    facts = service.facts(saved.paper_id)
    assert facts.decision and facts.decision.fact.reference == event.fact.reference
    assert facts.decision.fact.applicability == "historical"
    assert facts.execution_source == "unknown"
    assert "execution_source_unknown" in facts.reasons
    assert "decision_not_accepted" not in facts.reasons
    service.validate_all()


def test_frozen_sample_keeps_history_and_rejects_changed_pdf(tmp_path: Path) -> None:
    from tests.body_support import add_feed, prepared

    saved, service, _ = prepared(tmp_path)
    feed = add_feed(saved)
    original = service.current_pdf(saved.paper_id)
    assert original
    first = service.freeze_sample(
        saved.paper_id,
        feed_id=feed,
        pdf_sha256=original.pdf_sha256,
        reason="first sample",
        request_id="one",
    )
    assert (
        service.freeze_sample(
            saved.paper_id,
            feed_id=feed,
            pdf_sha256=original.pdf_sha256,
            reason="first sample",
            request_id="one",
        )
        == first
    )
    changed = service.attach_pdf(saved.paper_id, PDF + b"new", request_id="new")
    assert "sample_mismatch" in service.facts(saved.paper_id).reasons
    second = service.freeze_sample(
        saved.paper_id,
        feed_id=feed,
        pdf_sha256=changed.pdf_sha256,
        reason="replacement",
        request_id="two",
    )
    assert service.samples(saved.paper_id) == (first, second)
    assert second.sequence == first.sequence + 1
    assert "sample_mismatch" not in service.facts(saved.paper_id).reasons
    service.validate_all()


def test_conflicting_concurrent_decision_request_keeps_first_committer(
    tmp_path: Path,
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from paper_radar.screening.reasons import (
        DecisionReason,
        ScreeningReasonInput,
        ScreeningResult,
        ScreeningSource,
    )

    saved = archive(tmp_path)
    service = BodyService(saved.database, saved.data_root)
    start = Barrier(2)

    from paper_radar.body.models import DecisionEvent

    def write(actor: str) -> DecisionEvent | str:
        start.wait(timeout=10)
        try:
            return service.decide(
                saved.paper_id,
                ScreeningReasonInput(
                    result=ScreeningResult("accepted"),
                    source=ScreeningSource("direct_manual_decision"),
                    reason=DecisionReason("user_judgment"),
                ),
                request_id="one-request",
                actor=actor,
            )
        except BodyError as error:
            return error.reason

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(write, ["first", "second"]))
    assert sum(result == "request_conflict" for result in results) == 1
    assert len(service.decisions(saved.paper_id)) == 1
    assert service.decisions(saved.paper_id)[0].fact.sequence == 1


@pytest.mark.parametrize("pdf", [b"%PDF-short", b"NotPDF" + b"x" * 2048])
def test_invalid_pdf_does_not_append_selection(tmp_path: Path, pdf: bytes) -> None:
    saved = archive(tmp_path)
    service = BodyService(saved.database, saved.data_root)
    with pytest.raises(BodyError) as error:
        service.attach_pdf(saved.paper_id, pdf, request_id="bad")
    assert error.value.reason == "invalid_pdf"
    assert service.pdfs(saved.paper_id) == ()


def test_production_upstream_allows_only_matching_experiment_sample_and_test_wins(
    tmp_path: Path,
) -> None:
    from dataclasses import replace

    from paper_radar.config import compile_config
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
    from tests.a8_call_support import request_for
    from tests.body_support import CHECKS, Parser, add_feed
    from tests.config_extraction_support import EXTRACTION_YAML
    from tests.config_projection_support import new_yaml_version
    from tests.pi_rpc_source_support import NOW, candidate, source_archive

    data, supplied = source_archive(tmp_path)
    extraction_dir = data.settings.parent / "extraction"
    extraction_dir.mkdir()
    (extraction_dir / "extraction-v1.yaml").write_text(EXTRACTION_YAML)
    data.settings.write_text(data.settings.read_text() + "extraction: extraction-v1\n")
    data = replace(
        data, snapshot_id=compile_config(data.settings, data.database).snapshot_id
    )
    service = BodyService(data.database, data.data_root)
    service.register_root("experiment")
    pdf = service.attach_pdf(data.paper_id, PDF, request_id="pdf")
    feed = add_feed(data)
    service.freeze_sample(
        data.paper_id,
        feed_id=feed,
        pdf_sha256=pdf.pdf_sha256,
        reason="selected",
        request_id="sample",
    )
    tasks = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    receipt = tasks.register(request_for(data))
    success = tasks.run_once(receipt.receipt_id, lambda *_: candidate(data, supplied))
    assert isinstance(success, SuccessReceipt)
    record = ScreeningReasonInput(
        result=ScreeningResult("accepted"),
        source=ScreeningSource("direct_manual_decision"),
        reason=DecisionReason("user_judgment"),
    )
    service.decide(
        data.paper_id,
        record,
        request_id="accept",
        actor="human",
        screening_references=(success.success_id,),
    )
    result = service.extract(
        data.paper_id, snapshot_id=data.snapshot_id, parser=Parser()
    )
    assert result.identity
    service.review_layout(
        result.identity,
        passed=True,
        checks=CHECKS,
        note="checked",
        actor="human",
        request_id="review",
    )
    assert service.facts(data.paper_id, identity=result.identity).eligible
    assert (
        service.facts(data.paper_id, identity=result.identity).execution_source
        == "production"
    )
    assert service.facts(
        data.paper_id, identity=result.identity, ordinary=True
    ).reasons == ("ordinary_consumption_denied",)
    # 旧 Screening 依据保留效力;新的 test 成功只有被决定事件引用才改变来源。
    new_yaml_version(data.settings, "profile", lambda c: c.update(background="changed"))
    other = compile_config(data.settings, data.database)
    second = tasks.register(
        request_for(data, snapshot_id=other.snapshot_id, scheduled_day="2026-01-02")
    )
    test_success = tasks.run_once(
        second.receipt_id,
        lambda *_: SuccessCandidate(
            b'{"boundary":"in_scope","reason_zh":"Synthetic study."}'
        ),
    )
    assert isinstance(test_success, SuccessReceipt)
    assert (
        service.facts(data.paper_id, identity=result.identity).execution_source
        == "production"
    )
    service.decide(
        data.paper_id,
        record,
        request_id="mixed",
        actor="human",
        screening_references=(success.success_id, test_success.success_id),
    )
    facts = service.facts(data.paper_id, identity=result.identity)
    assert facts.execution_source == "test" and "test_execution_source" in facts.reasons
    assert len(service.decisions(data.paper_id)) == 2
    service.validate_all()


def test_read_consumer_uses_the_supplied_transaction_for_body_facts(
    tmp_path: Path,
) -> None:
    from sqlalchemy import Engine, event

    from paper_radar.storage.database import DatabaseMode, open_database
    from tests.body_support import prepared

    saved, service, parser = prepared(tmp_path)
    extracted = service.extract(
        saved.paper_id, snapshot_id=saved.snapshot_id, parser=parser
    )
    assert extracted.identity
    engine = open_database(saved.database, mode=DatabaseMode.READ_WRITE)
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            connection.exec_driver_sql("DELETE FROM body_pdfs")

            def deny_other_connection(*_: object) -> None:
                raise AssertionError("body facts opened another database view")

            event.listen(Engine, "connect", deny_other_connection)
            try:
                facts = service.facts_in_connection(
                    connection, saved.paper_id, identity=extracted.identity
                )
            finally:
                event.remove(Engine, "connect", deny_other_connection)
            assert facts.pdf is None
            assert "pdf_absent" in facts.reasons and "facts_changed" in facts.reasons
            connection.rollback()
        assert service.current_pdf(saved.paper_id) is not None
    finally:
        engine.dispose()
