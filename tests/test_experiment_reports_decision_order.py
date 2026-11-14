"""B-E14 独立 D1:后追加接受不因回退/相同墙钟改写旧pending报告。"""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import TypeAdapter
from typer.testing import CliRunner

from paper_radar.cli import app
from paper_radar.experiment.reports import Reports
from tests.experiment_screen_support import screen_fixture
from tests.test_experiment_accept_cli import accept
from tests.test_experiment_candidates_cli import FeedFixture
from tests.test_experiment_candidates_cli import feed as feed
from tests.test_experiment_reports_cli import report


@pytest.mark.parametrize("same_clock", [False, True])
def test_later_acceptance_preserves_pending_for_backward_or_equal_clock(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, same_clock: bool
) -> None:
    fixture = screen_fixture(feed, tmp_path, monkeypatch)
    screened = fixture.screen()
    assert screened.exit_code == 0, screened.output
    frozen_at = datetime(2099, 11, 14, tzinfo=UTC)
    service = Reports(
        fixture.root / "paper-radar.sqlite3",
        fixture.root / "data",
        fixture.root / "views",
        clock=lambda: frozen_at,
    )
    receipt = service.render(
        day="2099-11-14", timezone="UTC", snapshot_id=fixture.snapshot
    )
    members = TypeAdapter(list[dict[str, str]]).validate_python(receipt["members"])
    assert [m["primary_kind"] for m in members] == ["pending"]
    path = fixture.root / "views" / str(receipt["relative_path"])
    frozen = path.read_bytes()
    with monkeypatch.context() as clock:
        if same_clock:
            clock.setattr("paper_radar.body.service.now", lambda: frozen_at.isoformat())
        accepted = accept(fixture)
    assert accepted.exit_code == 0, accepted.output
    verified = report(fixture.root, "verify", str(receipt["report_id"]))
    assert verified.exit_code == 0, verified.output
    assert json.loads(verified.stdout) == receipt
    path.unlink()
    rebuilt = report(fixture.root, "rebuild", str(receipt["report_id"]))
    assert rebuilt.exit_code == 0, rebuilt.output
    assert path.read_bytes() == frozen
    backup = CliRunner().invoke(
        app,
        [
            "backup",
            "create",
            "--database",
            str(fixture.root / "paper-radar.sqlite3"),
            "--data-root",
            str(fixture.root / "data"),
            "--output",
            str(tmp_path / "backups"),
        ],
    )
    assert backup.exit_code == 0, backup.output


def test_acceptance_before_planning_cannot_be_forged_into_pending_by_clock(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sqlite3

    from paper_radar.experiment.report_rendering import render
    from paper_radar.feed_metadata.repository import canonical, sha

    fixture = screen_fixture(feed, tmp_path, monkeypatch)
    assert fixture.screen().exit_code == 0
    with monkeypatch.context() as clock:
        clock.setattr(
            "paper_radar.body.service.now", lambda: "2100-01-01T00:00:00+00:00"
        )
        accepted = accept(fixture)
    assert accepted.exit_code == 0, accepted.output
    database, data = fixture.root / "paper-radar.sqlite3", fixture.root / "data"
    service = Reports(
        database,
        data,
        fixture.root / "views",
        clock=lambda: datetime(2099, 11, 14, tzinfo=UTC),
    )
    receipt = service.render(
        day="2099-11-14", timezone="UTC", snapshot_id=fixture.snapshot
    )
    (inputs,) = service.history()
    (blocked,) = inputs.entries
    assert blocked.primary_kind == "blocked"
    success = blocked.supporting_success_id
    assert success is not None
    basis = dict(blocked.basis)
    basis.update(acceptance=None, fact=dict(kind="pending"))
    pending = blocked.model_copy(
        update=dict(
            primary_kind="pending",
            primary_ref=success,
            section="pending",
            first_publication_key=f"pending:{success}",
            basis=basis,
        )
    )
    from paper_radar.screening_tasks import ScreeningTasks

    timestamp = (
        ScreeningTasks(database, data)
        .load_success(success)
        .receipt.settled_at.isoformat()
    )
    pending = pending.model_copy(update=dict(available_at=timestamp))
    forged = inputs.model_copy(update=dict(entries=(pending,)))
    content = render(forged)
    payload = canonical(forged.model_dump(mode="json"))
    with sqlite3.connect(database) as connection:
        connection.execute("DROP TRIGGER report_entries_no_update")
        connection.execute("DROP TRIGGER report_runs_publish_only")
        connection.execute(
            "UPDATE report_entries SET primary_kind='pending', primary_ref=?, "
            "section='pending', first_publication_key=?, daily_first_key=?, "
            "projection_json=?",
            (
                success,
                f"pending:{success}",
                f"pending:{success}",
                canonical(pending.model_dump(mode="json")),
            ),
        )
        connection.execute(
            "UPDATE report_runs SET projection_json=?, "
            "input_fingerprint=?, content_sha256=?",
            (payload, sha(payload), sha(content)),
        )
    (fixture.root / "views" / str(receipt["relative_path"])).write_bytes(content)
    rejected = report(fixture.root, "verify", str(receipt["report_id"]))
    assert rejected.exit_code == 2 and "registration_invalid" in rejected.output


def test_acceptance_committed_before_report_write_lock_requires_replanning(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typing import Any

    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    from paper_radar.experiment.reports import ReportError

    fixture = screen_fixture(feed, tmp_path, monkeypatch)
    assert fixture.screen().exit_code == 0
    service = Reports(
        fixture.root / "paper-radar.sqlite3",
        fixture.root / "data",
        fixture.root / "views",
    )
    pending = True

    def accept_before_lock(
        connection: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        nonlocal pending
        if pending and statement.strip() == "BEGIN IMMEDIATE":
            pending = False
            actual = accept(fixture)
            assert actual.exit_code == 0, actual.output

    event.listen(Engine, "before_cursor_execute", accept_before_lock)
    try:
        with pytest.raises(ReportError) as error:
            service.render(
                day="2026-11-14", timezone="UTC", snapshot_id=fixture.snapshot
            )
        assert error.value.reason == "facts_changed"
    finally:
        event.remove(Engine, "before_cursor_execute", accept_before_lock)
    assert not pending
    assert service.history() == ()
    replanned = report(
        fixture.root,
        "render",
        "--date",
        "2026-11-14",
        "--timezone",
        "UTC",
        "--snapshot",
        fixture.snapshot,
    )
    assert replanned.exit_code == 0, replanned.output
    assert [m["primary_kind"] for m in json.loads(replanned.stdout)["members"]] == [
        "blocked"
    ]
