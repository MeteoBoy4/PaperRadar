"""D1 完整公共正文/Read消费者组合;不运行真实模型。"""

from pathlib import Path
from typing import Any

import pytest

from paper_radar.read_queries import ReadQueries
from paper_radar.read_tasks import ReadAnalysis, ReadTask
from tests.body_read_closure_support import closure


@pytest.mark.parametrize("mode", ["normal", "degrade"])
def test_pdf_to_pi_analysis_is_visible_only_for_experiment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    service, task, body = closure(tmp_path, monkeypatch, mode=mode)
    result = service.run_attempt(task.task_id)
    if mode == "degrade":
        assert isinstance(result, ReadTask)
        assert result.attempts[0].failure == "output_invalid"
        result = service.run_attempt(task.task_id)
    assert isinstance(result, ReadAnalysis)
    query = ReadQueries(service.database, service.data_root)
    view = query.analysis(result.analysis_id, snapshot_id=task.snapshot_id)
    assert (view.body_status, view.config_status) == ("current", "current")
    assert (view.executor_kind, view.root_purpose, view.quality_basis) == (
        "pi_rpc",
        "experiment",
        "experiment_document_gate",
    )
    assert view.has_discards is (mode == "degrade")
    assert result.attempt_ordinal == (2 if mode == "degrade" else 1)
    assert (
        query.evidence(result.analysis_id, "e000002")[0].text == "Exact source α = 2."
    )
    assert body.facts(task.paper_id, identity=task.identity).eligible
    from paper_radar.read_tasks import ReadTaskError

    with pytest.raises(ReadTaskError, match="ordinary_consumption_denied"):
        query.analysis(result.analysis_id, ordinary=True)


@pytest.mark.parametrize("changed", ["decision", "quality", "pdf", "metadata"])
def test_later_prerequisite_change_denies_model_execution_without_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, changed: str
) -> None:
    import httpx

    from paper_radar.feed_metadata import JGRMetadata
    from paper_radar.fixture_audit.source_http import SourceHTTPExecutor
    from paper_radar.read_tasks import ReadTaskError
    from paper_radar.screening.reasons import (
        DecisionReason,
        ScreeningReasonInput,
        ScreeningResult,
        ScreeningSource,
    )
    from tests.body_support import CHECKS, PDF

    service, task, body = closure(tmp_path, monkeypatch)
    if changed == "decision":
        body.decide(
            task.paper_id,
            ScreeningReasonInput(
                result=ScreeningResult.DENIED,
                source=ScreeningSource.DIRECT_MANUAL_DECISION,
                reason=DecisionReason.OUT_OF_SCOPE,
            ),
            request_id="deny",
            actor="human",
        )
    elif changed == "quality":
        body.review_layout(
            task.identity,
            passed=False,
            checks={**CHECKS, "reading_order": False},
            note="rejected",
            actor="human",
            request_id="reject",
        )
    elif changed == "pdf":
        body.attach_pdf(task.paper_id, PDF + b"new", request_id="changed-pdf")
    else:
        JGRMetadata(
            service.database,
            service.data_root,
            http=SourceHTTPExecutor(
                transport=httpx.MockTransport(lambda _: httpx.Response(403))
            ),
        ).enrich(
            task.paper_id,
            request_id="later-metadata",
            contact_email="contact@example.org",
        )
    with pytest.raises(ReadTaskError, match="prerequisites_failed") as caught:
        service.run_attempt(task.task_id)
    assert {
        "decision": "decision_not_accepted",
        "quality": "quality_failed",
        "pdf": "facts_changed",
        "metadata": "metadata_agency_unknown",
    }[changed] in caught.value.reasons
    assert service.tasks.task(task.task_id).attempts == ()
    assert service.tasks.analyses(task.paper_id) == ()


def test_missing_sample_stops_before_any_execution_or_task(tmp_path: Path) -> None:
    from paper_radar.read_tasks import ReadTaskError, ReadTasks
    from tests.read_tasks_support import ready

    data, _, extraction = ready(tmp_path, missing="sample")
    tasks = ReadTasks(data.database, data.data_root)
    with pytest.raises(ReadTaskError, match="prerequisites_failed") as caught:
        tasks.register(
            data.paper_id,
            snapshot_id=data.snapshot_id,
            extraction_fingerprint=extraction.fingerprint,
            request_id="read",
        )
    assert "sample_mismatch" in caught.value.reasons
    assert tasks.history(data.paper_id) == ()
    assert ReadQueries(data.database, data.data_root).history(data.paper_id) == ()


