"""D1 公共只读分析查询的正文与配置轴。"""

from pathlib import Path

from paper_radar.read_queries import ReadQueries
from paper_radar.read_tasks import ReadAnalysis, ReadTask, ReadTasks
from tests.read_tasks_support import ready, valid_candidate


def test_current_body_without_analysis_is_distinct_from_unknown_identity(
    tmp_path: Path,
) -> None:
    data, body, extraction = ready(tmp_path)
    query = ReadQueries(data.database, data.data_root)
    empty = query.current(data.paper_id, snapshot_id=data.snapshot_id)
    assert empty.state == "no_analysis"
    assert empty.identity == extraction.identity
    tasks = ReadTasks(data.database, data.data_root)
    task = tasks.register(
        data.paper_id,
        snapshot_id=data.snapshot_id,
        extraction_fingerprint=extraction.fingerprint,
        request_id="read",
    )
    analysis = tasks.submit_test(tasks.claim(task.task_id), valid_candidate())
    assert isinstance(analysis, ReadAnalysis)
    current = query.current(data.paper_id, snapshot_id=data.snapshot_id)
    assert current.state == "available"
    assert current.analyses[0].body_status == "current"
    assert current.analyses[0].config_status == "current"
    assert current.analyses[0].analysis_id == analysis.analysis_id
    assert not hasattr(current.analyses[0], "raw_candidate")
    body.attach_pdf(
        data.paper_id, b"%PDF-1.7\n" + b"new bytes " * 150, request_id="new-pdf"
    )
    assert query.current(data.paper_id).state == "undeterminable"
    assert query.current(data.paper_id).identity_reason == "extraction_absent"
    assert query.analysis(analysis.analysis_id).body_status == "undeterminable"


def test_discarded_items_cannot_escape_into_dto_or_evidence_lookup(
    tmp_path: Path,
) -> None:
    import json
    from dataclasses import asdict

    import pytest

    from paper_radar.read_tasks import ReadTaskError

    data, _, extraction = ready(tmp_path)
    tasks = ReadTasks(data.database, data.data_root)
    task = tasks.register(
        data.paper_id,
        snapshot_id=data.snapshot_id,
        extraction_fingerprint=extraction.fingerprint,
        request_id="read",
    )
    bad = valid_candidate(
        main_findings=[
            {
                "statement": "PRIVATE DISCARDED SENTENCE。",
                "evidence": [
                    {"evidence_id": "e000001"},
                    {"evidence_id": "PRIVATE_BAD_ID"},
                ],
            },
            {"statement": "合法保留内容。", "evidence": [{"evidence_id": "e000002"}]},
        ]
    )
    tasks.submit_test(tasks.claim(task.task_id), bad)
    result = tasks.submit_test(tasks.claim(task.task_id), bad)
    assert isinstance(result, ReadAnalysis)
    query = ReadQueries(data.database, data.data_root)
    view = query.analysis(result.analysis_id)
    assert view.has_discards
    assert [(c.category, c.count) for c in view.discard_counts] == [
        ("main_findings", 1),
        ("reusable_points", 0),
        ("key_limitations", 0),
    ]
    rendered = json.dumps(asdict(view), default=str)
    assert "PRIVATE DISCARDED" not in rendered and "PRIVATE_BAD_ID" not in rendered
    assert (
        query.evidence(result.analysis_id, "e000002")[0].text == "Exact source α = 2."
    )
    with pytest.raises(ReadTaskError, match="corrupt_reference"):
        query.evidence(result.analysis_id, "PRIVATE_BAD_ID")
    with pytest.raises(ReadTaskError, match="corrupt_reference"):
        query.evidence(result.analysis_id, "e000001")


