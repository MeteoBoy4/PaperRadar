"""D1:trace 从共享 Body 当前正文装配资格,通过不授予自动执行。"""

from pathlib import Path

import pytest

from paper_radar.body import BodyService
from paper_radar.eligibility import Concept, EligibilityReason
from paper_radar.paper_trace import query_paper_trace
from tests.a7_registration_support import archive
from tests.body_selection_support import choose, second_body
from tests.experiment_layout_support import layout_fixture
from tests.experiment_read_support import read_fixture
from tests.test_experiment_candidates_cli import FeedFixture
from tests.test_experiment_candidates_cli import feed as feed


def test_trace_reports_actual_read_prerequisites_without_auto_permission(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = read_fixture(feed, tmp_path, monkeypatch)
    root = fixture.layout.extraction.root
    paper = fixture.layout.extraction.prepared.paper_id
    facts = BodyService(root.database, root.data_root).facts(
        paper, identity=fixture.layout.identity
    )
    assert facts.reasons == ()
    trace = query_paper_trace(
        root.database, root.data_root, paper, snapshot_id=fixture.snapshot
    )
    assert trace.eligibility[Concept.READ_PREREQUISITES].eligible is True
    auto = trace.eligibility[Concept.ELIGIBLE_FOR_AUTO_READ]
    assert auto.eligible is False
    assert EligibilityReason.EXPERIMENT_NO_AUTO_QUEUE in auto.reasons
    fixture.layout.review(passed=False, request="old-veto")
    denied = query_paper_trace(root.database, root.data_root, paper)
    assert (
        EligibilityReason.QUALITY_FAILED
        in denied.eligibility[Concept.READ_PREREQUISITES].reasons
    )
    original = fixture.layout.identity
    fixture.layout.identity = second_body(fixture.layout)
    ambiguous = query_paper_trace(root.database, root.data_root, paper)
    assert (
        EligibilityReason.EXTRACTION_UNKNOWN
        in ambiguous.eligibility[Concept.READ_PREREQUISITES].reasons
    )
    assert choose(fixture.layout).exit_code == 0
    fixture.layout.review(passed=True, request="new-pass")
    selected = query_paper_trace(root.database, root.data_root, paper)
    assert selected.eligibility[Concept.READ_PREREQUISITES].eligible is True
    fixture.layout.identity = original
    assert choose(fixture.layout, request="select-old").exit_code == 0
    vetoed = query_paper_trace(root.database, root.data_root, paper)
    assert (
        EligibilityReason.QUALITY_FAILED
        in vetoed.eligibility[Concept.READ_PREREQUISITES].reasons
    )


def test_trace_knows_pdf_is_absent(tmp_path: Path) -> None:
    data = archive(tmp_path)
    trace = query_paper_trace(data.database, data.data_root, data.paper_id)
    reasons = trace.eligibility[Concept.READ_PREREQUISITES].reasons
    assert EligibilityReason.PDF_ABSENT in reasons
    assert EligibilityReason.PDF_UNKNOWN not in reasons


def test_trace_with_unready_read_snapshot_keeps_task_mapping_undeterminable(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = layout_fixture(feed, tmp_path, monkeypatch)
    fixture.review()
    root = fixture.extraction.root
    paper = fixture.extraction.prepared.paper_id
    trace = query_paper_trace(
        root.database, root.data_root, paper, snapshot_id=fixture.extraction.snapshot
    )
    assert trace.eligibility[Concept.READ_PREREQUISITES].eligible is True
    assert trace.projection.read_tasks is not None
    assert trace.projection.read_tasks.mapping_determinable is False
    assert trace.projection.read_tasks.current_failed_task_ids == ()
