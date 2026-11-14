"""B-E7 独立 D1:显式两阶段 Screening 的产品 CLI。"""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.experiment_screen_support import screen_fixture
from tests.test_experiment_candidates_cli import FeedFixture, invoke
from tests.test_experiment_candidates_cli import feed as feed


def test_screen_rejects_missing_selection_before_external_preparation(
    tmp_path: Path,
) -> None:
    root = tmp_path / "experiment"
    assert invoke("init", "--root", str(root)).exit_code == 0
    result = invoke(
        "screen",
        "--root",
        str(root),
        "--selection-id",
        "unknown",
        "--snapshot",
        "unknown",
        "--credentials-dir",
        str(tmp_path / "credentials"),
        "--material-root",
        str(tmp_path / "materials"),
        "--install-root",
        str(tmp_path / "install"),
    )
    assert result.exit_code == 2, result.output
    assert "selection_changed" in result.output
    assert not (tmp_path / "credentials").exists()


def test_two_stages_use_authoritative_pi_rpc_and_replay_only_receipts(
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from paper_radar.body import BodyService
    from paper_radar.screening_tasks import ScreeningTasks

    prepared = screen_fixture(feed, tmp_path, monkeypatch)
    result = prepared.screen()
    assert result.exit_code == 0, result.output
    receipt = json.loads(result.stdout)
    assert receipt["state"] == "succeeded"
    assert receipt["boundary"]["attempts"] == 1
    assert receipt["value"]["attempts"] == 1
    tasks = ScreeningTasks(
        prepared.root / "paper-radar.sqlite3",
        prepared.root,
        clock=lambda: datetime.now(UTC),
    )
    for stage in ("boundary", "value"):
        successes = tasks.query_successes(
            paper_id=prepared.paper_id, stage=stage, snapshot_id=prepared.snapshot
        )
        assert len(successes) == 1
        assert (
            tasks.load_success(successes[0].receipt.success_id).receipt.executor_kind
            == "pi_rpc"
        )
    assert (
        tasks.language_basis(receipt["value"]["receipt"]["receipt_id"])[
            "original_title_is_zh"
        ]
        is False
    )
    assert BodyService(tasks.database, prepared.root).decisions(prepared.paper_id) == ()
    before = (prepared.credentials / "auth-observed.json").stat().st_mtime_ns
    replay = prepared.screen()
    assert replay.exit_code == 0, replay.output
    replayed = json.loads(replay.stdout)
    assert replayed["state"] == "replayed" and replayed["value"] is None
    assert replayed["boundary"]["receipt"] == receipt["boundary"]["receipt"]
    assert (prepared.credentials / "auth-observed.json").stat().st_mtime_ns == before
    entries = [
        json.loads(line)
        for line in (prepared.root / "logs/runtime.jsonl").read_text().splitlines()
    ]
    assert entries[-1]["event"] == "run_finished"
    assert entries[-1]["component"] == "experiment"
    assert len([row for row in entries if row["event"] == "claimed"]) == 2
    assert len([row for row in entries if row["event"] == "succeeded"]) == 2
    observed = (
        result.output
        + replay.output
        + (prepared.root / "logs/runtime.jsonl").read_text()
    )
    for secret in (
        "PRIVATE_",
        "oauth-test-only-sensitive-sentinel",
        "Frozen effective Pi system prompt",
        "论文研究天气过程",
    ):
        assert secret not in observed
    tasks.validate_all()


@pytest.mark.parametrize(
    "boundary,inferable,code,state",
    [
        ("out_of_scope", True, 3, "out_of_scope"),
        ("in_scope", False, 0, "succeeded"),
    ],
)
def test_boundary_stop_and_unknown_reuse_do_not_create_downstream_tasks(
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    boundary: str,
    inferable: bool,
    code: int,
    state: str,
) -> None:
    from paper_radar.body import BodyService
    from paper_radar.screening_tasks import ScreeningTasks

    prepared = screen_fixture(
        feed, tmp_path, monkeypatch, boundary=boundary, inferable=inferable
    )
    result = prepared.screen()
    assert result.exit_code == code, result.output
    receipt = json.loads(result.stdout)
    assert receipt["state"] == state
    tasks = ScreeningTasks(
        prepared.root / "paper-radar.sqlite3",
        prepared.root,
        clock=lambda: datetime.now(UTC),
    )
    value = tasks.query(
        paper_id=prepared.paper_id, stage="value", snapshot_id=prepared.snapshot
    )
    if boundary == "out_of_scope":
        assert value.budgets == () and receipt["value"] is None
    else:
        from paper_radar.screening.schema import ValuePredictionOutput

        content = tasks.load_success(receipt["value"]["success_id"])
        assert isinstance(content.output, ValuePredictionOutput)
        assert content.output.reuse_feasibility_inferable is False
    assert BodyService(tasks.database, prepared.root).decisions(prepared.paper_id) == ()
    from paper_radar.read_tasks import ReadTasks

    assert ReadTasks(tasks.database, prepared.root).history(prepared.paper_id) == ()


def test_two_failures_replay_and_a_b_a_preserve_original_budget(
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from paper_radar.screening_tasks import ScreeningTasks
    from tests.test_experiment_selection_cli import select

    prepared = screen_fixture(feed, tmp_path, monkeypatch, mode="output_invalid")
    failed = prepared.screen()
    assert failed.exit_code == 4, failed.output
    first = json.loads(failed.stdout)
    assert first["state"] == "budget_exhausted" and first["boundary"]["attempts"] == 2
    before = (prepared.credentials / "auth-observed.json").stat().st_mtime_ns
    replay = prepared.screen()
    assert replay.exit_code == 0 and json.loads(replay.stdout)["state"] == "replayed"
    b = select(
        prepared.root,
        prepared.view_id,
        "replace-b",
        "--position",
        "2",
        "--replaces",
        prepared.selection_id,
        "--replacement-reason",
        "换样",
    )
    assert b.exit_code == 0, b.output
    second = json.loads(b.stdout)
    a = select(
        prepared.root,
        prepared.view_id,
        "a-again",
        "--position",
        "1",
        "--replaces",
        second["selection_id"],
        "--replacement-reason",
        "换回原样本",
    )
    assert a.exit_code == 0, a.output
    returned = prepared.screen(selection_id=json.loads(a.stdout)["selection_id"])
    assert returned.exit_code == 4, returned.output
    receipt = json.loads(returned.stdout)
    assert (
        receipt["boundary"]["receipt"]["budget_id"]
        == first["boundary"]["receipt"]["budget_id"]
    )
    assert (
        receipt["boundary"]["receipt"]["task_id"]
        == first["boundary"]["receipt"]["task_id"]
    )
    assert receipt["boundary"]["attempts"] == 2
    assert (prepared.credentials / "auth-observed.json").stat().st_mtime_ns == before
    old = prepared.screen()
    assert old.exit_code == 0 and json.loads(old.stdout)["state"] == "replayed"
    tasks = ScreeningTasks(
        prepared.root / "paper-radar.sqlite3",
        prepared.root,
        clock=lambda: datetime.now(UTC),
    )
    query = tasks.query(
        paper_id=prepared.paper_id, stage="boundary", snapshot_id=prepared.snapshot
    )
    assert len(query.budgets) == 1 and len(query.budgets[0].tasks) == 1
    assert query.budgets[0].tasks[0].used_attempts == 2
    assert (
        tasks.query(
            paper_id=prepared.paper_id, stage="value", snapshot_id=prepared.snapshot
        ).budgets
        == ()
    )


@pytest.mark.parametrize(
    "change,reason",
    [
        ("selection", "selection_changed"),
        ("version", "frozen_version_changed"),
        ("egress", "egress_not_authorized"),
    ],
)
def test_inflight_boundary_settles_but_changed_authority_blocks_value(
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
    reason: str,
) -> None:
    from typing import Any

    from paper_radar.llm.rpc import run_call
    from paper_radar.llm.rpc_types import RpcCandidate, RpcFailure
    from paper_radar.papers import PaperFacts
    from paper_radar.screening_tasks import ScreeningTasks
    from tests.test_experiment_selection_cli import select

    prepared = screen_fixture(feed, tmp_path, monkeypatch)
    calls = 0

    def altered(*args: Any, **kwargs: Any) -> RpcCandidate | RpcFailure:
        nonlocal calls
        response = run_call(*args, **kwargs)
        calls += 1
        assert isinstance(response, RpcCandidate)
        if change == "selection":
            replaced = select(
                prepared.root,
                prepared.view_id,
                "race-replace",
                "--position",
                "2",
                "--replaces",
                prepared.selection_id,
                "--replacement-reason",
                "并发换样",
            )
            assert replaced.exit_code == 0, replaced.output
        elif change == "egress":
            assert prepared.egress(disabled=True).exit_code == 0
        else:
            papers = PaperFacts(prepared.root / "paper-radar.sqlite3", prepared.root)
            current = papers.show(prepared.paper_id)
            papers.correct(
                dict(
                    version_id=current.version_id,
                    request_id="changed",
                    reason="synthetic",
                    actor="owner",
                    fields={
                        "title": {
                            "value": "Updated synthetic title",
                            "locator": "manual/title",
                        }
                    },
                )
            )
        return response

    monkeypatch.setattr("paper_radar.pi_execution.service.run_call", altered)
    result = prepared.screen()
    assert result.exit_code == 2 and reason in result.output, result.output
    assert "corrupt_reference" not in result.output
    assert calls == 1
    tasks = ScreeningTasks(
        prepared.root / "paper-radar.sqlite3",
        prepared.root,
        clock=lambda: datetime.now(UTC),
    )
    boundary = tasks.query(
        paper_id=prepared.paper_id, stage="boundary", snapshot_id=prepared.snapshot
    )
    assert boundary.budgets[0].tasks[0].state == "succeeded"
    assert boundary.budgets[0].tasks[0].used_attempts == 1
    assert (
        tasks.query(
            paper_id=prepared.paper_id, stage="value", snapshot_id=prepared.snapshot
        ).budgets
        == ()
    )


@pytest.mark.parametrize(
    "change,reason",
    [
        ("selection", "selection_changed"),
        ("egress", "egress_not_authorized"),
        ("version", "facts_changed"),
    ],
)
def test_auth_to_claim_race_refuses_without_attempt_or_rpc(
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
    reason: str,
) -> None:
    from typing import Any

    from paper_radar.papers import PaperFacts
    from paper_radar.pi_execution.auth import credential_token
    from paper_radar.screening_tasks import ScreeningTasks
    from tests.test_experiment_selection_cli import select

    prepared = screen_fixture(feed, tmp_path, monkeypatch)
    calls = 0

    def changed(*args: Any, **kwargs: Any) -> str:
        nonlocal calls
        token = credential_token(*args, **kwargs)
        calls += 1
        if change == "selection":
            result = select(
                prepared.root,
                prepared.view_id,
                "claim-race",
                "--position",
                "2",
                "--replaces",
                prepared.selection_id,
                "--replacement-reason",
                "领取前换样",
            )
            assert result.exit_code == 0, result.output
        elif change == "egress":
            assert prepared.egress(disabled=True).exit_code == 0
        else:
            papers = PaperFacts(prepared.root / "paper-radar.sqlite3", prepared.root)
            current = papers.show(prepared.paper_id)
            papers.correct(
                dict(
                    version_id=current.version_id,
                    request_id="claim-race",
                    reason="synthetic",
                    actor="owner",
                    fields={
                        "title": {
                            "value": "Changed before claim",
                            "locator": "manual/title",
                        }
                    },
                )
            )
        return token

    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("unexpected RPC after authority changed")

    monkeypatch.setattr("paper_radar.pi_execution.launcher.credential_token", changed)
    monkeypatch.setattr("paper_radar.pi_execution.service.run_call", forbidden)
    result = prepared.screen()
    assert result.exit_code == 2 and reason in result.output, result.output
    assert "corrupt_reference" not in result.output and calls == 1
    tasks = ScreeningTasks(
        prepared.root / "paper-radar.sqlite3",
        prepared.root,
        clock=lambda: datetime.now(UTC),
    )
    query = tasks.query(
        paper_id=prepared.paper_id, stage="boundary", snapshot_id=prepared.snapshot
    )
    assert query.budgets[0].tasks[0].used_attempts == 0
    assert query.budgets[0].tasks[0].state == "ready"
    entries = [
        json.loads(line)
        for line in (prepared.root / "logs/runtime.jsonl").read_text().splitlines()
    ]
    assert all(row["event"] != "unexpected_error" for row in entries)
    assert entries[-1]["category"] == "controlled_failure"


@pytest.mark.parametrize(
    "interrupted,boundary,code",
    [
        (False, "in_scope", 0),
        (True, "in_scope", 0),
        (False, "out_of_scope", 3),
    ],
)
def test_explicit_receipt_recovers_ready_without_registration(
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    interrupted: bool,
    boundary: str,
    code: int,
) -> None:
    from paper_radar.screening_tasks import ScreeningTasks

    prepared = screen_fixture(feed, tmp_path, monkeypatch, boundary=boundary)
    auth = prepared.credentials / "auth.json"
    content = json.loads(auth.read_text())
    auth.write_text(json.dumps({**content, "mode": "failure"}))
    if interrupted:
        from paper_radar.pi_execution import launcher
        from paper_radar.pi_execution.auth import credential_token as real_auth

        def stop(*args: object, **kwargs: object) -> str:
            raise KeyboardInterrupt

        monkeypatch.setattr(launcher, "credential_token", stop)
    denied = prepared.screen()
    assert denied.exit_code == (130 if interrupted else 2), denied.output
    assert ("interrupted" if interrupted else "auth_failed") in denied.output
    if interrupted:
        monkeypatch.setattr(launcher, "credential_token", real_auth)
    tasks = ScreeningTasks(
        prepared.root / "paper-radar.sqlite3",
        prepared.root,
        clock=lambda: datetime.now(UTC),
    )
    query = tasks.query(
        paper_id=prepared.paper_id, stage="boundary", snapshot_id=prepared.snapshot
    )
    original = query.budgets[0].tasks[0].requests[0]
    assert tasks.status(original.receipt_id).used_attempts == 0
    auth.write_text(json.dumps(content))
    replay = prepared.screen()
    assert replay.exit_code == 0 and json.loads(replay.stdout)["state"] == "replayed"
    result = invoke(
        "screen",
        "--root",
        str(prepared.root),
        "--selection-id",
        prepared.selection_id,
        "--snapshot",
        prepared.snapshot,
        "--credentials-dir",
        str(prepared.credentials),
        "--material-root",
        str(prepared.materials),
        "--install-root",
        str(prepared.install),
        "--receipt-id",
        original.receipt_id,
    )
    assert result.exit_code == code, result.output
    receipt = json.loads(result.stdout)
    assert receipt["state"] == ("out_of_scope" if code == 3 else "succeeded")
    assert receipt["value"] is None
    assert receipt["boundary"]["receipt"]["receipt_id"] == original.receipt_id
    query = tasks.query(
        paper_id=prepared.paper_id, stage="boundary", snapshot_id=prepared.snapshot
    )
    assert len(query.budgets[0].tasks[0].requests) == 1
    assert (
        tasks.query(
            paper_id=prepared.paper_id, stage="value", snapshot_id=prepared.snapshot
        ).budgets
        == ()
    )


def test_explicit_value_retry_uses_production_feed_basis_and_only_its_generation(
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from paper_radar.screening_tasks import ScreeningTasks

    prepared = screen_fixture(feed, tmp_path, monkeypatch, mode="value_invalid")
    failed = prepared.screen()
    assert failed.exit_code == 4, failed.output
    saved = json.loads(failed.stdout)
    assert saved["boundary"]["state"] == "succeeded"
    assert saved["value"]["attempts"] == 2
    tasks = ScreeningTasks(
        prepared.root / "paper-radar.sqlite3",
        prepared.root,
        clock=lambda: datetime.now(UTC),
    )
    original = saved["value"]["receipt"]
    denied = prepared.screen(receipt_id=original["receipt_id"])
    assert denied.exit_code == 4 and "budget_exhausted" in denied.output
    successor = tasks.retry(
        dict(
            parent_task_id=original["task_id"],
            paper_id=prepared.paper_id,
            stage="value",
            snapshot_id=prepared.snapshot,
            request_id="explicit-value-retry",
            reason="所有者选择重试",
            actor="owner",
        )
    )
    (prepared.credentials / "auth.json").write_text(
        json.dumps(dict(token="synthetic-recovered-oauth"))
    )
    result = prepared.screen(receipt_id=successor.receipt_id)
    assert result.exit_code == 0, result.output
    receipt = json.loads(result.stdout)
    assert receipt["boundary"] is None and receipt["state"] == "succeeded"
    assert receipt["value"]["receipt"]["generation"] == 1
    assert receipt["value"]["attempts"] == 1
    assert (
        tasks.load_success(receipt["value"]["success_id"]).receipt.executor_kind
        == "pi_rpc"
    )
    replay = prepared.screen(receipt_id=successor.receipt_id)
    assert replay.exit_code == 2 and "already_succeeded" in replay.output
    stale = prepared.screen(receipt_id=original["receipt_id"])
    assert stale.exit_code == 2 and "not_latest" in stale.output


@pytest.mark.parametrize(
    "failure,reason",
    [
        ("egress", "egress_not_authorized"),
        ("waiver", "evidence_missing"),
        ("revision", "frozen_version_changed"),
    ],
)
def test_preconditions_refuse_before_authentication_and_without_budget(
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
    reason: str,
) -> None:
    from paper_radar.papers import PaperFacts
    from paper_radar.screening_tasks import ScreeningTasks
    from tests.test_owner_live_waiver import command as waiver

    prepared = screen_fixture(feed, tmp_path, monkeypatch)
    if failure == "egress":
        assert prepared.egress(disabled=True).exit_code == 0
    elif failure == "waiver":
        assert (
            waiver(
                prepared.root / "paper-radar.sqlite3",
                "--disable",
                "--reason",
                "恢复严格路径",
            ).exit_code
            == 0
        )
    else:
        papers = PaperFacts(prepared.root / "paper-radar.sqlite3", prepared.root)
        current = papers.show(prepared.paper_id)
        papers.correct(
            dict(
                version_id=current.version_id,
                request_id="precheck-change",
                reason="synthetic",
                actor="owner",
                fields={
                    "title": {
                        "value": "Changed selected basis",
                        "locator": "manual/title",
                    }
                },
            )
        )
    result = prepared.screen()
    assert result.exit_code == 2 and reason in result.output, result.output
    assert not (prepared.credentials / "auth-observed.json").exists()
    tasks = ScreeningTasks(
        prepared.root / "paper-radar.sqlite3",
        prepared.root,
        clock=lambda: datetime.now(UTC),
    )
    query = tasks.query(
        paper_id=prepared.paper_id, stage="boundary", snapshot_id=prepared.snapshot
    )
    assert all(
        task.used_attempts == 0 for budget in query.budgets for task in budget.tasks
    )


def test_screen_help_has_no_network_database_or_files(tmp_path: Path) -> None:
    import os
    import subprocess
    import sys

    result = subprocess.run(
        [
            str(Path(sys.executable).with_name("paper-radar")),
            "experiment",
            "screen",
            "--help",
        ],
        cwd=tmp_path,
        env={
            "PATH": os.environ["PATH"],
            "PYTHONPATH": str(Path(__file__).parent / "deny_external_io"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONIOENCODING": "utf-8",
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    for text in (
        "参数",
        "副作用",
        "自动配额",
        "输出去向",
        "常见失败",
        "示例",
        "--receipt-id",
        "130",
        "重放",
    ):
        assert text in result.stdout
    assert list(tmp_path.iterdir()) == []


def test_failed_budget_survives_backup_and_offline_subprocess_restore(
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import os
    import subprocess
    import sys

    from typer.testing import CliRunner

    from paper_radar.cli import app

    prepared = screen_fixture(feed, tmp_path, monkeypatch, mode="output_invalid")
    failed = prepared.screen()
    assert failed.exit_code == 4, failed.output
    receipt = json.loads(failed.stdout)["boundary"]["receipt"]
    backups = tmp_path / "backups"
    backup = CliRunner().invoke(
        app,
        [
            "backup",
            "create",
            "--database",
            str(prepared.root / "paper-radar.sqlite3"),
            "--data-root",
            str(prepared.root),
            "--output",
            str(backups),
        ],
    )
    assert backup.exit_code == 0, backup.output
    (batch,) = backups.iterdir()
    restored = tmp_path / "restored"
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run(
        [
            str(Path(sys.executable).with_name("paper-radar")),
            "restore",
            "verify",
            str(batch),
            "--target",
            str(restored),
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    prepared.root.rename(tmp_path / "original-unavailable")
    code = """
import json, socket, sys
from datetime import UTC, datetime
from pathlib import Path
from paper_radar.screening_tasks import ScreeningTasks
from paper_radar.experiment.selections import Selections
from paper_radar.experiment.validation import validate_all
def forbidden(*args, **kwargs):
    raise AssertionError("external call forbidden")
socket.socket = forbidden
root = Path(sys.argv[1])
database = root / "database.sqlite3"
validate_all(database, root)
tasks = ScreeningTasks(database, root, clock=lambda: datetime.now(UTC))
receipt = tasks.get_receipt(sys.argv[2])
status = tasks.status(receipt.receipt_id)
selection = Selections(database, root).history()[-1]
assert selection.paper_id == receipt.paper_id
print(json.dumps(dict(task=receipt.task_id, budget=receipt.budget_id,
    used=status.used_attempts, state=status.state, generation=receipt.generation)))
"""
    query = subprocess.run(
        [sys.executable, "-c", code, str(restored), receipt["receipt_id"]],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert query.returncode == 0, query.stdout + query.stderr
    assert json.loads(query.stdout) == dict(
        task=receipt["task_id"],
        budget=receipt["budget_id"],
        used=2,
        state="failed",
        generation=0,
    )
    assert "PRIVATE_" not in query.stdout + query.stderr


def test_test_boundary_success_is_never_promoted_by_screen(
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from paper_radar.screening_tasks import (
        ScreeningTasks,
        SuccessCandidate,
        SuccessReceipt,
    )

    prepared = screen_fixture(feed, tmp_path, monkeypatch)
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
            request_id="test-only-boundary",
            actor="owner",
            reason="合成test成功",
        )
    )
    result = tasks.run_once(
        registered.receipt_id,
        lambda stage, correction, renewal: SuccessCandidate(
            b'{"boundary":"in_scope","reason_zh":"Synthetic atmospheric study."}'
        ),
    )
    assert isinstance(result, SuccessReceipt)
    denied = prepared.screen()
    assert denied.exit_code == 2 and "test_source" in denied.output, denied.output
    assert not (prepared.credentials / "auth-observed.json").exists()
    assert (
        tasks.query(
            paper_id=prepared.paper_id, stage="value", snapshot_id=prepared.snapshot
        ).budgets
        == ()
    )
