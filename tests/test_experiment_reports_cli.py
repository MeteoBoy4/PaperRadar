"""B-E14 独立 D1:固定日报与单篇报告的 CLI 契约。"""

import html
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from paper_radar.cli import app
from tests.experiment_read_support import read_fixture
from tests.test_experiment_candidates_cli import FeedFixture
from tests.test_experiment_candidates_cli import feed as feed


def report(root: Path, command: str, *args: str) -> Result:
    return CliRunner().invoke(
        app, ["experiment", "report", command, "--root", str(root), *args]
    )


def test_empty_daily_is_fixed_and_rebuild_is_readonly(tmp_path: Path) -> None:
    root = tmp_path / "experiment"
    initialized = CliRunner().invoke(app, ["experiment", "init", "--root", str(root)])
    assert initialized.exit_code == 0, initialized.output
    first = report(
        root, "render", "--date", "2026-11-14", "--timezone", "Asia/Shanghai"
    )
    assert first.exit_code == 0, first.output
    receipt = json.loads(first.stdout)
    assert receipt["kind"] == "daily" and receipt["scope"] == "experiment"
    assert receipt["state"] == "published" and receipt["members"] == []
    path = root / "views" / receipt["relative_path"]
    frozen = path.read_bytes()
    text = frozen.decode()
    assert "无新结果" in text and "实验范围" in text and "无自动决定权" in text
    assert "Screening" in text and "Read" in text
    assert "not_assessed" in text and "unknown" in text and "下一步" in text
    repeated = report(
        root, "render", "--date", "2026-11-14", "--timezone", "Asia/Shanghai"
    )
    assert repeated.exit_code == 0 and json.loads(repeated.stdout) == receipt
    database = root / "paper-radar.sqlite3"
    stable_database = database.read_bytes()
    log = root / "logs/runtime.jsonl"
    stable_log = log.read_bytes()
    path.unlink()
    rebuilt = report(root, "rebuild", receipt["report_id"])
    assert rebuilt.exit_code == 0, rebuilt.output
    assert path.read_bytes() == frozen
    verified = report(root, "verify", receipt["report_id"])
    assert verified.exit_code == 0, verified.output
    assert database.read_bytes() == stable_database
    assert log.read_bytes() == stable_log


