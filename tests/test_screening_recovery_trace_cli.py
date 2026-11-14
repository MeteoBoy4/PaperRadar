"""B-E8 独立 D1:失败队列、显式恢复与安全组合追踪。"""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from paper_radar.cli import app
from paper_radar.screening_tasks import FailureKind, FailureReport, ScreeningTasks
from tests.a7_registration_support import archive, request_for
from tests.test_experiment_candidates_cli import FeedFixture
from tests.test_experiment_candidates_cli import feed as feed


def cli(*args: str) -> Result:
    return CliRunner().invoke(app, list(args))


def test_failure_queue_and_explicit_retry_replay(tmp_path: Path) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(
        data.database, data.data_root, clock=lambda: datetime.now(UTC)
    )
    receipt = tasks.register(request_for(data))
    common = ["--database", str(data.database), "--snapshot", data.snapshot_id]
    for attempt in range(2):
        tasks.fail(tasks.claim(receipt.receipt_id), FailureReport(FailureKind.TIMEOUT))
        result = cli("screening", "failures", *common)
        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert len(payload["failures"]) == attempt
    failed = payload["failures"][0]
    assert failed["paper_id"] == data.paper_id
    assert failed["task"]["task_id"] == receipt.task_id
    retry = [
        "screening",
        "retry",
        data.paper_id,
        *common,
        "--request-id",
        "retry-1",
        "--reason",
        "PRIVATE_REASON",
        "--actor",
        "PRIVATE_ACTOR",
    ]
    result = cli(*retry)
    assert result.exit_code == 0, result.output
    successor = json.loads(result.stdout)
    assert successor["generation"] == 1
    assert tasks.status(successor["receipt_id"]).used_attempts == 0
    assert json.loads(cli(*retry).stdout) == successor
    refused = cli(*retry[:-1], "changed")
    assert refused.exit_code == 2 and "request_conflict" in refused.output
    assert "PRIVATE_" not in result.output
    assert json.loads(cli("screening", "failures", *common).stdout)["failures"] == []


def test_trace_combines_safe_tasks_shared_eligibility_and_explicit_abstract(
    tmp_path: Path,
) -> None:
    from paper_radar.calibration import visibility
    from paper_radar.eligibility import Concept, evaluate_paper
    from paper_radar.paper_trace import query_paper_trace

    data = archive(tmp_path)
    tasks = ScreeningTasks(
        data.database, data.data_root, clock=lambda: datetime.now(UTC)
    )
    receipt = tasks.register(request_for(data))
    for _ in range(2):
        tasks.fail(tasks.claim(receipt.receipt_id), FailureReport(FailureKind.TIMEOUT))
    args = [
        "paper",
        "trace",
        data.paper_id,
        "--database",
        str(data.database),
        "--data-root",
        str(data.data_root),
        "--snapshot",
        data.snapshot_id,
        "--json",
    ]
    result = cli(*args)
    assert result.exit_code == 0, result.output
    output = json.loads(result.stdout)
    workflow = output["workflow"]
    assert workflow["screening"][0]["current_failures"][0]["task_id"] == receipt.task_id
    assert workflow["eligibility"]["model_failure_queue"]["eligible"] is True
    assert (
        workflow["eligibility"]["model_failure_queue"]["scope"]
        == "screening_current_latest_failed_only"
    )
    assert "text" not in output["current"]["fields"]["abstract"]["value"]
    trace = query_paper_trace(
        data.database, data.data_root, data.paper_id, snapshot_id=data.snapshot_id
    )
    assert trace.eligibility == evaluate_paper(trace.projection)
    assert trace.eligibility[Concept.MODEL_FAILURE_QUEUE].eligible is True
    assert trace.projection.visibility == visibility.evaluate_visibility(frozenset())
    expanded = cli(*args, "--show-abstract")
    assert expanded.exit_code == 0, expanded.output
    assert json.loads(expanded.stdout)["current"]["fields"]["abstract"]["value"]["text"]


