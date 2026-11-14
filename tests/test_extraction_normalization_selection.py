"""独立D1:旧版否决到新版显式选择/再核查/真实Read受限消费的合成CLI链。"""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from paper_radar.body import BodyService
from paper_radar.body.selection import BodySelections
from paper_radar.config import compile_config, load_config_snapshot
from paper_radar.docling_execution.models import WorkerResponse
from paper_radar.fulltext.artifacts import FulltextArtifacts
from paper_radar.read_queries import ReadQueries
from paper_radar.read_tasks import ReadTasks
from tests.body_selection_support import choose
from tests.config_projection_support import new_yaml_version
from tests.experiment_extract_support import executor
from tests.experiment_read_support import read_fixture
from tests.test_experiment_candidates_cli import FeedFixture
from tests.test_experiment_candidates_cli import feed as feed
from tests.test_extraction_normalization_repair import item, mapped


def test_vetoed_v1_reextract_select_review_and_read_v2_restricted_source(
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from paper_radar import reading_cli
    from paper_radar.experiment.layout import LayoutReviews

    # 单一短变量重复,无字体/inline/span字段;同一PDF与同一真实mapper结果。
    text = "One parameter qr qr needs verification in this synthetic observation."
    canonical, raw = mapped([item(0, text)], pages=1)
    fixture = read_fixture(
        feed, tmp_path, monkeypatch, reviewed=False, canonical=canonical
    )
    layout = fixture.layout
    extraction = layout.extraction
    root = extraction.root
    paper = extraction.prepared.paper_id
    body = BodyService(root.database, root.data_root)
    tasks = ReadTasks(root.database, root.data_root)
    old_identity = layout.identity
    old_snapshot = load_config_snapshot(root.database, fixture.snapshot)
    old = body.extraction(old_identity.extraction_fingerprint)
    assert old is not None and old.artifact_id is not None
    assert (
        not FulltextArtifacts(body.store)
        .load(old.artifact_id, expected_identity=old_identity)
        .context.replay()[0]
        .unreliable
    )
    rejected_review = layout.review(passed=False, request="v1-owner-veto")
    old = body.extraction(old_identity.extraction_fingerprint)
    assert old is not None and old.permanent_failure and old.artifact_id is not None
    old_members = body.store.read_artifact(old.artifact_id)
    old_pdf = body.current_pdf(paper)
    assert old_pdf is not None
    old_reviews = LayoutReviews(root.database, root.data_root).history(paper)
    assert len(old_reviews) == 1 and old_reviews[0]["passed"] is False
    assert rejected_review["fingerprint"] == old.fingerprint

    new_yaml_version(
        root.settings,
        "extraction",
        lambda value: value.update(normalization_version="v2"),
    )
    new_snapshot = compile_config(root.settings, root.database)
    assert old_snapshot.extraction is not None and new_snapshot.extraction is not None
    assert old_snapshot.extraction.backend == new_snapshot.extraction.backend
    assert (
        old_snapshot.extraction.model_artifacts
        == new_snapshot.extraction.model_artifacts
    )
    assert (
        old_snapshot.extraction.backend_config_json
        == new_snapshot.extraction.backend_config_json
    )
    assert new_snapshot.extraction.normalization_version == "v2"
    extraction.snapshot = fixture.snapshot = new_snapshot.snapshot_id
    calls = executor(
        monkeypatch, WorkerResponse(document=canonical, document_json=raw.decode())
    )
    extracted = extraction.extract()
    assert extracted.exit_code == 0, extracted.output
    payload = json.loads(extracted.stdout)
    # 不靠最新遍历/配置猜三元组:必须解引用实际extract返回的准确fingerprint。
    new = body.extraction(payload["fingerprint"])
    assert new is not None and new.artifact_id is not None and new.identity is not None
    assert new.fingerprint != old.fingerprint and new.pdf_sha256 == old.pdf_sha256
    assert len(calls) == 1 and new.remaining_attempts == old.remaining_attempts == 1
    assert body.current_pdf(paper) == old_pdf
    assert body.current_body(paper).reason == "ambiguous_extractions"
    layout.identity = new.identity
    selected = choose(layout, request="owner-select-v2")
    assert selected.exit_code == 0, selected.output
    assert body.current_body(paper).identity == new.identity
    (selection,) = BodySelections(root.database, root.data_root).history(paper)
    assert selection.identity == new.identity
    assert (selection.selector, selection.recorder) == ("owner", "agent")
    selected_view = body.extraction(new.fingerprint)
    assert selected_view is not None and selected_view.quality.basis == "absent"

    # 选择不代替新六项,且拒绝必须发生在认证/任务/预算之前。
    observed = extraction.prepared.credentials / "auth-observed.json"
    before_auth = observed.stat().st_mtime_ns
    missing_review = fixture.read(request="new-v2-read")
    assert (
        missing_review.exit_code == 2
        and "document_gate_required" in missing_review.output
    )
    assert observed.stat().st_mtime_ns == before_auth
    assert tasks.history(paper) == () and tasks.analyses(paper) == ()
    review = layout.review(passed=True, request="new-v2-owner-review")
    assert review["passed"] is True and review["fingerprint"] == new.fingerprint
    assert review["review_id"] != rejected_review["review_id"]
    loaded = FulltextArtifacts(body.store).load(
        new.artifact_id, expected_identity=new.identity
    )
    (source,) = loaded.context.replay()
    assert source.unreliable and source.text == text
    assert source.evidence_id == "e000002" and source.provenance.start == 0
    assert source.provenance.end == len(text)
    assert source.provenance.page_no == 1 and source.provenance.bbox == (
        20.0,
        150.0,
        500.0,
        170.0,
    )
    read_time = datetime.now(UTC)
    monkeypatch.setattr(reading_cli, "reading_clock", lambda: read_time)
    completed = fixture.read(request="new-v2-read")
    assert completed.exit_code == 0, completed.output
    result = json.loads(completed.stdout)
    assert result["state"] == "succeeded"
    (task,) = tasks.history(paper)
    assert task.identity == new.identity and len(task.attempts) == 1
    assert task.remaining_attempts == 1
    analysis = tasks.analysis(task.analysis_id or "")
    assert [(d["location"], d["reason"]) for d in analysis.diagnostics] == [
        ("$.research_value_reason.statement", "restricted_source_reference"),
        ("$.reuse_feasibility_reason.statement", "restricted_source_reference"),
    ]
    assert len(analysis.warnings) == 2 and all(
        w["origin"] == "program" for w in analysis.warnings
    )
    current = ReadQueries(root.database, root.data_root).current(paper)
    assert current.state == "available" and current.identity == new.identity
    assert current.analyses[0].restricted_content_warning
    assert (
        "ordinary_consumption_denied"
        in body.facts(paper, identity=new.identity, ordinary=True).reasons
    )
    assert body.extraction(old.fingerprint) == old
    assert body.store.read_artifact(old.artifact_id) == old_members
    reviews = {
        record["review_id"]: record
        for record in LayoutReviews(root.database, root.data_root).history(paper)
    }
    assert reviews[old_reviews[0]["review_id"]] == old_reviews[0]
    unchanged_extraction = body.extraction(new.fingerprint)
    assert unchanged_extraction is not None
    assert unchanged_extraction.attempts == new.attempts
    tasks.validate_all()
