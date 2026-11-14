"""B 显式 Read 的独立 D1 CLI 契约;仅合成外部边界。"""

import json
from pathlib import Path

import pytest

from tests.test_experiment_candidates_cli import FeedFixture, invoke
from tests.test_experiment_candidates_cli import feed as feed


def test_read_help_is_local_and_describes_recovery() -> None:
    result = invoke("read", "--help")
    assert result.exit_code == 0, result.output
    for text in ("自动配额", "--task-id", "--request-id", "reclaim", "130"):
        assert text in result.output


def test_explicit_read_accepts_real_rpc_and_private_analysis(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.experiment_read_support import read_fixture

    fixture = read_fixture(feed, tmp_path, monkeypatch)
    result = fixture.read()
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["state"] == "succeeded"
    assert payload["receipt"]["label"] == "manual"
    assert payload["task"]["output_language"] == "zh"
    assert len(payload["task"]["attempts"]) == 1
    assert "PRIVATE_READ_CONCLUSION" not in result.output
    query = fixture.query(
        "analysis", payload["task"]["analysis_id"], "--snapshot", fixture.snapshot
    )
    assert query.exit_code == 0, query.output
    content = json.loads(query.stdout)
    assert content["executor_kind"] == "pi_rpc"
    import hashlib

    from tests.experiment_layout_support import synthetic_pdf

    assert content["pdf_sha256"] == hashlib.sha256(synthetic_pdf()).hexdigest()
    assert content["task_id"] == payload["task"]["task_id"]
    assert content["output"]["one_sentence_conclusion"] == "PRIVATE_READ_CONCLUSION"
    assert "未核对" in content["warning"]
    assert content["evidence"]["e000002"][0]["text"]
    assert content["discard_counts"] == [
        {"category": "main_findings", "count": 0},
        {"category": "reusable_points", "count": 0},
        {"category": "key_limitations", "count": 0},
    ]
    from paper_radar.calibration.visibility import (
        Visibility,
        VisibilityCapability,
        VisibilityPermission,
    )
    from paper_radar.paper_trace import query_paper_trace

    original_permission = Visibility.permission

    def deny_content(
        self: Visibility, capability: VisibilityCapability
    ) -> VisibilityPermission:
        if capability is VisibilityCapability.AGENT_CONTENT:
            return VisibilityPermission.DENIED
        return original_permission(self, capability)

    monkeypatch.setattr(Visibility, "permission", deny_content)
    denied = fixture.query("analysis", payload["task"]["analysis_id"])
    assert denied.exit_code == 2 and "visibility_denied" in denied.output
    root = fixture.layout.extraction.root
    safe = query_paper_trace(
        root.database,
        root.data_root,
        fixture.layout.extraction.prepared.paper_id,
        snapshot_id=fixture.snapshot,
    ).safe_payload()
    assert safe["read_analyses"]
    assert "PRIVATE_READ_CONCLUSION" not in str(safe)


def test_final_attempt_degrades_and_replay_never_executes(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.read_queries import ReadQueries
    from paper_radar.read_tasks import ReadTaskError
    from tests.experiment_read_support import read_fixture

    fixture = read_fixture(feed, tmp_path, monkeypatch, mode="degrade")
    first = fixture.read()
    assert first.exit_code == 0, first.output
    value = json.loads(first.stdout)
    assert len(value["task"]["attempts"]) == 2
    root = fixture.layout.extraction.root
    with pytest.raises(ReadTaskError, match="ordinary_consumption_denied"):
        ReadQueries(root.database, root.data_root).analysis(
            value["task"]["analysis_id"], ordinary=True
        )
    private = fixture.query("analysis", value["task"]["analysis_id"])
    assert private.exit_code == 0, private.output
    content = json.loads(private.stdout)
    assert content["has_discards"] is True
    assert content["discard_counts"][0]["count"] == 1
    assert len(content["output"]["main_findings"]) == 1
    assert all(content["rule_versions"].values())
    replay = fixture.read()
    assert replay.exit_code == 0, replay.output
    assert json.loads(replay.stdout) == {
        "state": "replayed",
        "receipt": value["receipt"],
    }
    assert "PRIVATE_DISCARDED" not in private.output
    log = "".join(p.read_text() for p in (root.root / "logs").rglob("*.jsonl"))
    for secret in (
        "PRIVATE_READ_CONCLUSION",
        "PRIVATE_DISCARDED",
        "PRIVATE_BAD_ID",
        "PRIVATE_READ_PROMPT",
    ):
        assert secret not in log


def test_failure_retry_and_explicit_task_continue_are_a_real_cli_path(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.experiment_read_support import read_fixture

    fixture = read_fixture(feed, tmp_path, monkeypatch, mode="invalid")
    failed = fixture.read()
    assert failed.exit_code == 4, failed.output
    value = json.loads(failed.stdout.splitlines()[0])
    task = value["task"]["task_id"]
    assert len(value["task"]["attempts"]) == 2
    result = fixture.query("failures", "--snapshot", fixture.snapshot)
    assert result.exit_code == 0, result.output
    assert [t["task_id"] for t in json.loads(result.stdout)] == [task]
    from paper_radar.calibration.visibility import (
        Visibility,
        VisibilityCapability,
        VisibilityPermission,
    )

    original_permission = Visibility.permission

    def deny_decision(
        self: Visibility, capability: VisibilityCapability
    ) -> VisibilityPermission:
        if capability is VisibilityCapability.SET_DECISION:
            return VisibilityPermission.DENIED
        return original_permission(self, capability)

    with monkeypatch.context() as visibility_patch:
        visibility_patch.setattr(Visibility, "permission", deny_decision)
        hidden = fixture.query(
            "retry",
            task,
            "--request-id",
            "hidden-retry",
            "--reason",
            "owner retry",
            "--actor",
            "owner",
        )
        assert hidden.exit_code == 2 and "visibility_denied" in hidden.output
    assert len(json.loads(fixture.query("tasks").stdout)) == 1
    retried = fixture.query(
        "retry",
        task,
        "--request-id",
        "retry-1",
        "--reason",
        "PRIVATE_RETRY",
        "--actor",
        "owner",
    )
    assert retried.exit_code == 0, retried.output
    receipt = json.loads(retried.stdout)
    assert receipt["generation"] == 2
    assert fixture.query("failures", "--snapshot", fixture.snapshot).stdout == "[]\n"
    continued = fixture.read(request=None, task=receipt["task_id"])
    assert continued.exit_code == 4, continued.output
    assert len(json.loads(continued.stdout.splitlines()[0])["task"]["attempts"]) == 2
    repeated = fixture.query(
        "retry",
        task,
        "--request-id",
        "retry-1",
        "--reason",
        "PRIVATE_RETRY",
        "--actor",
        "owner",
    )
    assert repeated.exit_code == 0, repeated.output
    assert json.loads(repeated.stdout) == receipt

    from paper_radar.eligibility import Concept
    from paper_radar.paper_trace import query_paper_trace
    from tests.test_experiment_selection_cli import select

    root = fixture.layout.extraction.root
    owner = fixture.layout.extraction.prepared
    trace = query_paper_trace(
        root.database, root.data_root, owner.paper_id, snapshot_id=fixture.snapshot
    )
    assert trace.eligibility[Concept.MODEL_FAILURE_QUEUE].eligible is True
    assert (
        trace.eligibility[Concept.MODEL_FAILURE_QUEUE].scope
        == "screening_and_read_current_latest_failed_only"
    )
    replaced = select(
        root.root,
        owner.view_id,
        "replacement",
        "--position",
        "2",
        "--replaces",
        owner.selection_id,
        "--replacement-reason",
        "owner chose another paper",
    )
    assert replaced.exit_code == 0, replaced.output
    # 全库失败查询保留旧样本的当前输入失败;选择变化不允许新 retry。
    all_failed = fixture.query("failures", "--snapshot", fixture.snapshot)
    assert [r["task_id"] for r in json.loads(all_failed.stdout)] == [receipt["task_id"]]
    rejected = fixture.query(
        "retry",
        receipt["task_id"],
        "--request-id",
        "retry-2",
        "--reason",
        "retry after replacement",
        "--actor",
        "owner",
    )
    assert rejected.exit_code == 2 and "selection_changed" in rejected.output
    replay_after_change = fixture.query(
        "retry",
        task,
        "--request-id",
        "retry-1",
        "--reason",
        "PRIVATE_RETRY",
        "--actor",
        "owner",
    )
    assert replay_after_change.exit_code == 0, replay_after_change.output
    assert json.loads(replay_after_change.stdout) == receipt
    original_replay = fixture.read()
    assert (
        original_replay.exit_code == 0
        and json.loads(original_replay.stdout)["state"] == "replayed"
    )


@pytest.mark.parametrize(
    ("problem", "reason"),
    [
        ("no_review", "document_gate_required"),
        ("legacy_review", "owner_review_required"),
        ("veto", "document_gate_required"),
        ("egress", "egress_not_authorized"),
        ("budget", "read_input_over_budget"),
        ("waiver", "evidence_missing"),
    ],
)
def test_read_refuses_before_authentication_and_attempt(
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    problem: str,
    reason: str,
) -> None:
    from paper_radar.body import BodyService
    from paper_radar.body.extraction import LAYOUT_CHECKS
    from paper_radar.read_tasks import ReadTasks
    from tests.experiment_read_support import read_fixture
    from tests.test_owner_live_waiver import command as waiver

    fixture = read_fixture(
        feed,
        tmp_path,
        monkeypatch,
        reviewed=problem not in {"no_review", "legacy_review", "veto"},
    )
    root = fixture.layout.extraction.root
    paper = fixture.layout.extraction.prepared.paper_id
    if problem == "legacy_review":
        # 故障/历史反例:普通旧 actor 字符串不能提升为 B 所有者来源。
        BodyService(root.database, root.data_root).review_layout(
            fixture.layout.identity,
            passed=True,
            checks=dict.fromkeys(LAYOUT_CHECKS, True),
            actor="owner",
            note="legacy unverified owner string",
            request_id="legacy-owner-review",
        )
    if problem == "veto":
        fixture.layout.review(passed=False)
    if problem == "egress":
        result = invoke(
            "egress-authorize",
            "--root",
            str(root.root),
            "--snapshot",
            fixture.snapshot,
            "--stage",
            "read",
            "--disabled",
            "--reason",
            "owner revoked",
        )
        assert result.exit_code == 0, result.output
    if problem == "budget":
        monkeypatch.setattr("paper_radar.read_inputs.budget.SINGLE_FRAME_BYTES", 1)
    if problem == "waiver":
        assert (
            waiver(root.database, "--disable", "--reason", "strict mode").exit_code == 0
        )
    observed = fixture.layout.extraction.prepared.credentials / "auth-observed.json"
    before = observed.stat().st_mtime_ns
    result = fixture.read()
    assert result.exit_code == 2, result.output
    assert reason in result.output
    assert observed.stat().st_mtime_ns == before
    service = ReadTasks(root.database, root.data_root)
    assert all(t.attempts == () for t in service.history(paper))
    assert service.analyses(paper) == ()


def test_authentication_race_revocation_preserves_ready_receipt_and_recovery(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.pi_execution import auth, launcher
    from tests.experiment_read_support import read_fixture

    fixture = read_fixture(feed, tmp_path, monkeypatch)
    root = fixture.layout.extraction.root
    original = auth.credential_token

    from typing import Any

    def revoke(*args: Any, **kwargs: Any) -> str:
        token = original(*args, **kwargs)
        result = invoke(
            "egress-authorize",
            "--root",
            str(root.root),
            "--snapshot",
            fixture.snapshot,
            "--stage",
            "read",
            "--disabled",
            "--reason",
            "revoked during synthetic auth",
        )
        assert result.exit_code == 0, result.output
        return token

    monkeypatch.setattr(launcher, "credential_token", revoke)
    denied = fixture.read()
    assert denied.exit_code == 2 and "egress_not_authorized" in denied.output
    current = fixture.query("tasks")
    assert current.exit_code == 0, current.output
    (task,) = json.loads(current.stdout)
    assert task["attempts"] == [] and task["state"] == "ready"
    monkeypatch.setattr(launcher, "credential_token", original)
    allowed = invoke(
        "egress-authorize",
        "--root",
        str(root.root),
        "--snapshot",
        fixture.snapshot,
        "--stage",
        "read",
        "--reason",
        "owner reauthorizes",
    )
    assert allowed.exit_code == 0, allowed.output
    replay = fixture.read()
    assert replay.exit_code == 0 and json.loads(replay.stdout)["state"] == "replayed"
    resumed = fixture.read(request=None, task=task["task_id"])
    assert resumed.exit_code == 0, resumed.output
    assert json.loads(resumed.stdout)["state"] == "succeeded"


def test_restore_subprocess_preserves_read_axes_evidence_and_experiment_refusal(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os
    import subprocess
    import sys

    from typer.testing import CliRunner

    from paper_radar.cli import app
    from paper_radar.experiment.reading import analysis_payload
    from paper_radar.paper_trace import query_paper_trace
    from tests.experiment_read_support import read_fixture

    fixture = read_fixture(feed, tmp_path, monkeypatch, mode="degrade")
    result = fixture.read()
    assert result.exit_code == 0, result.output
    analysis = json.loads(result.stdout)["task"]["analysis_id"]
    root = fixture.layout.extraction.root
    paper = fixture.layout.extraction.prepared.paper_id
    expected = json.loads(
        json.dumps(
            dict(
                trace=query_paper_trace(
                    root.database, root.data_root, paper, snapshot_id=fixture.snapshot
                ).safe_payload(),
                analysis=analysis_payload(
                    root.database,
                    root.data_root,
                    analysis,
                    snapshot_id=fixture.snapshot,
                ),
            ),
            default=lambda value: (
                value.model_dump(mode="json")
                if hasattr(value, "model_dump")
                else value.isoformat()
            ),
        )
    )
    assert "PRIVATE_READ_CONCLUSION" not in json.dumps(expected["trace"])
    assert expected["trace"]["read_analyses"][0]["body_status"] == "current"
    assert expected["trace"]["read_analyses"][0]["config_status"] == "current"
    backup = CliRunner().invoke(
        app,
        [
            "backup",
            "create",
            "--database",
            str(root.database),
            "--data-root",
            str(root.data_root),
            "--output",
            str(tmp_path / "backups"),
        ],
    )
    assert backup.exit_code == 0, backup.output
    (batch,) = (tmp_path / "backups").iterdir()
    restored = tmp_path / "restored"
    restored_cli = subprocess.run(
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
    assert restored_cli.returncode == 0, restored_cli.stdout + restored_cli.stderr
    for path in (
        root.root,
        fixture.layout.extraction.models,
        fixture.layout.extraction.prepared.credentials,
        tmp_path / "synthetic.pdf",
    ):
        if path.exists():
            path.rename(path.with_name(path.name + "-unavailable"))
    cold = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.experiment_read_recovery_worker",
            str(restored),
            paper,
            fixture.snapshot,
            analysis,
        ],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        check=False,
    )
    assert cold.returncode == 0, cold.stdout + cold.stderr
    assert json.loads(cold.stdout) == expected


def test_expired_read_requires_explicit_reclaim_before_cli_resume(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from datetime import UTC, datetime, timedelta
    from typing import Any

    from paper_radar import reading_cli
    from paper_radar.read_execution import service as rpc
    from tests.experiment_read_support import read_fixture

    fixture = read_fixture(feed, tmp_path, monkeypatch)
    now = [datetime.now(UTC)]
    monkeypatch.setattr(reading_cli, "reading_clock", lambda: now[0])
    from paper_radar.llm.rpc import run_call

    actual = run_call

    def interrupt(*args: Any, **kwargs: Any) -> Any:
        raise KeyboardInterrupt

    monkeypatch.setattr(rpc, "run_call", interrupt)
    interrupted = fixture.read()
    assert interrupted.exit_code == 130, interrupted.output
    (task,) = json.loads(fixture.query("tasks").stdout)
    assert task["state"] == "running" and len(task["attempts"]) == 1
    now[0] += timedelta(seconds=601)
    unknown = fixture.query("failures", "--snapshot", fixture.snapshot)
    assert unknown.exit_code == 0 and json.loads(unknown.stdout) == []
    stale = fixture.read(request=None, task=task["task_id"])
    assert stale.exit_code == 2 and "task_running" in stale.output
    (unsettled,) = json.loads(fixture.query("tasks").stdout)
    assert unsettled["attempts"][0]["settled_at"] is None
    reclaimed = fixture.query("reclaim", task["task_id"])
    assert reclaimed.exit_code == 0, reclaimed.output
    settled = json.loads(reclaimed.stdout)
    assert settled["state"] == "ready" and settled["remaining_attempts"] == 1
    assert settled["attempts"][0]["failure"] == "outcome_unknown"
    monkeypatch.setattr(rpc, "run_call", actual)
    continued = fixture.read(request=None, task=task["task_id"])
    assert continued.exit_code == 0, continued.output
    assert len(json.loads(continued.stdout)["task"]["attempts"]) == 2


@pytest.mark.parametrize(
    "command", ["read", "tasks", "failures", "retry", "reclaim", "analysis"]
)
def test_new_read_help_is_cold_complete_and_never_opens_resources(
    tmp_path: Path, command: str
) -> None:
    from tests.config_test_support import run_cli

    group = "experiment" if command == "read" else "reading"
    result = run_cli(tmp_path, group, command, "--help", help_only=True)
    assert result.returncode == 0, result.stderr
    for text in ("参数", "副作用", "自动配额", "输出去向", "常见失败", "示例", "130"):
        assert text in result.stdout
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ("egress", "egress_not_authorized"),
        ("selection", "selection_changed"),
        ("revision", "frozen_version_changed"),
    ],
)
def test_read_rechecks_connection_after_waiting_for_claim_transaction(
    feed: FeedFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
    reason: str,
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event, current_thread

    from sqlalchemy import Connection, Engine, event

    from paper_radar.experiment.egress import EgressError
    from paper_radar.experiment.pdf import PdfError
    from paper_radar.experiment.reading import Reading
    from tests.experiment_read_support import read_fixture
    from tests.test_experiment_selection_cli import select
    from tests.test_owner_live_waiver import command as waiver

    fixture = read_fixture(feed, tmp_path, monkeypatch)
    root = fixture.layout.extraction.root
    assert (
        waiver(root.database, "--disable", "--reason", "prepare ready task").exit_code
        == 0
    )
    pending = fixture.read()
    assert pending.exit_code == 2 and "evidence_missing" in pending.output
    (task,) = json.loads(fixture.query("tasks").stdout)
    assert (
        waiver(
            root.database, "--enable", "--reason", "synthetic owner waiver"
        ).exit_code
        == 0
    )
    waiting, release = Event(), Event()

    def pause(
        connection: Connection,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        if statement == "BEGIN IMMEDIATE" and current_thread().name.startswith(
            "read-claim"
        ):
            waiting.set()
            assert release.wait(30)

    execution = fixture.layout.extraction.prepared
    service = Reading(
        root,
        snapshot=fixture.snapshot,
        credentials_dir=execution.credentials,
        material_root=execution.materials,
        install_root=execution.install,
    )
    event.listen(Engine, "before_cursor_execute", pause)
    try:
        with ThreadPoolExecutor(1, thread_name_prefix="read-claim") as pool:
            future = pool.submit(
                service.run,
                execution.paper_id,
                identity=fixture.layout.identity,
                task_id=task["task_id"],
            )
            try:
                assert waiting.wait(30)
                if change == "egress":
                    changed = invoke(
                        "egress-authorize",
                        "--root",
                        str(root.root),
                        "--snapshot",
                        fixture.snapshot,
                        "--stage",
                        "read",
                        "--disabled",
                        "--reason",
                        "owner revocation",
                    )
                elif change == "selection":
                    changed = select(
                        root.root,
                        execution.view_id,
                        "replacement",
                        "--position",
                        "2",
                        "--replaces",
                        execution.selection_id,
                        "--replacement-reason",
                        "owner replacement",
                    )
                else:
                    from paper_radar.papers import PaperFacts

                    papers = PaperFacts(root.database, root.data_root)
                    current = papers.show(execution.paper_id)
                    corrected = papers.correct(
                        dict(
                            version_id=current.version_id,
                            request_id="revision",
                            actor="owner",
                            reason="synthetic concurrent correction",
                            fields={
                                "title": {
                                    "value": "Changed frozen title",
                                    "locator": "manual/title",
                                }
                            },
                        )
                    )
                    assert corrected.status == "retained"
                    changed = None
                if changed is not None:
                    assert changed.exit_code == 0, changed.output
            finally:
                release.set()
            with pytest.raises((EgressError, PdfError)) as rejected:
                future.result(timeout=45)
            rejection = rejected.value
            assert isinstance(rejection, (EgressError, PdfError))
            assert rejection.reason == reason
    finally:
        event.remove(Engine, "before_cursor_execute", pause)
    (unchanged,) = json.loads(fixture.query("tasks").stdout)
    assert unchanged["attempts"] == []


def test_structured_owner_is_claim_basis_and_broken_link_rejects_backup(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import sqlite3

    from typer.testing import CliRunner

    from paper_radar.body import BodyService
    from paper_radar.body.extraction import LAYOUT_CHECKS
    from paper_radar.cli import app
    from paper_radar.experiment.layout import LayoutReviews
    from paper_radar.read_tasks import ReadTasks
    from tests.experiment_read_support import read_fixture

    fixture = read_fixture(feed, tmp_path, monkeypatch)
    root = fixture.layout.extraction.root
    paper = fixture.layout.extraction.prepared.paper_id
    # 故障反例准备:旧来源的“owner”通过不能抢走新的结构化所有者依据。
    BodyService(root.database, root.data_root).review_layout(
        fixture.layout.identity,
        passed=True,
        checks=dict.fromkeys(LAYOUT_CHECKS, True),
        actor="owner",
        note="later unmarked review",
        request_id="later-legacy-review",
    )
    result = fixture.read()
    assert result.exit_code == 0, result.output
    task = json.loads(result.stdout)["task"]["task_id"]
    owner = LayoutReviews(root.database, root.data_root).history(paper)[0]
    actual = ReadTasks(root.database, root.data_root).task(task)
    assert actual.attempts[0].basis["review_id"] == owner["review_id"]
    # 介质故障注入:旧 review 仍有合法 Body 依据,但 B 不允许丢失所有者结构来源。
    with sqlite3.connect(root.database) as connection:
        connection.execute(
            "UPDATE read_attempts SET basis_json=json_set(basis_json, '$.review_id', "
            "(SELECT review_id FROM body_layout_reviews "
            "WHERE recording_kind IS NULL LIMIT 1))"
        )
    backup = CliRunner().invoke(
        app,
        [
            "backup",
            "create",
            "--database",
            str(root.database),
            "--data-root",
            str(root.data_root),
            "--output",
            str(tmp_path / "bad-backup"),
        ],
    )
    assert backup.exit_code == 2 and "registration_invalid" in backup.output


def test_multiple_successful_bodies_cannot_be_selected_by_supplied_fingerprint(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.config import compile_config
    from tests.config_projection_support import new_yaml_version
    from tests.experiment_read_support import read_fixture

    fixture = read_fixture(feed, tmp_path, monkeypatch)
    root = fixture.layout.extraction.root
    new_yaml_version(
        root.settings,
        "extraction",
        lambda c: c["models"]["layout"].update(commit_sha="9" * 40),
    )
    manifest = fixture.layout.extraction.models / "deployment.json"
    deployment = json.loads(manifest.read_text())
    for model in deployment["models"]:
        if "layout" in model["repo_id"]:
            model["commit_sha"] = "9" * 40
    manifest.write_text(json.dumps(deployment))
    fixture.layout.extraction.snapshot = compile_config(
        root.settings, root.database
    ).snapshot_id
    second = fixture.layout.extraction.extract()
    assert second.exit_code == 0, second.output
    credentials = fixture.layout.extraction.prepared.credentials
    observed = (credentials / "auth-observed.json").stat().st_mtime_ns
    result = fixture.read()
    assert result.exit_code == 2 and "ambiguous_extractions" in result.output
    assert json.loads(fixture.query("tasks").stdout) == []
    assert (credentials / "auth-observed.json").stat().st_mtime_ns == observed