def test_real_product_admission_remains_closed_before_auth_and_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.pi_execution import ExecutionError
    from tests.read_execution_support import setup

    service, task, credentials = setup(tmp_path, monkeypatch)
    with pytest.raises(ExecutionError, match="evidence_missing"):
        service.run_attempt(task.task_id)
    assert service.tasks.task(task.task_id).attempts == ()
    assert ReadQueries(service.database, service.data_root).history(task.paper_id) == ()
    assert not (credentials / "auth-observed.json").exists()


def test_concurrent_explicit_execution_has_one_success_and_one_spent_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from concurrent.futures import ThreadPoolExecutor

    from paper_radar.read_tasks import ReadTaskError

    service, task, _ = closure(tmp_path, monkeypatch)

    def execute(_: int) -> str:
        try:
            result = service.run_attempt(task.task_id)
            assert isinstance(result, ReadAnalysis)
            return result.analysis_id
        except ReadTaskError as error:
            return error.reason

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(execute, range(2)))
    assert results.count("already_succeeded") == 1
    query = ReadQueries(service.database, service.data_root)
    assert len(query.history(task.paper_id)) == 1
    assert service.tasks.task(task.task_id).remaining_attempts == 1
    service.tasks.validate_all()


@pytest.mark.parametrize(
    "phase", ["before_file", "after_file", "before_db", "after_db"]
)
def test_file_and_database_faults_never_leave_half_or_duplicate_analysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    import os
    from contextlib import nullcontext

    from sqlalchemy import Connection, Engine, event
    from sqlalchemy.exc import SQLAlchemyError

    from paper_radar.read_tasks import ReadTaskError
    from paper_radar.storage.artifact_contract import ArtifactError
    from tests.artifact_support import fail_sql

    service, task, _ = closure(tmp_path, monkeypatch)
    original_link = os.link
    fired = False

    def link(source: str | Path, target: str | Path, **kwargs: Any) -> None:
        nonlocal fired
        # 真正发布文件边界,不替换制品或业务服务。
        if (
            phase in {"before_file", "after_file"}
            and not fired
            and Path(target).name.isalnum()
            and len(Path(target).name) == 64
        ):
            fired = True
            if phase == "after_file":
                original_link(source, target, **kwargs)
            raise OSError("injected file publication fault")
        original_link(source, target, **kwargs)

    monkeypatch.setattr(os, "link", link)

    def committed(connection: Connection) -> None:
        nonlocal fired
        if phase == "after_db" and not fired:
            # Engine.commit事件发生在实际commit之前,故以DBAPI边界模拟丢失回执。
            raw = connection.connection.driver_connection
            assert raw is not None
            raw.commit()
            fired = True
            raise SQLAlchemyError("lost acknowledgement after commit")

    if phase == "after_db":
        # 只在analysis插入后的最终提交注入,不干扰领取/供给事务。
        def arm(
            connection: Connection, cursor: object, statement: str, *args: object
        ) -> None:
            if statement.startswith("INSERT INTO read_analyses"):
                event.listen(connection, "commit", committed, once=True)

        event.listen(Engine, "before_cursor_execute", arm)
    try:
        with (
            fail_sql("INSERT INTO read_evidence")
            if phase == "before_db"
            else nullcontext(),
            pytest.raises((ReadTaskError, ArtifactError)) as caught,
        ):
            service.run_attempt(task.task_id)
        assert isinstance(caught.value, (ReadTaskError, ArtifactError))
        assert caught.value.reason in {"database_failed", "publication_failed"}
    finally:
        if phase == "after_db":
            event.remove(Engine, "before_cursor_execute", arm)
    query = ReadQueries(service.database, service.data_root)
    if phase == "after_db":
        assert len(query.history(task.paper_id)) == 1
        assert service.tasks.task(task.task_id).status == "succeeded"
    else:
        from datetime import UTC, datetime, timedelta

        from paper_radar.read_execution import ReadExecution

        assert query.history(task.paper_id) == ()
        assert service.tasks.task(task.task_id).remaining_attempts == 1
        later = datetime.now(UTC) + timedelta(seconds=601)
        restarted = ReadExecution(
            service.database,
            service.data_root,
            roots=service.roots,
            credentials_dir=service.credentials_dir,
            auth_mode=service.auth_mode,
            clock=lambda: later,
        )
        reclaimed = restarted.tasks.reclaim(task.task_id)
        assert reclaimed.attempts[0].failure == "outcome_unknown"
        recovered = restarted.run_attempt(task.task_id)
        assert isinstance(recovered, ReadAnalysis) and recovered.attempt_ordinal == 2
        assert len(query.history(task.paper_id)) == 1
        assert restarted.tasks.task(task.task_id).remaining_attempts == 0
    service.tasks.validate_all()


