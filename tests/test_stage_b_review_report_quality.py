"""D1:有制品的质量失败仍作为日报受阻事实,旧空报固定重建。"""

import json
from pathlib import Path

import pytest

from paper_radar.docling_execution.models import WorkerResponse
from paper_radar.eligibility import Concept, EligibilityReason
from paper_radar.fulltext.canonical import CanonicalDocument
from paper_radar.paper_trace import query_paper_trace
from tests.body_selection_support import choose, second_body
from tests.experiment_extract_support import executor, extract_fixture
from tests.experiment_layout_support import layout_fixture
from tests.test_experiment_candidates_cli import FeedFixture
from tests.test_experiment_candidates_cli import feed as feed
from tests.test_experiment_reports_cli import report
from tests.test_fulltext_artifacts import document


def test_artifact_with_automatic_quality_failure_remains_reported(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = extract_fixture(feed, tmp_path, monkeypatch)
    before = query_paper_trace(
        fixture.root.database,
        fixture.root.data_root,
        fixture.prepared.paper_id,
        snapshot_id=fixture.snapshot,
    )
    assert (
        EligibilityReason.EXTRACTION_ABSENT
        in before.eligibility[Concept.READ_PREREQUISITES].reasons
    )
    assert (
        EligibilityReason.PDF_UNKNOWN
        not in before.eligibility[Concept.READ_PREREQUISITES].reasons
    )
    assert before.projection.read_tasks is not None
    assert before.projection.read_tasks.mapping_determinable is False
    raw = document().model_dump(mode="json")
    raw["has_text_layer"] = False
    executor(
        monkeypatch,
        WorkerResponse(
            document=CanonicalDocument.model_validate_json(json.dumps(raw)),
            document_json='{"synthetic":true}',
            peak_memory_bytes=7,
        ),
    )
    extracted = fixture.extract()
    assert extracted.exit_code == 2, extracted.output
    payload = json.loads(extracted.stdout)
    assert payload["permanent_failure"] is True
    assert payload["artifact_id"]
    failed = query_paper_trace(
        fixture.root.database,
        fixture.root.data_root,
        fixture.prepared.paper_id,
        snapshot_id=fixture.snapshot,
    )
    reasons = failed.eligibility[Concept.READ_PREREQUISITES].reasons
    assert EligibilityReason.EXTRACTION_RETRY_REQUIRED in reasons
    assert EligibilityReason.QUALITY_FAILED in reasons
    assert failed.projection.read_tasks is not None
    assert failed.projection.read_tasks.mapping_determinable is False
    rendered = report(
        fixture.root.root,
        "render",
        "--date",
        "2026-11-15",
        "--timezone",
        "UTC",
        "--snapshot",
        fixture.snapshot,
    )
    assert rendered.exit_code == 0, rendered.output
    receipt = json.loads(rendered.stdout)
    text = (fixture.root.views / receipt["relative_path"]).read_text()
    assert "PDF/解析受阻" in text
    assert "积压=1" in text
    assert "无新结果。" not in text


def test_owner_veto_is_blocked_and_earlier_healthy_empty_report_stays_frozen(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = layout_fixture(feed, tmp_path, monkeypatch)
    root = fixture.extraction.root
    first = report(root.root, "render", "--date", "2026-11-14", "--timezone", "UTC")
    assert first.exit_code == 0, first.output
    old = json.loads(first.stdout)
    old_path = root.views / old["relative_path"]
    original = old_path.read_bytes()
    assert "无新结果。" in original.decode()
    veto = fixture.review(passed=False)
    assert veto["passed"] is False
    second = report(root.root, "render", "--date", "2026-11-15", "--timezone", "UTC")
    assert second.exit_code == 0, second.output
    new = json.loads(second.stdout)
    text = (root.views / new["relative_path"]).read_text()
    assert "PDF/解析受阻" in text and "layout_review" in text
    assert "积压=1" in text
    assert report(root.root, "rebuild", old["report_id"]).exit_code == 0
    assert old_path.read_bytes() == original


def test_new_selected_body_clears_current_blockage_and_preserves_veto_report(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = layout_fixture(feed, tmp_path, monkeypatch)
    root = fixture.extraction.root
    fixture.review(passed=False, request="old-veto")
    first = report(root.root, "render", "--date", "2026-11-14", "--timezone", "UTC")
    assert first.exit_code == 0, first.output
    old = json.loads(first.stdout)
    original = (root.views / old["relative_path"]).read_bytes()
    fixture.identity = second_body(fixture)
    ambiguous = report(root.root, "render", "--date", "2026-11-15", "--timezone", "UTC")
    assert ambiguous.exit_code == 0, ambiguous.output
    uncertain = json.loads(ambiguous.stdout)
    assert uncertain["members"] == []
    uncertain_text = (root.views / uncertain["relative_path"]).read_text()
    assert (
        "ambiguous_extractions" in uncertain_text
        and "因故障没有结果。" in uncertain_text
    )
    assert choose(fixture).exit_code == 0
    fixture.review(passed=True, request="new-pass")
    final = report(root.root, "render", "--date", "2026-11-16", "--timezone", "UTC")
    assert final.exit_code == 0, final.output
    receipt = json.loads(final.stdout)
    text = (root.views / receipt["relative_path"]).read_text()
    assert receipt["members"] == []
    assert "积压=0" in text and "无新结果。" in text
    assert "PDF/解析受阻" not in text and "正文不可判定" not in text
    assert report(root.root, "rebuild", old["report_id"]).exit_code == 0
    assert (root.views / old["relative_path"]).read_bytes() == original
