"""多成员合成实验:逐篇经真实选择/授权/接受/核查/Read CLI。"""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from paper_radar.body import BodyService
from tests.experiment_layout_support import LayoutFixture, synthetic_pdf
from tests.experiment_read_support import ReadFixture, read_fixture
from tests.test_experiment_accept_cli import accept
from tests.test_experiment_candidates_cli import FeedFixture, invoke
from tests.test_experiment_pdf_cli import attach
from tests.test_experiment_selection_cli import select


def multi_report_fixture(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[ReadFixture, list[str], str, str]:
    fixture = read_fixture(feed, tmp_path, monkeypatch)
    first = fixture.read()
    assert first.exit_code == 0, first.output
    analyses = [json.loads(first.stdout)["task"]["analysis_id"]]
    root, state, fetch = feed
    state["order"] = list(range(1, 7))
    check = fetch("multi-report")
    candidates = invoke(
        "candidates", "--root", str(root), "--check-id", check["check_id"]
    )
    assert candidates.exit_code == 0, candidates.output
    view = json.loads(candidates.stdout)["view_id"]
    previous = fixture.layout.extraction.prepared.selection_id
    pending = blocked = ""
    for number in range(2, 7):
        selected = select(
            root,
            view,
            f"report-select-{number}",
            "--position",
            str(number),
            "--replaces",
            previous,
            "--replacement-reason",
            "PRIVATE_MULTI_REPLACEMENT",
        )
        assert selected.exit_code == 0, selected.output
        selection = json.loads(selected.stdout)
        previous = selection["selection_id"]
        prepared = replace(
            fixture.layout.extraction.prepared,
            selection_id=previous,
            paper_id=selection["paper_id"],
            view_id=view,
        )
        screened = prepared.screen()
        assert screened.exit_code == 0, screened.output
        if number == 5:
            pending = json.loads(screened.stdout)["value"]["success_id"]
            continue
        accepted = accept(prepared, request=f"report-accept-{number}")
        assert accepted.exit_code == 0, accepted.output
        if number == 6:
            blocked = f"needs-pdf:{json.loads(accepted.stdout)['decision_id']}"
            continue
        attached = attach(
            prepared,
            tmp_path,
            request=f"report-pdf-{number}",
            raw=synthetic_pdf() + f"\n% synthetic member {number}\n".encode(),
        )
        assert attached.exit_code == 0, attached.output
        extraction = replace(fixture.layout.extraction, prepared=prepared)
        extracted = extraction.extract()
        assert extracted.exit_code == 0, extracted.output
        identity = (
            BodyService(extraction.root.database, extraction.root.data_root)
            .current_body(prepared.paper_id)
            .identity
        )
        assert identity is not None
        layout = LayoutFixture(extraction, identity)
        layout.review(request=f"report-review-{number}")
        read = ReadFixture(layout, fixture.snapshot).read(
            request=f"report-read-{number}"
        )
        assert read.exit_code == 0, read.output
        analyses.append(json.loads(read.stdout)["task"]["analysis_id"])
    return fixture, analyses, pending, blocked
