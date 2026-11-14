"""规范 paper-ID Read retry 的独立 D1 CLI。"""

import json
from pathlib import Path

import pytest

from tests.experiment_read_support import read_fixture
from tests.test_experiment_candidates_cli import FeedFixture
from tests.test_experiment_candidates_cli import feed as feed


def test_standard_paper_retry_registers_current_failed_successor_without_execution(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = read_fixture(feed, tmp_path, monkeypatch, mode="invalid")
    failed = fixture.read()
    assert failed.exit_code == 4, failed.output
    parent = json.loads(failed.stdout.splitlines()[0])["task"]["task_id"]
    paper = fixture.layout.extraction.prepared.paper_id
    result = fixture.query(
        "retry",
        paper,
        "--snapshot",
        fixture.snapshot,
        "--request-id",
        "paper-retry",
        "--reason",
        "owner retries",
        "--actor",
        "owner",
    )
    assert result.exit_code == 0, result.output
    receipt = json.loads(result.stdout)
    assert receipt["paper_id"] == paper and receipt["generation"] == 2
    tasks = json.loads(fixture.query("tasks").stdout)
    child = next(t for t in tasks if t["task_id"] == receipt["task_id"])
    assert child["parent_task_id"] == parent
    assert child["attempts"] == [] and child["state"] == "ready"

    continued = fixture.read(request=None, task=receipt["task_id"])
    assert continued.exit_code == 4, continued.output
    next_retry = fixture.query(
        "retry",
        paper,
        "--snapshot",
        fixture.snapshot,
        "--request-id",
        "paper-retry-next",
        "--reason",
        "owner retries",
        "--actor",
        "owner",
    )
    assert next_retry.exit_code == 0, next_retry.output
    from tests.test_experiment_selection_cli import select

    prepared = fixture.layout.extraction.prepared
    changed = select(
        prepared.root,
        prepared.view_id,
        "replace-after-retry",
        "--position",
        "2",
        "--replaces",
        prepared.selection_id,
        "--replacement-reason",
        "owner replaces",
    )
    assert changed.exit_code == 0, changed.output
    before = fixture.query("tasks").stdout
    observed = (prepared.credentials / "auth-observed.json").stat().st_mtime_ns
    replay = fixture.query(
        "retry",
        paper,
        "--snapshot",
        fixture.snapshot,
        "--request-id",
        "paper-retry",
        "--reason",
        "owner retries",
        "--actor",
        "owner",
    )
    assert replay.exit_code == 0 and json.loads(replay.stdout) == receipt
    assert fixture.query("tasks").stdout == before
    assert (prepared.credentials / "auth-observed.json").stat().st_mtime_ns == observed


def test_paper_retry_rejects_ambiguity_and_explicit_stale_parent(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event, current_thread

    from sqlalchemy import Connection, Engine, event

    from paper_radar.read_tasks import ReadTaskError, ReadTasks

    fixture = read_fixture(feed, tmp_path, monkeypatch, mode="invalid")
    failed = fixture.read()
    assert failed.exit_code == 4, failed.output
    parent = json.loads(failed.stdout.splitlines()[0])["task"]["task_id"]
    root = fixture.layout.extraction.root
    paper = fixture.layout.extraction.prepared.paper_id
    tasks = ReadTasks(root.database, root.data_root)
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
            "paper-retry"
        ):
            waiting.set()
            assert release.wait(30)

    event.listen(Engine, "before_cursor_execute", pause)
    try:
        with ThreadPoolExecutor(1, thread_name_prefix="paper-retry") as pool:
            future = pool.submit(
                tasks.retry_paper,
                paper,
                snapshot_id=fixture.snapshot,
                request_id="racing-retry",
                reason="owner retries",
                actor="owner",
            )
            try:
                assert waiting.wait(30)
                # 服务故障注入:另一语言在等待期间结算两次执行失败,不伪造成功或准入。
                other = tasks.register(
                    paper,
                    snapshot_id=fixture.snapshot,
                    extraction_fingerprint=fixture.layout.identity.extraction_fingerprint,
                    output_language="en",
                    request_id="en-fault",
                )
                for _ in range(2):
                    tasks.fail(tasks.claim(other.task_id), "executor_error")
            finally:
                release.set()
            with pytest.raises(ReadTaskError, match="ambiguous_task"):
                future.result(timeout=40)
    finally:
        event.remove(Engine, "before_cursor_execute", pause)
    assert (
        tasks.replay_retry_paper(
            paper,
            snapshot_id=fixture.snapshot,
            request_id="racing-retry",
            reason="owner retries",
            actor="owner",
        )
        is None
    )
    ambiguous = fixture.query(
        "retry",
        paper,
        "--snapshot",
        fixture.snapshot,
        "--request-id",
        "ambiguous",
        "--reason",
        "owner retries",
        "--actor",
        "owner",
    )
    assert ambiguous.exit_code == 2 and "ambiguous_task" in ambiguous.output
    resolved = fixture.query(
        "retry",
        paper,
        "--snapshot",
        fixture.snapshot,
        "--task-id",
        parent,
        "--request-id",
        "explicit-parent",
        "--reason",
        "owner retries",
        "--actor",
        "owner",
    )
    assert resolved.exit_code == 0, resolved.output
    child = json.loads(resolved.stdout)["task_id"]
    assert (
        tasks.task(child).parent_task_id == parent and tasks.task(child).attempts == ()
    )
    stale = fixture.query(
        "retry",
        paper,
        "--snapshot",
        fixture.snapshot,
        "--task-id",
        parent,
        "--request-id",
        "stale-parent",
        "--reason",
        "owner retries",
        "--actor",
        "owner",
    )
    assert stale.exit_code == 2 and "not_latest" in stale.output


@pytest.mark.parametrize("state", ["succeeded", "ready", "running", "lease_expired"])
def test_paper_retry_refuses_nonfailed_states_without_implicit_reclaim(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, state: str
) -> None:
    from datetime import UTC, datetime, timedelta
    from typing import Any

    from paper_radar import reading_cli
    from paper_radar.read_execution import service as rpc
    from tests.test_owner_live_waiver import command as waiver

    fixture = read_fixture(feed, tmp_path, monkeypatch)
    root = fixture.layout.extraction.root
    now = [datetime.now(UTC)]
    monkeypatch.setattr(reading_cli, "reading_clock", lambda: now[0])
    if state == "ready":
        assert (
            waiver(root.database, "--disable", "--reason", "hold ready").exit_code == 0
        )
    if state in {"running", "lease_expired"}:

        def interrupted(*args: Any, **kwargs: Any) -> Any:
            raise KeyboardInterrupt

        monkeypatch.setattr(rpc, "run_call", interrupted)
    result = fixture.read()
    assert result.exit_code == (
        0 if state == "succeeded" else 2 if state == "ready" else 130
    ), result.output
    before = json.loads(fixture.query("tasks").stdout)
    if state == "lease_expired":
        now[0] += timedelta(seconds=601)
    paper = fixture.layout.extraction.prepared.paper_id
    rejected = fixture.query(
        "retry",
        paper,
        "--snapshot",
        fixture.snapshot,
        "--request-id",
        "invalid-state-retry",
        "--reason",
        "owner retries",
        "--actor",
        "owner",
    )
    assert rejected.exit_code == 2 and "not_failed" in rejected.output
    assert json.loads(fixture.query("tasks").stdout) == before


def test_noncurrent_fingerprint_cannot_retry_and_paper_request_survives_cold_restore(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os
    import subprocess
    import sys

    from typer.testing import CliRunner

    from paper_radar.cli import app
    from paper_radar.config import compile_config
    from tests.config_projection_support import new_yaml_version

    fixture = read_fixture(feed, tmp_path, monkeypatch, mode="invalid")
    failed = fixture.read()
    assert failed.exit_code == 4, failed.output
    parent = json.loads(failed.stdout.splitlines()[0])["task"]["task_id"]
    root = fixture.layout.extraction.root
    paper = fixture.layout.extraction.prepared.paper_id
    new_yaml_version(
        root.settings,
        "models",
        lambda c: c["reading"].update(model="different-read-model"),
    )
    changed = compile_config(root.settings, root.database).snapshot_id
    for extra in ([], ["--task-id", parent]):
        denied = fixture.query(
            "retry",
            paper,
            "--snapshot",
            changed,
            "--request-id",
            "noncurrent" + str(len(extra)),
            "--reason",
            "owner retries",
            "--actor",
            "owner",
            *extra,
        )
        assert denied.exit_code == 2 and "not_failed" in denied.output
    registered = fixture.query(
        "retry",
        paper,
        "--snapshot",
        fixture.snapshot,
        "--request-id",
        "cold-paper-retry",
        "--reason",
        "owner retries",
        "--actor",
        "owner",
    )
    assert registered.exit_code == 0, registered.output
    before = dict(
        receipt=json.loads(registered.stdout),
        tasks=json.loads(fixture.query("tasks").stdout),
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
            str(tmp_path / "backups"),
        ],
    )
    assert backup.exit_code == 0, backup.output
    (batch,) = (tmp_path / "backups").iterdir()
    restored = tmp_path / "restored"
    actual_restore = subprocess.run(
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
    assert actual_restore.returncode == 0, actual_restore.stdout + actual_restore.stderr
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
            "-B",
            "-m",
            "tests.experiment_read_retry_recovery_worker",
            str(restored),
            paper,
            fixture.snapshot,
        ],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert cold.returncode == 0, cold.stdout + cold.stderr
    assert json.loads(cold.stdout) == before


def test_expired_read_settles_then_paper_retry_and_single_task_execution(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from datetime import UTC, datetime, timedelta
    from typing import Any

    from paper_radar import reading_cli
    from paper_radar.llm.rpc import run_call
    from paper_radar.read_execution import service as rpc

    fixture = read_fixture(feed, tmp_path, monkeypatch)
    now = [datetime.now(UTC)]
    monkeypatch.setattr(reading_cli, "reading_clock", lambda: now[0])

    def interrupted(*args: Any, **kwargs: Any) -> Any:
        raise KeyboardInterrupt

    monkeypatch.setattr(rpc, "run_call", interrupted)
    first = fixture.read()
    assert first.exit_code == 130, first.output
    (parent,) = json.loads(fixture.query("tasks").stdout)
    now[0] += timedelta(seconds=601)
    reclaimed = fixture.query("reclaim", parent["task_id"])
    assert reclaimed.exit_code == 0 and json.loads(reclaimed.stdout)["state"] == "ready"
    second = fixture.read(request=None, task=parent["task_id"])
    assert second.exit_code == 130, second.output
    now[0] += timedelta(seconds=601)
    paper = fixture.layout.extraction.prepared.paper_id
    refused = fixture.query(
        "retry",
        paper,
        "--snapshot",
        fixture.snapshot,
        "--request-id",
        "expired-parent",
        "--reason",
        "owner retries",
        "--actor",
        "owner",
    )
    assert refused.exit_code == 2 and "not_failed" in refused.output
    assert (
        json.loads(fixture.query("failures", "--snapshot", fixture.snapshot).stdout)
        == []
    )
    settled = fixture.query("reclaim", parent["task_id"])
    assert settled.exit_code == 0 and json.loads(settled.stdout)["state"] == "failed"
    retry = fixture.query(
        "retry",
        paper,
        "--snapshot",
        fixture.snapshot,
        "--request-id",
        "settled-parent",
        "--reason",
        "owner retries",
        "--actor",
        "owner",
    )
    assert retry.exit_code == 0, retry.output
    child = json.loads(retry.stdout)["task_id"]
    tasks = json.loads(fixture.query("tasks").stdout)
    assert next(t for t in tasks if t["task_id"] == child)["attempts"] == []
    monkeypatch.setattr(rpc, "run_call", run_call)
    executed = fixture.read(request=None, task=child)
    assert executed.exit_code == 0, executed.output
    current = json.loads(executed.stdout)["task"]
    assert current["state"] == "succeeded" and len(current["attempts"]) == 1


def test_explicit_en_successor_keeps_frozen_language_and_never_registers_new_input(
    feed: FeedFixture, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import re

    from sqlalchemy import Connection, Engine, event

    from paper_radar.read_tasks import ReadTasks

    fixture = read_fixture(feed, tmp_path, monkeypatch)
    root = fixture.layout.extraction.root
    paper = fixture.layout.extraction.prepared.paper_id
    tasks = ReadTasks(root.database, root.data_root)
    # 故障注入:既有en任务两次执行失败,后继只改变代际,不创造中文输入。
    parent = tasks.register(
        paper,
        snapshot_id=fixture.snapshot,
        extraction_fingerprint=fixture.layout.identity.extraction_fingerprint,
        output_language="en",
        request_id="frozen-en-parent",
    )
    for _ in range(2):
        tasks.fail(tasks.claim(parent.task_id), "executor_error")
    retry = fixture.query(
        "retry",
        paper,
        "--snapshot",
        fixture.snapshot,
        "--task-id",
        parent.task_id,
        "--request-id",
        "en-successor",
        "--reason",
        "owner retries",
        "--actor",
        "owner",
    )
    assert retry.exit_code == 0, retry.output
    child = json.loads(retry.stdout)["task_id"]
    before = [(t.task_id, t.fingerprint, t.generation) for t in tasks.history(paper)]
    forbidden: list[str] = []

    def reject_new_registration(
        connection: Connection,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        if re.search(
            r'INSERT\s+INTO\s+["`]?'
            r"read_(registrations|budgets|tasks)\b",
            statement,
            re.I,
        ):
            forbidden.append("registration attempted")
            raise RuntimeError("new Read registration forbidden during continuation")

    event.listen(Engine, "before_cursor_execute", reject_new_registration)
    try:
        resumed = fixture.read(request=None, task=child)
    finally:
        event.remove(Engine, "before_cursor_execute", reject_new_registration)
    # 合成RPC只返回zh;真正沿en执行故收到语言不符的output_invalid,不得改成zh成功。
    assert resumed.exit_code == 4, resumed.output
    value = json.loads(resumed.stdout.splitlines()[0])["task"]
    assert value["output_language"] == "en" and value["task_id"] == child
    assert [a["failure"] for a in value["attempts"]] == [
        "output_invalid",
        "output_invalid",
    ]
    assert forbidden == []
    assert [
        (t.task_id, t.fingerprint, t.generation) for t in tasks.history(paper)
    ] == before
    assert {t.output_language for t in tasks.history(paper)} == {"en"}
