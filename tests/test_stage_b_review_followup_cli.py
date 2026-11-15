"""#185 r1/r2 独立 D1:跨论文 trace 与报告等修复的产品接缝。"""

import hashlib
import json
from datetime import UTC, datetime, tzinfo
from pathlib import Path

import httpx
import pytest
from pydantic import TypeAdapter
from typer.testing import CliRunner

from paper_radar.cli import app
from tests.test_experiment_candidates_cli import FeedFixture
from tests.test_experiment_candidates_cli import feed as feed
from tests.test_experiment_selection_cli import Candidate, select
from tests.test_experiment_selection_cli import candidate as candidate


def test_plain_cgroup_is_rejected_before_extraction_budget(
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.experiment_extract_support import executor, extract_fixture

    fixture = extract_fixture(feed, tmp_path, monkeypatch)
    requests = executor(monkeypatch)
    # 数值限制合格并不证明属于用户 manager 管理的 scope。
    fixture.proc.write_text("0::/user/synthetic\n")
    result = fixture.extract()
    assert result.exit_code == 2, result.output
    assert "cgroup_limit_invalid" in result.output
    assert requests == []
    assert not (fixture.root.data_root / ".body-docling.lock").exists()
    trace = CliRunner().invoke(
        app,
        [
            "paper",
            "trace",
            fixture.prepared.paper_id,
            "--database",
            str(fixture.root.database),
            "--data-root",
            str(fixture.root.data_root),
            "--workflow",
            "--json",
        ],
    )
    assert trace.exit_code == 0, trace.output
    assert json.loads(trace.stdout)["workflow"]["extractions"] == []


@pytest.mark.parametrize(
    "change", ["uid", "manager_group", "inactive", "persistent", "duplicate"]
)
def test_scope_name_and_limits_do_not_replace_manager_ownership(
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    from dataclasses import replace

    from paper_radar.experiment import extraction
    from tests.experiment_extract_support import executor, extract_fixture

    fixture = extract_fixture(feed, tmp_path, monkeypatch)
    paths = extraction.RESOURCE_PATHS
    original = paths.user_scope_properties(fixture.group.name)
    if change == "uid":
        uid = extraction.RESOURCE_PATHS.current_uid()
        paths = replace(paths, current_uid=lambda: uid + 1)
    else:
        altered = (
            original.replace("ControlGroup=/user.slice", "ControlGroup=/other.slice")
            if change == "manager_group"
            else original.replace("active", "inactive")
            if change == "inactive"
            else original.replace("Transient=yes", "Transient=no")
            if change == "persistent"
            else original + "Id=duplicate.scope\n"
        )
        paths = replace(paths, user_scope_properties=lambda _: altered)
    monkeypatch.setattr(extraction, "RESOURCE_PATHS", paths)
    requests = executor(monkeypatch)
    result = fixture.extract()
    assert result.exit_code == 2, result.output
    assert "cgroup_limit_invalid" in result.output
    assert requests == []
    assert not (fixture.root.data_root / ".body-docling.lock").exists()


def test_new_report_freezes_source_section_and_restores_original_bytes(
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.experiment_read_support import read_fixture
    from tests.test_experiment_reports_cli import report

    fixture = read_fixture(feed, tmp_path, monkeypatch)
    result = fixture.read()
    assert result.exit_code == 0, result.output
    root = fixture.layout.extraction.root.root
    published = report(
        root,
        "render",
        "--date",
        "2026-11-14",
        "--timezone",
        "Asia/Shanghai",
        "--snapshot",
        fixture.snapshot,
    )
    assert published.exit_code == 0, published.output
    receipt = json.loads(published.stdout)
    path = root / "views" / receipt["relative_path"]
    original = path.read_bytes()
    assert b"renderer=2" in original
    assert b'"Results"' in original
    assert b'"sections"' in original
    from paper_radar.experiment.reports import ReportHistory

    (frozen,) = ReportHistory(root / "paper-radar.sqlite3", root / "data").history()
    sections = frozen.entries[0].basis["evidence_sections"]["e000002"]
    assert len(sections) == 1
    assert sections[0]["headings"] == ["Results"]
    assert sections[0]["state"] == "located" and sections[0]["reason"] is None
    assert (
        sections[0]["source_id"]
        == frozen.entries[0].basis["analysis"]["evidence"]["e000002"][0]["provenance"][
            "source_id"
        ]
    )
    path.unlink()
    rebuilt = report(root, "rebuild", receipt["report_id"])
    assert rebuilt.exit_code == 0, rebuilt.output
    assert path.read_bytes() == original
    # 模拟绕过追加保护并同步重算自洽哈希的离线篡改,来源核验仍须拒绝。
    import sqlite3

    from paper_radar.experiment.report_rendering import ReportInput, render
    from paper_radar.feed_metadata.repository import canonical, sha

    with sqlite3.connect(root / "paper-radar.sqlite3") as connection:
        connection.execute("DROP TRIGGER report_runs_publish_only")
        connection.execute("DROP TRIGGER report_entries_no_update")
        payload = json.loads(
            connection.execute("SELECT projection_json FROM report_runs").fetchone()[0]
        )
        payload["entries"][0]["basis"]["evidence_sections"]["e000002"][0][
            "headings"
        ] = ["FORGED_SECTION"]
        raw = canonical(payload)
        connection.execute(
            "UPDATE report_runs SET projection_json=?,input_fingerprint=?,"
            "content_sha256=?",
            (raw, sha(raw), sha(render(ReportInput.model_validate_json(raw)))),
        )
        connection.execute(
            "UPDATE report_entries SET projection_json=?",
            (canonical(payload["entries"][0]),),
        )
    refused = report(root, "verify", receipt["report_id"])
    assert refused.exit_code == 2 and "registration_invalid" in refused.output


@pytest.mark.parametrize(
    "case", ["no_heading", "unreliable_heading", "parent_hierarchy"]
)
def test_report_sections_follow_persisted_sources_without_guessing(
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    from paper_radar.experiment.reports import ReportHistory
    from tests.experiment_read_support import read_fixture
    from tests.test_experiment_reports_cli import report
    from tests.test_fulltext_artifacts import document

    original = document()
    heading, paragraph = original.blocks
    if case == "no_heading":
        canonical = original.model_copy(
            update={
                "blocks": (
                    heading.model_copy(update={"label": "text", "heading_level": None}),
                    paragraph,
                )
            }
        )
    elif case == "unreliable_heading":
        canonical = original.model_copy(
            update={
                "blocks": (heading.model_copy(update={"unreliable": True}), paragraph)
            }
        )
    else:
        canonical = original.model_copy(
            update={
                "blocks": (
                    heading,
                    paragraph.model_copy(update={"parent_ref": heading.ref}),
                )
            }
        )
    fixture = read_fixture(feed, tmp_path, monkeypatch, canonical=canonical)
    result = fixture.read()
    assert result.exit_code == 0, result.output
    root = fixture.layout.extraction.root.root
    published = report(
        root,
        "render",
        "--date",
        "2026-11-14",
        "--timezone",
        "Asia/Shanghai",
        "--snapshot",
        fixture.snapshot,
    )
    assert published.exit_code == 0, published.output
    (frozen,) = ReportHistory(root / "paper-radar.sqlite3", root / "data").history()
    (source,) = frozen.entries[0].basis["evidence_sections"]["e000002"]
    assert source["headings"] == (["Results"] if case == "parent_hierarchy" else [])
    assert source["reason"] == (
        None
        if case == "parent_hierarchy"
        else "unreliable_section_heading"
        if case == "unreliable_heading"
        else "no_persisted_section"
    )
    assert source["state"] == (
        "located" if case == "parent_hierarchy" else "unavailable"
    )


@pytest.mark.parametrize("new_failure", [True, False])
def test_report_metadata_health_uses_observed_time_not_request_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    new_failure: bool,
) -> None:
    from paper_radar.feed_metadata import JGRMetadata
    from paper_radar.fixture_audit.source_http import SourceHTTPExecutor
    from paper_radar.papers import PaperFacts
    from paper_radar.sources.feeds import endpoint
    from tests.feed_support import item
    from tests.test_experiment_candidates_cli import MAIN, invoke
    from tests.test_experiment_reports_cli import report

    root = tmp_path / "experiment"
    assert invoke("init", "--root", str(root)).exit_code == 0
    papers = PaperFacts(root / "paper-radar.sqlite3", root / "data")
    registered = papers.register_feed(endpoint("jgr"))
    saved = papers.submit(item(registered.feed_id, doi="10.1029/synthetic1"))
    assert saved.paper_id is not None
    paper = saved.paper_id
    # 请求键逆时间排序,明确击中旧实现的无序覆盖而不依赖随机 UUID。
    requests = sorted(
        (
            hashlib.sha256(
                json.dumps([paper, str(n)], separators=(",", ":")).encode()
            ).hexdigest(),
            str(n),
        )
        for n in range(8)
    )
    failing = not new_failure

    def respond(request: httpx.Request) -> httpx.Response:
        if failing:
            return httpx.Response(403)
        if "doiRA" in str(request.url):
            return httpx.Response(
                200, json=[{"DOI": "10.1029/synthetic1", "RA": "Crossref"}]
            )
        if request.url.host == "api.crossref.org":
            return httpx.Response(
                200,
                json={
                    "message": {
                        "DOI": "10.1029/synthetic1",
                        "title": ["Title"],
                        "abstract": MAIN,
                        "type": "journal-article",
                    }
                },
            )
        return httpx.Response(403)

    service = JGRMetadata(
        papers.database,
        root / "data",
        http=SourceHTTPExecutor(transport=httpx.MockTransport(respond)),
    )

    class Clock(datetime):
        current = datetime(2026, 11, 14, 1, tzinfo=UTC)

        @classmethod
        def now(cls, tz: tzinfo | None = None) -> "Clock":
            return cls.fromtimestamp(cls.current.timestamp(), tz)

    monkeypatch.setattr("paper_radar.feed_metadata.service.datetime", Clock)
    service.enrich(
        paper, request_id=requests[-1][1], contact_email="contact@example.org"
    )
    failing = new_failure
    Clock.current = datetime(2026, 11, 14, 2, tzinfo=UTC)
    service.enrich(
        paper, request_id=requests[0][1], contact_email="contact@example.org"
    )
    result = report(
        root, "render", "--date", "2026-11-14", "--timezone", "Asia/Shanghai"
    )
    assert result.exit_code == 0, result.output
    text = (root / "views" / json.loads(result.stdout)["relative_path"]).read_text()
    assert ("元数据不可得" in text) is new_failure


def test_trace_selection_history_is_paper_scoped_and_current_is_root_scoped(
    candidate: Candidate,
) -> None:
    root, view, check = candidate
    first = json.loads(select(root, view, "a", "--position", "1").stdout)
    second = json.loads(
        select(
            root,
            view,
            "b",
            "--position",
            "2",
            "--replaces",
            first["selection_id"],
            "--replacement-reason",
            "换样",
        ).stdout
    )

    def trace(paper_id: str) -> list[dict[str, object]]:
        result = CliRunner().invoke(
            app,
            [
                "paper",
                "trace",
                paper_id,
                "--database",
                str(root / "paper-radar.sqlite3"),
                "--data-root",
                str(root / "data"),
                "--workflow",
                "--json",
            ],
        )
        assert result.exit_code == 0, result.output
        return TypeAdapter(list[dict[str, object]]).validate_python(
            json.loads(result.stdout)["workflow"]["selections"]
        )

    a, b = (item["paper_id"] for item in check["items"])
    assert [(s["selection_id"], s["current"]) for s in trace(a)] == [
        (first["selection_id"], False)
    ]
    assert [(s["selection_id"], s["current"]) for s in trace(b)] == [
        (second["selection_id"], True)
    ]
    third = json.loads(
        select(
            root,
            view,
            "a-again",
            "--position",
            "1",
            "--replaces",
            second["selection_id"],
            "--replacement-reason",
            "换回",
        ).stdout
    )
    assert [(s["selection_id"], s["current"]) for s in trace(a)] == [
        (first["selection_id"], False),
        (third["selection_id"], True),
    ]
    assert [(s["selection_id"], s["current"]) for s in trace(b)] == [
        (second["selection_id"], False)
    ]
