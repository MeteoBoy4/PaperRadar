"""D1实际持久前置、重复请求、语言及输入回摆。"""

from pathlib import Path
from typing import Any, Literal

import pytest

from paper_radar.config import compile_config
from paper_radar.read_inputs import PreparedReadInput
from paper_radar.read_tasks import (
    ReadAnalysis,
    ReadHandle,
    ReadTask,
    ReadTaskError,
    ReadTasks,
)
from tests.config_projection_support import new_yaml_version
from tests.read_tasks_support import ready, valid_candidate


@pytest.mark.parametrize(
    ("missing", "reason"),
    [
        ("metadata", "metadata_unknown"),
        ("accepted", "decision_not_accepted"),
        ("sample", "sample_mismatch"),
        ("quality", "quality_absent"),
    ],
)
def test_registration_requires_real_persisted_prerequisites(
    tmp_path: Path, missing: str, reason: str
) -> None:
    data, _, extraction = ready(tmp_path, missing=missing)
    tasks = ReadTasks(data.database, data.data_root)
    with pytest.raises(ReadTaskError, match="prerequisites_failed") as caught:
        tasks.register(
            data.paper_id,
            snapshot_id=data.snapshot_id,
            extraction_fingerprint=extraction.fingerprint,
            request_id="read",
        )
    assert reason in caught.value.reasons
    assert tasks.history(data.paper_id) == ()


def test_changed_decision_is_rechecked_at_claim_before_executor(tmp_path: Path) -> None:
    from paper_radar.screening.reasons import (
        DecisionReason,
        ScreeningReasonInput,
        ScreeningResult,
        ScreeningSource,
    )

    data, body, extraction = ready(tmp_path)
    tasks = ReadTasks(data.database, data.data_root)
    task = tasks.register(
        data.paper_id,
        snapshot_id=data.snapshot_id,
        extraction_fingerprint=extraction.fingerprint,
        request_id="read",
    )
    body.decide(
        data.paper_id,
        ScreeningReasonInput(
            result=ScreeningResult.DENIED,
            source=ScreeningSource.DIRECT_MANUAL_DECISION,
            reason=DecisionReason.OUT_OF_SCOPE,
        ),
        request_id="deny",
        actor="human",
    )
    called: list[ReadHandle] = []

    def execute(handle: ReadHandle) -> bytes:
        called.append(handle)
        return valid_candidate()

    with pytest.raises(ReadTaskError, match="prerequisites_failed"):
        tasks.run_once(task.task_id, execute)
    assert not called and tasks.task(task.task_id).remaining_attempts == 2


def test_a_b_a_snapshot_language_and_labels_do_not_refill_budget(
    tmp_path: Path,
) -> None:
    data, _, extraction = ready(tmp_path)
    tasks = ReadTasks(data.database, data.data_root)

    def register(
        snapshot: str,
        key: str,
        language: Literal["zh", "en"] = "zh",
        label: str = "manual",
    ) -> ReadTask:
        return tasks.register(
            data.paper_id,
            snapshot_id=snapshot,
            extraction_fingerprint=extraction.fingerprint,
            request_id=key,
            output_language=language,
            label=label,
        )

    first = register(data.snapshot_id, "a")
    tasks.fail(tasks.claim(first.task_id), "timeout")
    new_yaml_version(
        data.settings, "profile", lambda c: c.update(background="Changed background")
    )
    newer = compile_config(data.settings, data.database)
    other = register(newer.snapshot_id, "b")
    returned = register(data.snapshot_id, "a-again", label="experiment")
    english = register(data.snapshot_id, "en", language="en")
    assert returned.task_id == first.task_id and returned.remaining_attempts == 1
    assert len({first.fingerprint, other.fingerprint, english.fingerprint}) == 3
    assert other.remaining_attempts == english.remaining_attempts == 2
    assert (
        tasks.prepare(first.task_id).description.semantic_snapshot_id
        == data.snapshot_id
    )


def test_preclaim_rejects_without_attempt_and_receives_latest_correction(
    tmp_path: Path,
) -> None:
    data, _, extraction = ready(tmp_path)
    tasks = ReadTasks(data.database, data.data_root)
    task = tasks.register(
        data.paper_id,
        snapshot_id=data.snapshot_id,
        extraction_fingerprint=extraction.fingerprint,
        request_id="read",
    )

    def reject(prepared: PreparedReadInput, correction: str | None) -> None:
        assert prepared.budget.accepted and correction is None
        raise ReadTaskError("read_input_over_budget")

    with pytest.raises(ReadTaskError, match="read_input_over_budget"):
        tasks.claim(task.task_id, preclaim=reject)
    assert tasks.task(task.task_id).attempts == ()