@pytest.fixture
def unsafe_titles(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    from tests.experiment_report_http_support import unsafe_title_transport

    return unsafe_title_transport(monkeypatch)


def test_successful_read_has_private_daily_and_independent_paper_report(
    unsafe_titles: dict[str, str],
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = read_fixture(feed, tmp_path, monkeypatch, mode="degrade")
    read = fixture.read()
    assert read.exit_code == 0, read.output
    analysis = json.loads(read.stdout)["task"]["analysis_id"]
    unsafe_titles["title"] = "CHANGED_CURRENT_TITLE"
    feed[2]("changed-before-first-report")
    root = fixture.layout.extraction.root.root
    options = (
        "--date",
        "2026-11-14",
        "--timezone",
        "Asia/Shanghai",
        "--snapshot",
        fixture.snapshot,
    )
    daily = report(root, "render", *options)
    assert daily.exit_code == 0, daily.output
    receipt = json.loads(daily.stdout)
    assert [m["primary_ref"] for m in receipt["members"]] == [analysis]
    text = (root / "views" / receipt["relative_path"]).read_text()
    for expected in (
        "PRIVATE_SYNTHETIC_TITLE",
        "PRIVATE_READ_CONCLUSION",
        "实验非决定支撑",
        "owner",
        "agent",
        "依预先选样授权代执行",
        "受限内容未核对",
        "main_findings",
        '"count": 1',
        "e000002",
        "bbox",
        "char_span",
        "pdf_sha256",
        "reading_sha256",
        "owner_evidence_prerequisite_waived",
        "original_state=unknown",
        "assessment=not_assessed",
        "historical_state_read=false",
        "evidence=unknown",
        "Screening",
        "Read",
        "下一步",
    ):
        assert expected in html.unescape(text), expected
    assert "CHANGED_CURRENT_TITLE" not in text
    assert "PRIVATE_DISCARDED" not in text
    assert "[PRIVATE_SYNTHETIC_TITLE](file:///PRIVATE_PATH)" not in text
    assert "&#91;PRIVATE&#95;SYNTHETIC&#95;TITLE&#93;" in text
    single = report(root, "render", *options, "--analysis-id", analysis)
    assert single.exit_code == 0, single.output
    paper = json.loads(single.stdout)
    assert paper["kind"] == "paper" and paper["report_id"] != receipt["report_id"]
    assert paper["members"] == receipt["members"]
    tomorrow = report(
        root, "render", "--date", "2026-11-15", "--timezone", "Asia/Shanghai"
    )
    assert tomorrow.exit_code == 0 and json.loads(tomorrow.stdout)["members"] == []
    log = (root / "logs/runtime.jsonl").read_text()
    for secret in (
        "PRIVATE_READ_CONCLUSION",
        "PRIVATE_READ_PROMPT",
        "PRIVATE_SYNTHETIC_TITLE",
        "oauth-test-only-sensitive-sentinel",
    ):
        assert secret not in log and secret not in daily.stdout


def test_pending_and_needs_pdf_are_independent_first_publication_facts(
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.experiment_screen_support import screen_fixture
    from tests.test_experiment_accept_cli import accept

    fixture = screen_fixture(feed, tmp_path, monkeypatch)
    screened = fixture.screen()
    assert screened.exit_code == 0, screened.output
    options = ("--timezone", "Asia/Shanghai", "--snapshot", fixture.snapshot)
    pending = report(fixture.root, "render", "--date", "2026-11-14", *options)
    assert pending.exit_code == 0, pending.output
    original = json.loads(pending.stdout)
    assert [m["primary_kind"] for m in original["members"]] == ["pending"]
    assert accept(fixture).exit_code == 0
    stable = report(fixture.root, "render", "--date", "2026-11-14", *options)
    assert json.loads(stable.stdout) == original
    blocked = report(fixture.root, "render", "--date", "2026-11-15", *options)
    assert blocked.exit_code == 0, blocked.output
    members = json.loads(blocked.stdout)["members"]
    assert [m["primary_kind"] for m in members] == ["blocked"]
    assert (
        members[0]["first_publication_key"]
        != original["members"][0]["first_publication_key"]
    )
    empty = report(fixture.root, "render", "--date", "2026-11-16", *options)
    assert empty.exit_code == 0 and json.loads(empty.stdout)["members"] == []


def test_fault_empty_daily_discloses_metadata_failure_instead_of_no_new_results(
    feed: FeedFixture,
) -> None:
    root, state, fetch = feed
    state["missing"] = True
    fetch("missing")
    result = report(
        root, "render", "--date", "2026-11-14", "--timezone", "Asia/Shanghai"
    )
    assert result.exit_code == 0, result.output
    receipt = json.loads(result.stdout)
    text = (root / "views" / receipt["relative_path"]).read_text()
    assert receipt["members"] == []
    assert "因故障没有结果" in text and "元数据" in text
    assert "Screening" in text and "Read" in text and "not_assessed" in text
    assert "无新结果。" not in text


@pytest.mark.parametrize("command", [(), ("render",), ("rebuild",), ("verify",)])
def test_report_help_is_cold_and_complete(
    tmp_path: Path, command: tuple[str, ...]
) -> None:
    from tests.config_test_support import run_cli

    result = run_cli(
        tmp_path, "experiment", "report", *command, "--help", help_only=True
    )
    assert result.returncode == 0, result.stderr
    for text in ("参数", "副作用", "自动配额", "输出去向", "常见失败", "示例", "130"):
        assert text in result.stdout, text
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "day,timezone",
    [("2026-11-31", "UTC"), ("../private", "UTC"), ("2026-11-14", "../private")],
)
def test_dates_and_timezone_are_controlled_without_leaking_arguments(
    tmp_path: Path, day: str, timezone: str
) -> None:
    root = tmp_path / "experiment"
    assert (
        CliRunner().invoke(app, ["experiment", "init", "--root", str(root)]).exit_code
        == 0
    )
    result = report(root, "render", "--date", day, "--timezone", timezone)
    assert result.exit_code == 2 and "invalid_date_timezone" in result.output
    assert "../private" not in result.output
    assert list((root / "views").iterdir()) == []


@pytest.mark.parametrize(
    "arguments",
    [("PRIVATE_ARGUMENT",), ("--PRIVATE_ARGUMENT",), ("render", "--PRIVATE_ARGUMENT")],
)
def test_report_group_argument_errors_never_echo_private_text(
    tmp_path: Path, arguments: tuple[str, ...]
) -> None:
    result = CliRunner().invoke(app, ["experiment", "report", *arguments])
    assert result.exit_code == 2
    assert "PRIVATE_ARGUMENT" not in result.output
    assert "--help" in result.output
    assert list(tmp_path.iterdir()) == []