def test_agent_content_requires_expansion_and_visibility(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.calibration import visibility
    from paper_radar.screening_tasks import SuccessCandidate

    data = archive(tmp_path)
    tasks = ScreeningTasks(
        data.database, data.data_root, clock=lambda: datetime.now(UTC)
    )
    receipt = tasks.register(request_for(data))
    tasks.submit(
        tasks.claim(receipt.receipt_id),
        SuccessCandidate(b'{"boundary":"in_scope","reason_zh":"PRIVATE_AGENT_TEXT"}'),
    )
    args = [
        "paper",
        "trace",
        data.paper_id,
        "--database",
        str(data.database),
        "--data-root",
        str(data.data_root),
        "--snapshot",
        data.snapshot_id,
        "--json",
    ]
    default = cli(*args)
    assert default.exit_code == 0 and "PRIVATE_AGENT_TEXT" not in default.output
    expanded = cli(*args, "--show-agent-content")
    assert expanded.exit_code == 0 and "PRIVATE_AGENT_TEXT" in expanded.output, (
        expanded.output
    )
    monkeypatch.setattr(
        visibility,
        "evaluate_visibility",
        lambda hidden: visibility.Visibility(
            frozenset({visibility.HiddenCondition.UNREVEALED})
        ),
    )
    refused = cli(*args, "--show-agent-content")
    assert refused.exit_code == 1 and "visibility_denied" in refused.output
    assert "PRIVATE_AGENT_TEXT" not in refused.output
    safe = cli(*args)
    assert safe.exit_code == 0 and "PRIVATE_AGENT_TEXT" not in safe.output


def test_second_expired_lease_requires_explicit_settlement_before_retry(
    tmp_path: Path,
) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(
        data.database, data.data_root, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    receipt = tasks.register(request_for(data))
    tasks.fail(tasks.claim(receipt.receipt_id), FailureReport(FailureKind.TIMEOUT))
    tasks.claim(receipt.receipt_id)
    common = ["--database", str(data.database), "--snapshot", data.snapshot_id]
    failures = cli("screening", "failures", *common)
    assert failures.exit_code == 0 and json.loads(failures.stdout)["failures"] == []
    trace_args = [
        "paper",
        "trace",
        data.paper_id,
        *common,
        "--data-root",
        str(data.data_root),
        "--json",
    ]
    trace = cli(*trace_args)
    assert trace.exit_code == 0, trace.output
    task = json.loads(trace.stdout)["workflow"]["screening"][0]["budgets"][0]["tasks"][
        0
    ]
    assert task["state"] == "lease_expired" and task["used_attempts"] == 2
    retry = [
        "screening",
        "retry",
        data.paper_id,
        *common,
        "--request-id",
        "after-reclaim",
        "--reason",
        "所有者选择重试",
        "--actor",
        "owner",
    ]
    refused = cli(*retry)
    assert refused.exit_code == 2 and "not_failed" in refused.output
    # 查询和拒绝重试后依旧未结算;没有 outcome_unknown 或退款。
    unchanged = json.loads(cli(*trace_args).stdout)["workflow"]["screening"][0]
    assert unchanged["budgets"][0]["tasks"][0] == task
    reclaimed = cli(
        "screening", "reclaim", receipt.receipt_id, "--database", str(data.database)
    )
    assert reclaimed.exit_code == 0, reclaimed.output
    assert json.loads(reclaimed.stdout)["state"] == "failed"
    result = cli(*retry)
    assert result.exit_code == 0, result.output
    successor = json.loads(result.stdout)
    restored_query = json.loads(cli(*trace_args).stdout)["workflow"]["screening"][0]
    old, new = restored_query["budgets"][0]["tasks"]
    assert old["attempts"][-1]["failure"]["kind"] == "outcome_unknown"
    assert new["parent_task_id"] == receipt.task_id
    assert new["task_id"] == successor["task_id"] and new["used_attempts"] == 0


def test_queue_is_whole_library_and_historical_fingerprints_stay_in_trace(
    tmp_path: Path,
) -> None:
    from paper_radar.papers import PaperFacts
    from tests.test_paper_mapping import screening_fields
    from tests.test_paper_service import observation

    data = archive(tmp_path)
    papers = PaperFacts(data.database, data.data_root)
    second = papers.submit(observation(doi="10.1234/other", fields=screening_fields()))
    assert second.paper_id
    tasks = ScreeningTasks(
        data.database, data.data_root, clock=lambda: datetime.now(UTC)
    )
    for paper_id in (data.paper_id, second.paper_id):
        receipt = tasks.register(request_for(data, paper_id=paper_id))
        for _ in range(2):
            tasks.fail(
                tasks.claim(receipt.receipt_id), FailureReport(FailureKind.TIMEOUT)
            )
    args = [
        "screening",
        "failures",
        "--database",
        str(data.database),
        "--snapshot",
        data.snapshot_id,
    ]
    output = cli(*args)
    assert output.exit_code == 0, output.output
    assert {item["paper_id"] for item in json.loads(output.stdout)["failures"]} == {
        data.paper_id,
        second.paper_id,
    }
    current = papers.show(data.paper_id)
    papers.correct(
        dict(
            version_id=current.version_id,
            request_id="new-title",
            reason="manual",
            actor="owner",
            fields={"title": {"value": "Changed title", "locator": "manual/title"}},
        )
    )
    output = cli(*args)
    assert [item["paper_id"] for item in json.loads(output.stdout)["failures"]] == [
        second.paper_id
    ]
    trace = cli(
        "paper",
        "trace",
        data.paper_id,
        "--database",
        str(data.database),
        "--data-root",
        str(data.data_root),
        "--snapshot",
        data.snapshot_id,
        "--json",
    )
    budget = json.loads(trace.stdout)["workflow"]["screening"][0]["budgets"][0]
    assert (
        budget["applicability"] == "historical"
        and budget["tasks"][0]["state"] == "failed"
    )


@pytest.mark.parametrize(
    "arguments",
    [
        ("screening", "--help"),
        ("screening", "failures", "--help"),
        ("screening", "retry", "--help"),
        ("screening", "reclaim", "--help"),
        ("paper", "show", "--help"),
        ("paper", "trace", "--help"),
    ],
)
def test_recovery_help_is_cold_chinese_and_has_no_external_io(
    tmp_path: Path, arguments: tuple[str, ...]
) -> None:
    from tests.config_test_support import run_cli

    result = run_cli(tmp_path, *arguments, help_only=True)
    assert result.returncode == 0, result.stderr
    for phrase in ("参数", "副作用", "自动配额", "输出去向", "常见失败", "示例"):
        assert phrase in result.stdout
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("purpose", ["production", "experiment", "unknown"])
def test_show_and_trace_are_root_neutral_and_always_evaluate_visibility(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    purpose: str,
) -> None:
    from paper_radar.body import BodyService
    from paper_radar.calibration import visibility

    data = archive(tmp_path)
    if purpose != "unknown":
        BodyService(data.database, data.data_root).register_root(purpose)
    calls = []
    original = visibility.evaluate_visibility

    def observe(hidden: frozenset[visibility.HiddenCondition]) -> visibility.Visibility:
        calls.append(hidden)
        return original(hidden)

    monkeypatch.setattr(visibility, "evaluate_visibility", observe)
    for command in ("show", "trace"):
        calls.clear()
        result = cli(
            "paper",
            command,
            data.paper_id,
            "--database",
            str(data.database),
            "--data-root",
            str(data.data_root),
            "--snapshot",
            data.snapshot_id,
            "--json",
        )
        assert result.exit_code == 0, result.output
        output = json.loads(result.stdout)["workflow"]
        assert output["root"]["purpose"] == purpose
        assert calls and all(hidden == frozenset() for hidden in calls)
        if purpose == "experiment":
            assert (
                "experiment_no_auto_queue"
                in output["eligibility"]["eligible_for_auto_read"]["reasons"]
            )


@pytest.mark.parametrize("field", ["request-id", "reason", "actor"])
def test_retry_requires_nonempty_audit_fields(tmp_path: Path, field: str) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(
        data.database, data.data_root, clock=lambda: datetime.now(UTC)
    )
    receipt = tasks.register(request_for(data))
    for _ in range(2):
        tasks.fail(tasks.claim(receipt.receipt_id), FailureReport(FailureKind.TIMEOUT))
    values = {"request-id": "request", "reason": "reason", "actor": "owner"}
    values[field] = " "
    args = [part for key, value in values.items() for part in ("--" + key, value)]
    result = cli(
        "screening",
        "retry",
        data.paper_id,
        "--database",
        str(data.database),
        "--snapshot",
        data.snapshot_id,
        *args,
    )
    assert result.exit_code == 2 and "invalid_request" in result.output
    assert tasks.status(receipt.receipt_id).state == "failed"


def test_retry_rejects_ambiguity_and_visibility_before_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.calibration import visibility

    data = archive(tmp_path)
    tasks = ScreeningTasks(
        data.database, data.data_root, clock=lambda: datetime.now(UTC)
    )
    for stage in ("boundary", "value"):
        receipt = tasks.register(
            request_for(
                data,
                stage=stage,
                **({"original_title_is_zh": False} if stage == "value" else {}),
            )
        )
        for _ in range(2):
            tasks.fail(
                tasks.claim(receipt.receipt_id), FailureReport(FailureKind.TIMEOUT)
            )
    args = [
        "screening",
        "retry",
        data.paper_id,
        "--database",
        str(data.database),
        "--snapshot",
        data.snapshot_id,
        "--request-id",
        "retry",
        "--reason",
        "所有者选择重试",
        "--actor",
        "owner",
    ]
    ambiguous = cli(*args)
    assert ambiguous.exit_code == 2 and "ambiguous_failure" in ambiguous.output
    monkeypatch.setattr(
        visibility,
        "evaluate_visibility",
        lambda hidden: visibility.Visibility(
            frozenset({visibility.HiddenCondition.WAITING_CALIBRATION})
        ),
    )
    refused = cli(*args, "--stage", "boundary")
    assert refused.exit_code == 2 and "visibility_denied" in refused.output
    assert len(tasks.failures(snapshot_id=data.snapshot_id)) == 2
    monkeypatch.undo()
    allowed = cli(*args, "--stage", "boundary")
    assert allowed.exit_code == 0, allowed.output
    assert json.loads(allowed.stdout)["stage"] == "boundary"


@pytest.mark.parametrize("expired", [False, True])
def test_backup_restore_preserves_failure_parent_chain_and_readonly_expired_trace(
    tmp_path: Path,
    expired: bool,
) -> None:
    import os
    import subprocess
    import sys

    data = archive(tmp_path)

    def clock() -> datetime:
        return datetime(2026, 1, 1, tzinfo=UTC)

    tasks = ScreeningTasks(data.database, data.data_root, clock=clock)
    initial = tasks.register(request_for(data))
    for _ in range(2):
        tasks.fail(tasks.claim(initial.receipt_id), FailureReport(FailureKind.TIMEOUT))
    retry_args = [
        "screening",
        "retry",
        data.paper_id,
        "--database",
        str(data.database),
        "--snapshot",
        data.snapshot_id,
        "--request-id",
        "restore-retry",
        "--reason",
        "PRIVATE_REASON",
        "--actor",
        "PRIVATE_ACTOR",
    ]
    registered = cli(*retry_args)
    assert registered.exit_code == 0, registered.output
    successor = json.loads(registered.stdout)
    tasks.fail(tasks.claim(successor["receipt_id"]), FailureReport(FailureKind.TIMEOUT))
    second = tasks.claim(successor["receipt_id"])
    if not expired:
        tasks.fail(second, FailureReport(FailureKind.CANCELLED))
    common = [
        "--database",
        str(data.database),
        "--data-root",
        str(data.data_root),
        "--snapshot",
        data.snapshot_id,
        "--json",
    ]
    before = cli("paper", "trace", data.paper_id, *common)
    assert before.exit_code == 0, before.output
    queue = cli(
        "screening",
        "failures",
        "--database",
        str(data.database),
        "--snapshot",
        data.snapshot_id,
    )
    assert queue.exit_code == 0, queue.output
    output = tmp_path / "backups"
    backup = cli(
        "backup",
        "create",
        "--database",
        str(data.database),
        "--data-root",
        str(data.data_root),
        "--output",
        str(output),
    )
    assert backup.exit_code == 0, backup.output
    (batch,) = output.iterdir()
    restored = tmp_path / "restored"
    process = subprocess.run(
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
    assert process.returncode == 0, process.stdout + process.stderr
    data.database.rename(data.database.with_suffix(".unavailable"))
    data.data_root.rename(tmp_path / "original-unavailable")
    # 恢复查询走冷子进程和真实 CLI;socket 拒绝确保只依赖恢复副本。
    code = """
import json, socket, ssl, sys
from pathlib import Path
from paper_radar.cli import app
from typer.testing import CliRunner

def forbidden(*args, **kwargs):
    raise AssertionError("external I/O forbidden")
socket.socket = forbidden
root = Path(sys.argv[1])
database = str(root / "database.sqlite3")
def run(*args):
    result = CliRunner().invoke(app, list(args))
    assert result.exit_code == 0, (result.output, repr(result.exception))
    return json.loads(result.stdout)
trace = run("paper", "trace", sys.argv[2], "--database", database,
    "--data-root", str(root), "--snapshot", sys.argv[3], "--json")
queue = run("screening", "failures", "--database", database, "--snapshot", sys.argv[3])
again = run("paper", "trace", sys.argv[2], "--database", database,
    "--data-root", str(root), "--snapshot", sys.argv[3], "--json")
assert trace == again
print(json.dumps(dict(trace=trace, queue=queue), ensure_ascii=False))
"""
    process = subprocess.run(
        [sys.executable, "-c", code, str(restored), data.paper_id, data.snapshot_id],
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert process.returncode == 0, process.stdout + process.stderr
    saved = json.loads(process.stdout)
    assert saved["trace"] == json.loads(before.stdout)
    assert saved["queue"] == json.loads(queue.stdout)
    generations = saved["trace"]["workflow"]["screening"][0]["budgets"][0]["tasks"]
    assert generations[1]["parent_task_id"] == initial.task_id
    assert generations[1]["state"] == ("lease_expired" if expired else "failed")
    assert generations[1]["used_attempts"] == 2
    assert "PRIVATE_" not in process.stdout + process.stderr


def test_product_retry_receipt_executes_via_explicit_screen_and_continues_value(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    feed: FeedFixture,
) -> None:
    # Feed fixture 与合成 Pi RPC 都在外部接缝;不替换任务登记/领取/接收。
    from tests.experiment_screen_support import screen_fixture

    prepared = screen_fixture(feed, tmp_path, monkeypatch, mode="output_invalid")
    result = prepared.screen()
    assert result.exit_code == 4, result.output
    original = json.loads(result.stdout)["boundary"]["receipt"]
    database = prepared.root / "paper-radar.sqlite3"
    retry = cli(
        "screening",
        "retry",
        prepared.paper_id,
        "--database",
        str(database),
        "--snapshot",
        prepared.snapshot,
        "--request-id",
        "cli-recover",
        "--reason",
        "PRIVATE_OWNER_REASON",
        "--actor",
        "owner",
    )
    assert retry.exit_code == 0, retry.output
    successor = json.loads(retry.stdout)
    (prepared.credentials / "auth.json").write_text(
        json.dumps(dict(token="synthetic-recovered-oauth"))
    )
    executed = prepared.screen(receipt_id=successor["receipt_id"])
    assert executed.exit_code == 0, executed.output
    assert json.loads(executed.stdout)["value"] is None
    continued = prepared.screen(continue_value=True)
    assert continued.exit_code == 0, continued.output
    trace = cli(
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
    )
    assert trace.exit_code == 0, trace.output
    workflow = json.loads(trace.stdout)["workflow"]
    assert workflow["root"]["purpose"] == "experiment"
    assert workflow["selections"][0]["selection_id"] == prepared.selection_id
    assert workflow["selections"][0]["authorizer"] == "owner"
    assert workflow["feed"]["language"]["observations"]
    assert workflow["eligibility"]["current_screening_artifact"]["eligible"] is True
    assert workflow["eligibility"]["effective_screening_decision"]["eligible"] is False
    assert (
        workflow["screening"][0]["budgets"][0]["tasks"][1]["parent_task_id"]
        == original["task_id"]
    )
    for forbidden in (
        "PRIVATE_SYNTHETIC_ABSTRACT",
        "PRIVATE_OWNER_REASON",
        "PRIVATE_WAIVER_REASON",
        "PRIVATE_EGRESS_REASON",
    ):
        assert forbidden not in trace.output + retry.output


def test_trace_preserves_historical_screening_applicability(tmp_path: Path) -> None:
    from paper_radar.papers import PaperFacts
    from paper_radar.screening_tasks import SuccessCandidate, SuccessReceipt
    from tests.a7_value_support import value_payload

    data = archive(tmp_path)
    tasks = ScreeningTasks(
        data.database, data.data_root, clock=lambda: datetime.now(UTC)
    )
    receipt = tasks.register(
        request_for(data, stage="value", original_title_is_zh=False)
    )
    succeeded = tasks.submit(
        tasks.claim(receipt.receipt_id), SuccessCandidate(value_payload())
    )
    assert isinstance(succeeded, SuccessReceipt)
    papers = PaperFacts(data.database, data.data_root)
    current = papers.show(data.paper_id)
    papers.correct(
        dict(
            version_id=current.version_id,
            request_id="artifact-history",
            reason="manual",
            actor="owner",
            fields={"title": {"value": "New input", "locator": "manual/title"}},
        )
    )
    result = cli(
        "paper",
        "trace",
        data.paper_id,
        "--database",
        str(data.database),
        "--data-root",
        str(data.data_root),
        "--snapshot",
        data.snapshot_id,
        "--json",
    )
    assert result.exit_code == 0, result.output
    artifact = json.loads(result.stdout)["workflow"]["eligibility"][
        "current_screening_artifact"
    ]
    assert artifact["eligible"] is False
    assert artifact["reasons"] == ["screening_historical"]


def test_retry_exact_replay_precedes_later_generations_and_changed_facts(
    tmp_path: Path,
) -> None:
    from paper_radar.papers import PaperFacts

    data = archive(tmp_path)
    tasks = ScreeningTasks(
        data.database, data.data_root, clock=lambda: datetime.now(UTC)
    )
    receipt = tasks.register(request_for(data))
    common = [
        "screening",
        "retry",
        data.paper_id,
        "--database",
        str(data.database),
        "--snapshot",
        data.snapshot_id,
        "--reason",
        "owner choice",
        "--actor",
        "owner",
    ]
    for generation in range(2):
        for _ in range(2):
            tasks.fail(
                tasks.claim(receipt.receipt_id), FailureReport(FailureKind.TIMEOUT)
            )
        result = cli(*common, "--request-id", f"retry-{generation}")
        assert result.exit_code == 0, result.output
        if generation == 0:
            first_successor = json.loads(result.stdout)
        receipt = tasks.get_receipt(json.loads(result.stdout)["receipt_id"])
    papers = PaperFacts(data.database, data.data_root)
    current = papers.show(data.paper_id)
    papers.correct(
        dict(
            version_id=current.version_id,
            request_id="after-retry",
            reason="manual",
            actor="owner",
            fields={"title": {"value": "Later input", "locator": "manual/title"}},
        )
    )
    replay = cli(*common, "--request-id", "retry-0")
    assert replay.exit_code == 0, replay.output
    assert json.loads(replay.stdout) == first_successor
    assert tasks.status(receipt.receipt_id).used_attempts == 0