def test_experimental_test_analysis_visible_and_ordinary_consumption_rejected(
    tmp_path: Path,
) -> None:
    data, _, extraction = ready(tmp_path)
    tasks = ReadTasks(data.database, data.data_root)
    task = tasks.register(
        data.paper_id,
        snapshot_id=data.snapshot_id,
        extraction_fingerprint=extraction.fingerprint,
        request_id="read",
    )
    result = tasks.run_once(task.task_id, lambda _: valid_candidate())
    assert isinstance(result, ReadAnalysis)
    assert result.root_purpose == "experiment" and result.executor_kind == "test"
    assert result.quality_basis == "experiment_document_gate"
    assert tasks.analyses(data.paper_id)[0].analysis_id == result.analysis_id
    with pytest.raises(ReadTaskError, match="ordinary_consumption_denied"):
        tasks.analysis(result.analysis_id, ordinary=True)


def test_metadata_consumer_reads_real_routes_in_supplied_uncommitted_view(
    tmp_path: Path,
) -> None:
    from sqlalchemy import Engine, event

    from paper_radar.feed_metadata import JGRMetadata
    from paper_radar.storage.database import DatabaseMode, open_database

    data, _, _ = ready(tmp_path)
    engine = open_database(data.database, mode=DatabaseMode.READ_WRITE)
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("BEGIN IMMEDIATE")
            connection.exec_driver_sql(
                "UPDATE feed_metadata_requests SET revision_no=NULL"
            )

            def forbid_connect(*_args: Any, **_kwargs: Any) -> None:
                raise AssertionError("second_database_view")

            event.listen(Engine, "engine_connect", forbid_connect)
            try:
                facts = JGRMetadata(data.database, data.data_root).facts_in_connection(
                    connection, data.paper_id
                )
                assert facts is not None and not facts.minimum_complete
                assert "routes_incomplete" in facts.missing
            finally:
                event.remove(Engine, "engine_connect", forbid_connect)
            connection.rollback()
    finally:
        engine.dispose()


def test_claim_rejects_changed_pdf_before_model_and_preserves_attempt_budget(
    tmp_path: Path,
) -> None:
    from tests.body_support import PDF

    data, body, extraction = ready(tmp_path)
    service = ReadTasks(data.database, data.data_root)
    task = service.register(
        data.paper_id,
        snapshot_id=data.snapshot_id,
        extraction_fingerprint=extraction.fingerprint,
        request_id="read",
    )
    body.attach_pdf(data.paper_id, PDF + b"updated", request_id="changed")
    with pytest.raises(ReadTaskError, match="prerequisites_failed") as caught:
        service.claim(task.task_id)
    assert "facts_changed" in caught.value.reasons
    assert service.task(task.task_id).remaining_attempts == 2


def test_real_complete_frame_over_budget_rejected_without_task_or_attempt(
    tmp_path: Path,
) -> None:
    from paper_radar.body.models import ParserResult
    from paper_radar.config.extraction import ExtractionSemantics
    from tests.body_support import Parser
    from tests.test_fulltext_artifacts import document

    class LargeParser(Parser):
        def convert(self, pdf: bytes, semantics: ExtractionSemantics) -> ParserResult:
            doc = document()
            source = doc.blocks[1]
            text = "正文😀" * 25000
            provenance = tuple(
                p.model_copy(update={"charspan": (0, len(text))})
                for p in source.provenance
            )
            changed = source.model_copy(
                update={"orig": text, "text": text, "provenance": provenance}
            )
            return ParserResult(
                doc.model_copy(update={"blocks": (doc.blocks[0], changed)})
            )

    data, _, extraction = ready(tmp_path, parser=LargeParser())
    service = ReadTasks(data.database, data.data_root)
    with pytest.raises(ReadTaskError, match="read_input_over_budget"):
        service.register(
            data.paper_id,
            snapshot_id=data.snapshot_id,
            extraction_fingerprint=extraction.fingerprint,
            request_id="read",
        )
    assert service.history(data.paper_id) == ()