def test_failed_generation_retry_and_expired_lease_preserve_query_truth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from datetime import UTC, datetime, timedelta

    from paper_radar.read_tasks import ReadTask, ReadTaskError, ReadTasks
    from tests.read_tasks_support import valid_candidate

    service, task, _ = closure(tmp_path, monkeypatch, mode="environment")
    for remaining in (1, 0):
        failed = service.run_attempt(task.task_id)
        assert isinstance(failed, ReadTask)
        assert failed.remaining_attempts == remaining
        assert failed.attempts[-1].failure == "executor_error"
    query = ReadQueries(service.database, service.data_root)
    assert query.current(task.paper_id).state == "no_analysis"
    child = service.tasks.retry(
        task.task_id, request_id="retry", reason="explicit retry", actor="human"
    )
    assert (
        service.tasks.retry(
            task.task_id, request_id="again", reason="same failed parent", actor="human"
        ).task_id
        == child.task_id
    )
    time = [datetime.now(UTC)]
    tasks = ReadTasks(service.database, service.data_root, clock=lambda: time[0])
    old = tasks.claim(child.task_id)
    time[0] += timedelta(seconds=601)
    assert query.current(task.paper_id).state == "no_analysis"
    assert tasks.task(child.task_id).status == "running"
    tasks.reclaim(child.task_id)
    with pytest.raises(ReadTaskError, match="settlement_conflict"):
        tasks.submit_test(old, valid_candidate())
    result = tasks.submit_test(tasks.claim(child.task_id), valid_candidate())
    assert isinstance(result, ReadAnalysis) and result.attempt_ordinal == 2
    assert query.analysis(result.analysis_id).executor_kind == "test"
    assert tasks.task(child.task_id).remaining_attempts == 0
    assert len(query.history(task.paper_id)) == 1
    with pytest.raises(ReadTaskError, match="not_failed"):
        tasks.retry(
            child.task_id, request_id="success-retry", reason="forbidden", actor="human"
        )


def test_permanent_body_failure_cannot_produce_read_analysis(tmp_path: Path) -> None:
    from paper_radar.body.models import ParserResult
    from paper_radar.config.extraction import ExtractionSemantics
    from tests.body_support import Parser, prepared
    from tests.test_fulltext_artifacts import document

    class NoText(Parser):
        def convert(self, pdf: bytes, semantics: ExtractionSemantics) -> ParserResult:
            self.calls += 1
            return ParserResult(document().model_copy(update={"has_text_layer": False}))

    saved, body, _ = prepared(tmp_path)
    parser = NoText()
    failed = body.extract(saved.paper_id, snapshot_id=saved.snapshot_id, parser=parser)
    assert (
        failed.permanent_failure
        and failed.attempts[0].failure == "extraction_failed_no_text_layer"
    )
    again = body.extract(saved.paper_id, snapshot_id=saved.snapshot_id, parser=parser)
    assert parser.calls == 1 and again.remaining_attempts == 1
    assert ReadQueries(saved.database, saved.data_root).history(saved.paper_id) == ()


def test_complete_persisted_body_over_frame_limit_has_no_read_task_or_analysis(
    tmp_path: Path,
) -> None:
    from paper_radar.body.models import ParserResult
    from paper_radar.config.extraction import ExtractionSemantics
    from paper_radar.read_tasks import ReadTaskError, ReadTasks
    from tests.body_support import Parser
    from tests.read_tasks_support import ready
    from tests.test_fulltext_artifacts import document

    class Large(Parser):
        def convert(self, pdf: bytes, semantics: ExtractionSemantics) -> ParserResult:
            doc = document()
            text = "正文😀" * 25000
            source = doc.blocks[1]
            block = source.model_copy(
                update={
                    "orig": text,
                    "text": text,
                    "provenance": tuple(
                        p.model_copy(update={"charspan": (0, len(text))})
                        for p in source.provenance
                    ),
                }
            )
            return ParserResult(
                doc.model_copy(update={"blocks": (doc.blocks[0], block)})
            )

    data, body, extracted = ready(tmp_path, parser=Large())
    assert body.facts(data.paper_id, identity=extracted.identity).eligible
    tasks = ReadTasks(data.database, data.data_root)
    with pytest.raises(ReadTaskError, match="read_input_over_budget"):
        tasks.register(
            data.paper_id,
            snapshot_id=data.snapshot_id,
            extraction_fingerprint=extracted.fingerprint,
            request_id="read",
        )
    assert tasks.history(data.paper_id) == ()
    assert (
        ReadQueries(data.database, data.data_root).current(data.paper_id).state
        == "no_analysis"
    )
