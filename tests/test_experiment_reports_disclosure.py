"""B-E14 独立 D1:未读取历史不冒充原状态,待决定不冒充已代执行接受。"""

import json
from pathlib import Path
from typing import Literal

import pytest

from paper_radar.experiment.report_rendering import ReportEntry, ReportInput, render
from tests.experiment_screen_support import screen_fixture
from tests.test_experiment_candidates_cli import FeedFixture
from tests.test_experiment_candidates_cli import feed as feed
from tests.test_experiment_reports_cli import report
from tests.test_owner_live_waiver import command as waiver


@pytest.mark.parametrize("enabled", [True, False])
def test_unread_history_is_unknown_and_current_assessment_is_unassessed(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, enabled: bool
) -> None:
    fixture = screen_fixture(feed, tmp_path, monkeypatch)
    if not enabled:
        assert (
            waiver(
                fixture.root / "paper-radar.sqlite3",
                "--disable",
                "--reason",
                "synthetic strict disclosure",
            ).exit_code
            == 0
        )

    def forbidden() -> None:
        raise AssertionError("protected history must remain unread")

    monkeypatch.setattr("paper_radar.live_evidence.service._ledger", forbidden)
    result = report(
        fixture.root,
        "render",
        "--date",
        "2026-11-14",
        "--timezone",
        "UTC",
        "--snapshot",
        fixture.snapshot,
    )
    assert result.exit_code == 0, result.output
    receipt = json.loads(result.stdout)
    text = (fixture.root / "views" / receipt["relative_path"]).read_text()
    assert "assessment=not_assessed" in text
    assert "original_state=unknown" in text and "historical_state_read=false" in text
    assert (
        "original_state=not_assessed" not in text
        and "original_state=absent" not in text
    )
    assert "保留原 not_assessed" not in text and "evidence=verified" not in text
    assert "历史原状态 unknown（未读取）" in text
    assert "Screening" in text and "Read" in text


@pytest.mark.parametrize("accepted", [False, True])
def test_frozen_projection_only_labels_actual_delegated_acceptance(
    accepted: bool,
) -> None:
    kind: Literal["blocked", "pending"] = "blocked" if accepted else "pending"
    entry = ReportEntry(
        position=1,
        display_number="N1",
        paper_id="synthetic-paper",
        version_id="synthetic-version",
        revision_no=1,
        primary_kind=kind,
        primary_ref="synthetic-result",
        section=kind,
        first_publication_key=f"{kind}:synthetic-result",
        available_at="2026-11-14T00:00:00+00:00",
        title="Synthetic title",
        basis={
            "acceptance": {"authorizer": "owner", "actor": "agent"}
            if accepted
            else None,
            "authorization": {"authorizer": "owner"},
            "screening": None,
        },
    )
    inputs = ReportInput(
        report_id="12345678-1234-4234-8234-123456789abc",
        kind="daily",
        root_id="synthetic-root",
        report_date="2026-11-14",
        timezone="UTC",
        snapshot_id=None,
        frozen_at="2026-11-14T00:00:00+00:00",
        admission_fragment="合成未评估披露",
        summary={},
        warnings=(),
        entries=(entry,),
    )
    text = render(inputs).decode()
    if accepted:
        assert "决定来源：所有者授权 + Agent 代执行" in text
        assert "尚无代执行接受决定" not in text
    else:
        assert "尚无代执行接受决定" in text and "保留选样授权" in text
        assert "决定来源：所有者授权 + Agent 代执行" not in text