def test_ambiguous_body_denies_new_claim_but_preserves_accepted_history(
    tmp_path: Path,
) -> None:
    import pytest

    from paper_radar.config import compile_config
    from paper_radar.read_tasks import ReadTaskError
    from tests.body_support import CHECKS, Parser
    from tests.config_projection_support import new_yaml_version

    data, body, extraction = ready(tmp_path)
    tasks = ReadTasks(data.database, data.data_root)

    def register(request: str) -> ReadTask:
        return tasks.register(
            data.paper_id,
            snapshot_id=data.snapshot_id,
            extraction_fingerprint=extraction.fingerprint,
            request_id=request,
        )

    task = register("read")
    result = tasks.submit_test(tasks.claim(task.task_id), valid_candidate())
    assert isinstance(result, ReadAnalysis)
    pending = tasks.register(
        data.paper_id,
        snapshot_id=data.snapshot_id,
        extraction_fingerprint=extraction.fingerprint,
        request_id="english",
        output_language="en",
    )
    new_yaml_version(
        data.settings,
        "extraction",
        lambda c: c["models"]["layout"]["files"][0].update(sha256="9" * 64),
    )
    newer = compile_config(data.settings, data.database)
    second = body.extract(data.paper_id, snapshot_id=newer.snapshot_id, parser=Parser())
    assert second.identity is not None and second.identity != extraction.identity
    body.review_layout(
        second.identity,
        passed=True,
        checks=CHECKS,
        note="new check",
        actor="human",
        request_id="second-review",
    )
    query = ReadQueries(data.database, data.data_root)
    assert query.current(data.paper_id).state == "undeterminable"
    assert query.current(data.paper_id).identity_reason == "ambiguous_extractions"
    assert query.analysis(result.analysis_id).output.research_value == 3
    with pytest.raises(ReadTaskError, match="prerequisites_failed") as caught:
        tasks.claim(pending.task_id)
    assert "facts_changed" in caught.value.reasons
    assert tasks.task(pending.task_id).remaining_attempts == 2
    with pytest.raises(ReadTaskError, match="prerequisites_failed"):
        register("cannot-self-select-old")
    tasks.validate_all()


def test_ordinary_query_rejects_experiment_even_without_analysis(
    tmp_path: Path,
) -> None:
    import pytest

    from paper_radar.read_tasks import ReadTaskError

    data, _, _ = ready(tmp_path)
    query = ReadQueries(data.database, data.data_root)
    with pytest.raises(ReadTaskError, match="ordinary_consumption_denied"):
        query.current(data.paper_id, ordinary=True)


def test_missing_pdf_is_undeterminable_not_an_unread_body(tmp_path: Path) -> None:
    from tests.body_support import body_archive

    data = body_archive(tmp_path)
    result = ReadQueries(data.database, data.data_root).current(data.paper_id)
    assert result.state == "undeterminable"
    assert result.identity_reason == "pdf_absent"
    assert result.identity is None and result.analyses == ()


def test_restricted_source_warning_survives_safe_dto(tmp_path: Path) -> None:
    from paper_radar.body.models import ParserResult
    from paper_radar.config.extraction import ExtractionSemantics
    from tests.body_support import Parser
    from tests.read_queries_support import successful
    from tests.test_fulltext_artifacts import document

    class FormulaParser(Parser):
        def convert(self, pdf: bytes, semantics: ExtractionSemantics) -> ParserResult:
            doc = document()
            changed = doc.blocks[1].model_copy(
                update={"label": "formula", "formula_mode": "display"}
            )
            return ParserResult(
                doc.model_copy(update={"blocks": (doc.blocks[0], changed)})
            )

    data, _, extraction = ready(tmp_path, parser=FormulaParser())
    tasks = ReadTasks(data.database, data.data_root)
    result = successful(tasks, data, extraction.fingerprint, "read")
    view = ReadQueries(data.database, data.data_root).analysis(result.analysis_id)
    assert view.restricted_content_warning
    assert not view.has_discards
    assert view.output.degraded_content_warnings


def test_current_version_without_pdf_cannot_borrow_previous_version_body(
    tmp_path: Path,
) -> None:
    from paper_radar.body import BodyService
    from paper_radar.papers import PaperFacts
    from tests.body_support import PDF, Parser, body_archive
    from tests.test_paper_service import observation
    from tests.test_version_relations import relation

    data = body_archive(tmp_path)
    papers = PaperFacts(data.database, data.data_root)
    pre = papers.submit(
        observation(doi="10.1/pre", version_kind="preprint", relations=relation())
    )
    assert pre.paper_id is not None
    body = BodyService(data.database, data.data_root)
    body.attach_pdf(pre.paper_id, PDF, request_id="pre-pdf")
    body.extract(pre.paper_id, snapshot_id=data.snapshot_id, parser=Parser())
    query = ReadQueries(data.database, data.data_root)
    assert query.current(pre.paper_id).state == "no_analysis"
    papers.submit(observation(doi="10.1/journal"))
    assert query.current(pre.paper_id).identity_reason == "pdf_absent"
    assert query.current(pre.paper_id).state == "undeterminable"
