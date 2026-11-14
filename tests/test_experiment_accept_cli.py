"""B-E9 独立 D1:预先选样授权的显式代执行接受。"""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from paper_radar.cli import app
from tests.experiment_screen_support import ScreenFixture, screen_fixture
from tests.test_experiment_candidates_cli import FeedFixture, invoke
from tests.test_experiment_candidates_cli import feed as feed


def accept(prepared: ScreenFixture, *, request: str = "accept-1") -> Result:
    return invoke(
        "accept",
        prepared.paper_id,
        "--root",
        str(prepared.root),
        "--selection-id",
        prepared.selection_id,
        "--snapshot",
        prepared.snapshot,
        "--request-id",
        request,
    )


def test_accept_is_delegated_atomic_and_replayed_in_safe_trace(
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from paper_radar.body import BodyService

    prepared = screen_fixture(feed, tmp_path, monkeypatch)
    screened = prepared.screen()
    assert screened.exit_code == 0, screened.output
    stages = json.loads(screened.stdout)
    result = accept(prepared)
    assert result.exit_code == 0, result.output
    receipt = json.loads(result.stdout)
    log_path = prepared.root / "logs/runtime.jsonl"
    events_logged = [json.loads(line) for line in log_path.read_text().splitlines()]
    assert [entry["event"] for entry in events_logged[-2:]] == [
        "run_started",
        "run_finished",
    ]
    assert all(entry["component"] == "experiment" for entry in events_logged[-2:])
    assert receipt["authorizer"] == "owner" and receipt["actor"] == "agent"
    assert receipt["explanation"] == "依预先选样授权代执行"
    assert receipt["boundary_success_id"] == stages["boundary"]["success_id"]
    assert receipt["value_success_id"] == stages["value"]["success_id"]
    replay = accept(prepared)
    assert replay.exit_code == 0, replay.output
    assert json.loads(replay.stdout) == {**receipt, "replayed": True}
    logged_before_query = log_path.read_bytes()
    events = BodyService(
        prepared.root / "paper-radar.sqlite3", prepared.root
    ).decisions(prepared.paper_id)
    assert len(events) == 1
    assert events[0].fact.reference == receipt["decision_id"]
    assert events[0].fact.record.model_dump(mode="json") == dict(
        result="accepted", source="direct_manual_decision", reason="user_judgment"
    )
    trace = CliRunner().invoke(
        app,
        [
            "paper",
            "trace",
            prepared.paper_id,
            "--database",
            str(prepared.root / "paper-radar.sqlite3"),
            "--data-root",
            str(prepared.root),
            "--snapshot",
            prepared.snapshot,
            "--json",
        ],
    )
    assert trace.exit_code == 0, trace.output
    workflow = json.loads(trace.stdout)["workflow"]
    assert workflow["delegated_acceptances"][0]["decision_id"] == receipt["decision_id"]
    assert "projection" not in workflow
    expanded = CliRunner().invoke(
        app,
        [
            "paper",
            "trace",
            prepared.paper_id,
            "--database",
            str(prepared.root / "paper-radar.sqlite3"),
            "--data-root",
            str(prepared.root),
            "--snapshot",
            prepared.snapshot,
            "--json",
            "--show-agent-content",
            "--show-abstract",
        ],
    )
    assert expanded.exit_code == 0, expanded.output
    assert "论文研究天气过程" in expanded.output
    assert "PRIVATE_SYNTHETIC_ABSTRACT" in expanded.output
    assert log_path.read_bytes() == logged_before_query
    observed = (
        result.output
        + replay.output
        + trace.output
        + (prepared.root / "logs/runtime.jsonl").read_text()
    )
    for secret in (
        "PRIVATE_SYNTHETIC_ABSTRACT",
        "PRIVATE_EGRESS_REASON",
        "oauth-test-only-sensitive-sentinel",
        "论文研究天气过程",
    ):
        assert secret not in observed


@pytest.mark.parametrize(
    "case,reason",
    [
        ("boundary_missing", "boundary_missing"),
        ("value_missing", "value_missing"),
        ("out_of_scope", "out_of_scope"),
        ("changed", "frozen_version_changed"),
        ("replaced", "selection_changed"),
        ("mismatch", "selection_mismatch"),
    ],
)
def test_accept_rejects_ineligible_basis_without_decision(
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    reason: str,
) -> None:
    from dataclasses import replace

    from paper_radar.body import BodyService
    from paper_radar.papers import PaperFacts
    from tests.test_experiment_selection_cli import select

    prepared = screen_fixture(
        feed,
        tmp_path,
        monkeypatch,
        mode="value_invalid" if case == "value_missing" else "normal",
        boundary="out_of_scope" if case == "out_of_scope" else "in_scope",
    )
    if case not in {"boundary_missing", "mismatch"}:
        screened = prepared.screen()
        assert screened.exit_code == {"value_missing": 4, "out_of_scope": 3}.get(
            case, 0
        ), screened.output
    if case == "changed":
        papers = PaperFacts(prepared.root / "paper-radar.sqlite3", prepared.root)
        original = papers.show(prepared.paper_id)
        corrected = papers.correct(
            dict(
                version_id=original.version_id,
                request_id="new-revision",
                actor="owner",
                reason="synthetic",
                fields={"title": {"value": "New title", "locator": "manual/title"}},
            )
        )
        assert corrected.status == "retained"
    if case == "replaced":
        replaced = select(
            prepared.root,
            prepared.view_id,
            "replace",
            "--position",
            "2",
            "--replaces",
            prepared.selection_id,
            "--replacement-reason",
            "所有者换样",
        )
        assert replaced.exit_code == 0, replaced.output
    if case == "mismatch":
        prepared = replace(prepared, paper_id="different-paper")
    result = accept(prepared)
    assert result.exit_code == 2 and reason in result.output, result.output
    if case != "mismatch":
        assert (
            BodyService(prepared.root / "paper-radar.sqlite3", prepared.root).decisions(
                prepared.paper_id
            )
            == ()
        )


def test_accept_help_is_cold_and_complete(tmp_path: Path) -> None:
    from tests.config_test_support import run_cli

    result = run_cli(tmp_path, "experiment", "accept", "--help", help_only=True)
    assert result.returncode == 0, result.stderr
    for text in (
        "参数",
        "副作用",
        "自动配额",
        "输出去向",
        "常见失败",
        "示例",
        "130",
        "accepted",
    ):
        assert text in result.stdout
    assert list(tmp_path.iterdir()) == []


def test_test_success_source_never_authorizes_delegated_acceptance(
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import UTC, datetime

    from paper_radar.body import BodyService
    from paper_radar.screening_tasks import (
        ScreeningTasks,
        SuccessCandidate,
        SuccessReceipt,
    )

    prepared = screen_fixture(feed, tmp_path, monkeypatch)
    # 公共 A7 test 接收器注入不适合生产消费的成功,断言仍走产品 CLI。
    tasks = ScreeningTasks(
        prepared.root / "paper-radar.sqlite3",
        prepared.root,
        clock=lambda: datetime.now(UTC),
    )
    registered = tasks.register(
        dict(
            paper_id=prepared.paper_id,
            snapshot_id=prepared.snapshot,
            stage="boundary",
            source="manual",
            request_id="synthetic-test-source",
            reason="synthetic",
            actor="agent",
        )
    )
    success = tasks.submit(
        tasks.claim(registered.receipt_id),
        SuccessCandidate(
            b'{"boundary":"in_scope","reason_zh":"Synthetic test output only."}'
        ),
    )
    assert isinstance(success, SuccessReceipt)
    result = accept(prepared)
    assert result.exit_code == 2 and "test_source" in result.output, result.output
    assert BodyService(tasks.database, prepared.root).decisions(prepared.paper_id) == ()


def test_low_experimental_prediction_does_not_veto_preselection(
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import UTC, datetime

    from paper_radar.screening.schema import ValuePredictionOutput
    from paper_radar.screening_tasks import ScreeningTasks
    from tests.pi_execution_support import PeerRun

    def low_peer(peer: str) -> PeerRun:
        return PeerRun(
            peer.replace('"research_value":4', '"research_value":1').replace(
                '"reuse_feasibility":3', '"reuse_feasibility":1'
            )
        )

    monkeypatch.setattr("tests.experiment_screen_support.PeerRun", low_peer)
    prepared = screen_fixture(feed, tmp_path, monkeypatch)
    screened = prepared.screen()
    assert screened.exit_code == 0, screened.output
    tasks = ScreeningTasks(
        prepared.root / "paper-radar.sqlite3",
        prepared.root,
        clock=lambda: datetime.now(UTC),
    )
    output = tasks.load_success(
        json.loads(screened.stdout)["value"]["success_id"]
    ).output
    assert isinstance(output, ValuePredictionOutput)
    assert output.research_value == 1 and output.reuse_feasibility == 1
    accepted = accept(prepared)
    assert accepted.exit_code == 0, accepted.output


def test_request_conflict_duplicate_selection_and_historical_replay(
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dataclasses import replace

    from tests.test_experiment_selection_cli import select

    prepared = screen_fixture(feed, tmp_path, monkeypatch)
    assert prepared.screen().exit_code == 0
    first = accept(prepared)
    assert first.exit_code == 0, first.output
    conflict = accept(replace(prepared, paper_id="other-paper"))
    assert conflict.exit_code == 2 and "request_conflict" in conflict.output
    duplicate = accept(prepared, request="different-request")
    assert duplicate.exit_code == 2 and "already_accepted" in duplicate.output
    replaced = select(
        prepared.root,
        prepared.view_id,
        "replace",
        "--position",
        "2",
        "--replaces",
        prepared.selection_id,
        "--replacement-reason",
        "换样保留旧决定",
    )
    assert replaced.exit_code == 0, replaced.output
    replayed = accept(prepared)
    assert replayed.exit_code == 0, replayed.output
    assert json.loads(replayed.stdout) == {**json.loads(first.stdout), "replayed": True}


@pytest.mark.parametrize(
    "stop",
    ["INSERT INTO body_decision_screenings", "INSERT INTO experiment_acceptances"],
)
def test_acceptance_fault_rolls_back_decision_and_association(
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stop: str,
) -> None:
    from paper_radar.body import BodyService
    from paper_radar.experiment.acceptance import Acceptances
    from tests.artifact_support import fail_sql

    prepared = screen_fixture(feed, tmp_path, monkeypatch)
    assert prepared.screen().exit_code == 0
    with fail_sql(stop):
        failed = accept(prepared)
    assert failed.exit_code == 2, failed.output
    assert "execution_failed" in failed.output or "database_failed" in failed.output
    database = prepared.root / "paper-radar.sqlite3"
    assert BodyService(database, prepared.root).decisions(prepared.paper_id) == ()
    assert Acceptances(database, prepared.root).history() == ()
    retried = accept(prepared)
    assert retried.exit_code == 0, retried.output


@pytest.mark.parametrize("when", [1, 2])
def test_visibility_is_checked_before_prevalidation_and_inside_write(
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    when: int,
) -> None:
    from paper_radar.body import BodyService
    from paper_radar.calibration import visibility

    prepared = screen_fixture(feed, tmp_path, monkeypatch)
    assert prepared.screen().exit_code == 0
    original = visibility.evaluate_visibility
    calls = 0

    def hide(hidden: frozenset[visibility.HiddenCondition]) -> visibility.Visibility:
        nonlocal calls
        calls += 1
        return original(
            frozenset({visibility.HiddenCondition.UNREVEALED})
            if calls >= when
            else hidden
        )

    monkeypatch.setattr(visibility, "evaluate_visibility", hide)
    refused = accept(prepared)
    assert refused.exit_code == 2 and "visibility_denied" in refused.output
    assert calls == when
    assert (
        BodyService(prepared.root / "paper-radar.sqlite3", prepared.root).decisions(
            prepared.paper_id
        )
        == ()
    )


@pytest.mark.parametrize(
    "change,reason",
    [("selection", "selection_changed"), ("revision", "frozen_version_changed")],
)
def test_short_transaction_rechecks_after_full_success_prevalidation(
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
    reason: str,
) -> None:
    from paper_radar.body import BodyService
    from paper_radar.papers import PaperFacts
    from paper_radar.screening_tasks import ScreeningTasks
    from paper_radar.screening_tasks.success_models import SuccessContent
    from tests.test_experiment_selection_cli import select

    prepared = screen_fixture(feed, tmp_path, monkeypatch)
    assert prepared.screen().exit_code == 0
    original = ScreeningTasks.load_success
    changed = False

    def raced(service: ScreeningTasks, success_id: str) -> SuccessContent:
        nonlocal changed
        content = original(service, success_id)
        if content.receipt.stage == "value" and not changed:
            changed = True
            if change == "selection":
                result = select(
                    prepared.root,
                    prepared.view_id,
                    "raced-replace",
                    "--position",
                    "2",
                    "--replaces",
                    prepared.selection_id,
                    "--replacement-reason",
                    "并发换样",
                )
                assert result.exit_code == 0, result.output
            else:
                papers = PaperFacts(service.database, prepared.root)
                revision = papers.show(prepared.paper_id)
                result_correction = papers.correct(
                    dict(
                        version_id=revision.version_id,
                        request_id="raced-revision",
                        actor="owner",
                        reason="synthetic",
                        fields={
                            "title": {
                                "value": "Changed after successful prevalidation",
                                "locator": "manual/title",
                            }
                        },
                    )
                )
                assert result_correction.status == "retained"
        return content

    monkeypatch.setattr(ScreeningTasks, "load_success", raced)
    refused = accept(prepared)
    assert refused.exit_code == 2 and reason in refused.output, refused.output
    assert changed
    assert (
        BodyService(prepared.root / "paper-radar.sqlite3", prepared.root).decisions(
            prepared.paper_id
        )
        == ()
    )


def test_concurrent_same_request_commits_one_delegated_decision(
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from paper_radar.body import BodyService
    from paper_radar.experiment.acceptance import Acceptances, DelegatedAcceptance
    from paper_radar.experiment.root import ExperimentRoot
    from paper_radar.screening_tasks import ScreeningTasks
    from paper_radar.screening_tasks.success_models import SuccessContent

    prepared = screen_fixture(feed, tmp_path, monkeypatch)
    assert prepared.screen().exit_code == 0
    original = ScreeningTasks.load_success
    barrier = Barrier(2)

    def synchronized(service: ScreeningTasks, success_id: str) -> SuccessContent:
        result = original(service, success_id)
        if result.receipt.stage == "value":
            barrier.wait(timeout=15)
        return result

    monkeypatch.setattr(ScreeningTasks, "load_success", synchronized)
    root = ExperimentRoot(prepared.root)

    def run() -> tuple[DelegatedAcceptance, bool]:
        return Acceptances(root.database, root.data_root).accept(
            root,
            paper_id=prepared.paper_id,
            selection_id=prepared.selection_id,
            snapshot=prepared.snapshot,
            request_id="concurrent",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.submit(run), pool.submit(run)
        a, b = first.result(timeout=30), second.result(timeout=30)
    monkeypatch.setattr(ScreeningTasks, "load_success", original)
    assert a[0] == b[0] and sorted([a[1], b[1]]) == [False, True]
    assert (
        len(BodyService(root.database, root.data_root).decisions(prepared.paper_id))
        == 1
    )
    assert Acceptances(root.database, root.data_root).history() == (a[0],)


def test_backup_restore_keeps_delegated_acceptance_without_original_roots(
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import os
    import subprocess
    import sys

    prepared = screen_fixture(feed, tmp_path, monkeypatch)
    assert prepared.screen().exit_code == 0
    accepted = accept(prepared)
    assert accepted.exit_code == 0, accepted.output
    database = prepared.root / "paper-radar.sqlite3"
    before = CliRunner().invoke(
        app,
        [
            "paper",
            "trace",
            prepared.paper_id,
            "--database",
            str(database),
            "--data-root",
            str(prepared.root),
            "--snapshot",
            prepared.snapshot,
            "--json",
        ],
    )
    assert before.exit_code == 0, before.output
    output = tmp_path / "backups"
    backup = CliRunner().invoke(
        app,
        [
            "backup",
            "create",
            "--database",
            str(database),
            "--data-root",
            str(prepared.root),
            "--output",
            str(output),
        ],
    )
    assert backup.exit_code == 0, backup.output
    (batch,) = output.iterdir()
    restored = tmp_path / "restored"
    restore = subprocess.run(
        [
            str(Path(sys.executable).with_name("paper-radar")),
            "restore",
            "verify",
            str(batch),
            "--target",
            str(restored),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert restore.returncode == 0, restore.stdout + restore.stderr
    for path in (
        prepared.root,
        prepared.credentials,
        prepared.install,
        prepared.materials,
    ):
        if path.exists():
            path.rename(path.with_name(path.name + "-unavailable"))
        assert not path.exists()
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.experiment_accept_recovery_worker",
            str(restored),
            prepared.paper_id,
            prepared.snapshot,
        ],
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 0, process.stdout + process.stderr
    assert json.loads(process.stdout) == json.loads(before.stdout)
    assert json.loads(process.stdout)["workflow"]["delegated_acceptances"] == [
        json.loads(accepted.stdout)
    ]
    assert "oauth-test-only-sensitive-sentinel" not in process.stdout + process.stderr


@pytest.mark.parametrize("corruption", ["missing_association", "changed_record"])
def test_backup_closure_rejects_corrupted_or_missing_delegation(
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    corruption: str,
) -> None:
    import sqlite3

    prepared = screen_fixture(feed, tmp_path, monkeypatch)
    assert prepared.screen().exit_code == 0
    assert accept(prepared).exit_code == 0
    database = prepared.root / "paper-radar.sqlite3"
    # 故障注入绕过只追加保护;不把这种写法用于产品动作。
    with sqlite3.connect(database) as connection:
        if corruption == "missing_association":
            connection.execute("DROP TRIGGER experiment_acceptances_no_delete")
            connection.execute("DELETE FROM experiment_acceptances")
        else:
            connection.execute("DROP TRIGGER experiment_acceptances_no_update")
            connection.execute("UPDATE experiment_acceptances SET record_json='{}'")
    backup = CliRunner().invoke(
        app,
        [
            "backup",
            "create",
            "--database",
            str(database),
            "--data-root",
            str(prepared.root),
            "--output",
            str(tmp_path / "backups"),
        ],
    )
    assert backup.exit_code != 0 and "registration_invalid" in backup.output, (
        backup.output
    )


@pytest.mark.parametrize("failure", ["commit", "interrupt"])
def test_commit_failure_and_interrupt_leave_no_partial_acceptance(
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    from sqlalchemy import Connection, Engine, event

    from paper_radar.body import BodyService
    from paper_radar.experiment.acceptance import Acceptances

    prepared = screen_fixture(feed, tmp_path, monkeypatch)
    assert prepared.screen().exit_code == 0

    def failed_commit(connection: Connection) -> None:
        raise OSError("PRIVATE_SYNTHETIC_COMMIT_FAILURE")

    def interrupted(
        connection: Connection,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        if statement.startswith("INSERT INTO experiment_acceptances"):
            raise KeyboardInterrupt

    if failure == "commit":
        event.listen(Engine, "commit", failed_commit)
    else:
        event.listen(Engine, "before_cursor_execute", interrupted)
    try:
        failed = accept(prepared)
    finally:
        if failure == "commit":
            event.remove(Engine, "commit", failed_commit)
        else:
            event.remove(Engine, "before_cursor_execute", interrupted)
    assert failed.exit_code == (2 if failure == "commit" else 130), failed.output
    assert (
        "execution_failed" if failure == "commit" else "interrupted"
    ) in failed.output
    assert "PRIVATE_SYNTHETIC_COMMIT_FAILURE" not in failed.output
    database = prepared.root / "paper-radar.sqlite3"
    assert BodyService(database, prepared.root).decisions(prepared.paper_id) == ()
    assert Acceptances(database, prepared.root).history() == ()


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE experiment_acceptances SET request_id='changed'",
        "DELETE FROM experiment_acceptances",
        "INSERT OR REPLACE INTO experiment_acceptances "
        "SELECT * FROM experiment_acceptances",
    ],
)
def test_delegation_association_is_append_only(
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    statement: str,
) -> None:
    import sqlite3

    from paper_radar.experiment.acceptance import Acceptances

    prepared = screen_fixture(feed, tmp_path, monkeypatch)
    assert prepared.screen().exit_code == 0
    assert accept(prepared).exit_code == 0
    database = prepared.root / "paper-radar.sqlite3"
    service = Acceptances(database, prepared.root)
    before = service.history()
    with (
        sqlite3.connect(database) as connection,
        pytest.raises(sqlite3.IntegrityError, match="append_only"),
    ):
        connection.execute(statement)
    assert service.history() == before


def test_history_does_not_mix_authorization_and_acceptance_read_snapshots(
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sqlalchemy import Connection

    from paper_radar.experiment.acceptance import Acceptances
    from paper_radar.experiment.root import ExperimentRoot
    from paper_radar.experiment.selections import SelectionRecord, Selections
    from tests.test_experiment_selection_cli import select

    prepared = screen_fixture(feed, tmp_path, monkeypatch)
    assert prepared.screen().exit_code == 0
    root = ExperimentRoot(prepared.root)
    original = Selections.history_in_connection
    changed = False

    def raced(
        service: Selections, connection: Connection
    ) -> tuple[SelectionRecord, ...]:
        nonlocal changed
        before = original(service, connection)
        if not changed:
            changed = True
            selection = select(
                prepared.root,
                prepared.view_id,
                "concurrent-authorization",
                "--position",
                "1",
                "--replaces",
                prepared.selection_id,
                "--replacement-reason",
                "重新授权同一样本",
            )
            assert selection.exit_code == 0, selection.output
            Acceptances(root.database, root.data_root).accept(
                root,
                paper_id=prepared.paper_id,
                selection_id=json.loads(selection.stdout)["selection_id"],
                snapshot=prepared.snapshot,
                request_id="concurrent-acceptance",
            )
        return before

    monkeypatch.setattr(Selections, "history_in_connection", raced)
    assert Acceptances(root.database, root.data_root).history() == ()
    assert changed
    monkeypatch.setattr(Selections, "history_in_connection", original)
    assert len(Acceptances(root.database, root.data_root).history()) == 1
