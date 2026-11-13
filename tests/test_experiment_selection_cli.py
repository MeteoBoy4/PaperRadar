"""B-E4 独立 D1:选样授权的 CLI、事务故障与脱网恢复。"""

import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Connection
from typer.testing import Result

from tests.test_experiment_candidates_cli import feed as feed
from tests.test_experiment_candidates_cli import invoke

Candidate = tuple[Path, str, dict[str, Any]]
Feed = tuple[Path, dict[str, Any], Callable[[str], dict[str, Any]]]


@pytest.fixture
def candidate(feed: Feed) -> Candidate:
    root, state, fetch = feed
    state["order"] = [1, 2]
    check = fetch("selection-round")
    result = invoke("candidates", "--root", str(root), "--check-id", check["check_id"])
    assert result.exit_code == 0, result.output
    return root, json.loads(result.stdout)["view_id"], check


def select(
    root: Path, view_id: str, request: str = "select-one", *extra: str
) -> Result:
    return invoke(
        "select",
        "--root",
        str(root),
        "--view-id",
        view_id,
        "--request-id",
        request,
        "--reason",
        "PRIVATE_OWNER_REASON 原文理由",
        "--actor",
        "agent",
        *extra,
    )


def test_select_freezes_authorization_and_replay_is_only_a_receipt(
    candidate: Candidate,
) -> None:
    root, view, check = candidate
    first = select(root, view, "first", "--position", "1")
    assert first.exit_code == 0, first.output
    receipt = json.loads(first.stdout)
    assert receipt["paper_id"] == check["items"][0]["paper_id"]
    assert receipt["authorizer"] == "owner" and receipt["actor"] == "agent"
    assert receipt["replayed"] is False
    replay = select(root, view, "first", "--position", "1")
    assert replay.exit_code == 0, replay.output
    assert json.loads(replay.stdout) == {**receipt, "replayed": True}
    assert "PRIVATE_" not in first.output + replay.output
    query = invoke("selection", "--root", str(root))
    assert query.exit_code == 0, query.output
    assert json.loads(query.stdout)["current_selection_id"] == receipt["selection_id"]


def test_backup_rejects_selection_tampering(
    candidate: Candidate, tmp_path: Path
) -> None:
    import sqlite3

    from typer.testing import CliRunner

    from paper_radar.cli import app

    root, view, _ = candidate
    assert select(root, view, "first", "--position", "1").exit_code == 0
    with sqlite3.connect(root / "paper-radar.sqlite3") as connection:
        # 模拟越过追加保护的离线损坏;正常 SQL UPDATE/DELETE 本身应被拒绝。
        connection.execute("DROP TRIGGER experiment_selections_no_update")
        connection.execute("UPDATE experiment_selections SET record_json='{}'")
    backup = CliRunner().invoke(
        app,
        [
            "backup",
            "create",
            "--database",
            str(root / "paper-radar.sqlite3"),
            "--data-root",
            str(root),
            "--output",
            str(tmp_path / "backups"),
        ],
    )
    assert backup.exit_code == 2, backup.output
    assert "registration_invalid" in backup.output


def test_request_conflicts_and_replacement_keeps_a_b_a_history(
    candidate: Candidate,
) -> None:
    root, view, _ = candidate
    first = json.loads(select(root, view, "a", "--position", "1").stdout)
    conflict = select(root, view, "a", "--position", "2")
    assert conflict.exit_code == 2 and "request_conflict" in conflict.output
    missing = select(root, view, "b", "--position", "2")
    assert missing.exit_code == 2 and "replacement_required" in missing.output
    second_result = select(
        root,
        view,
        "b",
        "--doi",
        "https://doi.org/10.1029/SYNTHETIC2",
        "--replaces",
        first["selection_id"],
        "--replacement-reason",
        "PRIVATE_REPLACEMENT_REASON 原因",
    )
    assert second_result.exit_code == 0, second_result.output
    second = json.loads(second_result.stdout)
    third_result = select(
        root,
        view,
        "a-again",
        "--position",
        "1",
        "--replaces",
        second["selection_id"],
        "--replacement-reason",
        "重新研究问题",
    )
    assert third_result.exit_code == 0, third_result.output
    third = json.loads(third_result.stdout)
    assert third["selection_id"] != first["selection_id"]
    stale = select(
        root,
        view,
        "stale",
        "--position",
        "2",
        "--replaces",
        first["selection_id"],
        "--replacement-reason",
        "旧请求",
    )
    assert stale.exit_code == 2 and "selection_changed" in stale.output
    replay = select(root, view, "a", "--position", "1")
    assert replay.exit_code == 0
    assert json.loads(replay.stdout) == {**first, "replayed": True}
    result = invoke("selection", "--root", str(root))
    history = json.loads(result.stdout)
    assert history["current_selection_id"] == third["selection_id"]
    assert [entry["selection_id"] for entry in history["history"]] == [
        first["selection_id"],
        second["selection_id"],
        third["selection_id"],
    ]
    assert "PRIVATE_" not in conflict.output + second_result.output + result.output


@pytest.mark.parametrize(
    "arguments,reason",
    [
        (("--position", "999"), "candidate_not_found"),
        (("--doi", "10.1029/not-in-check"), "candidate_not_found"),
        (("--position", "1", "--doi", "10.1029/synthetic1"), "invalid_request"),
        (("--position", "0"), "invalid_request"),
        (("--position", "1", "--replacement-reason", "unbound"), "invalid_request"),
        (("--position", "1", "--actor", "PRIVATE_INVALID_ACTOR"), "invalid_request"),
    ],
)
def test_controlled_selection_rejections_do_not_write_authorizations(
    candidate: Candidate, arguments: tuple[str, ...], reason: str
) -> None:
    root, view, _ = candidate
    result = select(root, view, "invalid", *arguments)
    assert result.exit_code == 2, result.output
    assert reason in result.output
    assert "PRIVATE_" not in result.output
    assert json.loads(invoke("selection", "--root", str(root)).stdout)["history"] == []


def test_current_revision_changes_reject_old_view_and_allow_explicit_new_view(
    candidate: Candidate,
) -> None:
    from paper_radar.papers import PaperFacts
    from tests.test_experiment_candidates_cli import MAIN

    root, view, check = candidate
    papers = PaperFacts(root / "paper-radar.sqlite3", root)
    current = papers.show(check["items"][0]["paper_id"])
    papers.correct(
        dict(
            version_id=current.version_id,
            request_id="later-correction",
            actor="owner",
            reason="synthetic",
            fields={
                "abstract": {
                    "value": {
                        "text": MAIN + " Added current fact.",
                        "is_truncated": False,
                        "rule": "synthetic",
                    },
                    "locator": "manual/abstract",
                }
            },
        )
    )
    refused = select(root, view, "old-view", "--position", "1")
    assert refused.exit_code == 2, refused.output
    assert "basis_changed" in refused.output and "revision_changed" in refused.output
    assert "metadata_changed" in refused.output
    refreshed = invoke(
        "candidates", "--root", str(root), "--check-id", check["check_id"]
    )
    accepted = select(
        root, json.loads(refreshed.stdout)["view_id"], "refreshed", "--position", "1"
    )
    assert accepted.exit_code == 0, accepted.output
    assert json.loads(accepted.stdout)["revision_no"] == current.revision_no + 1


def test_missing_and_truncated_candidates_cannot_authorize(feed: Feed) -> None:
    root, state, fetch = feed
    state["order"] = [1]
    state["missing"] = True
    check = fetch("missing")
    result = invoke("candidates", "--root", str(root), "--check-id", check["check_id"])
    refused = select(
        root, json.loads(result.stdout)["view_id"], "missing", "--position", "1"
    )
    assert refused.exit_code == 2 and "candidate_not_ready" in refused.output


def test_select_checks_shared_visibility_before_opening_write_transaction(
    candidate: Candidate, monkeypatch: pytest.MonkeyPatch
) -> None:
    from contextlib import contextmanager

    from paper_radar.calibration import visibility
    from paper_radar.experiment import selections

    root, view, _ = candidate
    calls: list[str] = []
    real_visibility = visibility.evaluate_visibility
    from paper_radar.feed_metadata.repository import transaction as real_transaction

    def observe(hidden: frozenset[visibility.HiddenCondition]) -> visibility.Visibility:
        calls.append("visibility")
        return real_visibility(frozenset({visibility.HiddenCondition.UNREVEALED}))

    @contextmanager
    def transaction(database: Path, *, write: bool = False) -> Iterator[Connection]:
        if write:
            calls.append("write")
        with real_transaction(database, write=write) as connection:
            yield connection

    monkeypatch.setattr(visibility, "evaluate_visibility", observe)
    monkeypatch.setattr(selections, "transaction", transaction)
    refused = select(root, view, "hidden", "--position", "1")
    assert refused.exit_code == 2 and "visibility_denied" in refused.output
    assert calls == ["visibility"]


def test_select_entry_logs_only_safe_envelope_and_query_does_not_log(
    candidate: Candidate,
) -> None:
    root, view, _ = candidate
    result = select(root, view, "log", "--position", "1")
    assert result.exit_code == 0, result.output
    path = root / "logs/runtime.jsonl"
    data = path.read_bytes()
    entries = [json.loads(line) for line in data.decode().splitlines()]
    assert [entry["event"] for entry in entries[-2:]] == ["run_started", "run_finished"]
    assert all(entry["component"] == "experiment" for entry in entries[-2:])
    assert "PRIVATE_" not in data.decode()
    query = invoke("selection", "--root", str(root))
    assert query.exit_code == 0
    assert path.read_bytes() == data


@pytest.mark.parametrize("command", ["select", "selection"])
def test_selection_help_is_chinese_without_network_database_or_files(
    tmp_path: Path, command: str
) -> None:
    import os
    import subprocess
    import sys
    from pathlib import Path

    result = subprocess.run(
        [
            str(Path(sys.executable).with_name("paper-radar")),
            "experiment",
            command,
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
    for text in ("参数", "副作用", "自动配额", "输出去向", "常见失败", "示例", "130"):
        assert text in result.stdout
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("fault", ["insert", "after_insert"])
def test_selection_transaction_interruption_leaves_no_partial_authorization(
    candidate: Candidate, fault: str
) -> None:
    from contextlib import nullcontext

    from sqlalchemy import Engine, event
    from sqlalchemy.exc import SQLAlchemyError

    from paper_radar.experiment.selections import Selections
    from tests.artifact_support import fail_sql

    root, view, _ = candidate
    service = Selections(root / "paper-radar.sqlite3", root)

    def interrupt(
        connection: Connection,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        if statement.startswith("INSERT INTO experiment_selections"):
            raise KeyboardInterrupt("PRIVATE_FAILURE")

    if fault == "after_insert":
        event.listen(Engine, "after_cursor_execute", interrupt)
    try:
        with (
            (
                fail_sql("INSERT INTO experiment_selections")
                if fault == "insert"
                else nullcontext()
            ),
            pytest.raises(
                SQLAlchemyError if fault == "insert" else KeyboardInterrupt,
                match="nonexistent_a3_table"
                if fault == "insert"
                else "PRIVATE_FAILURE",
            ),
        ):
            service.select(
                view_id=view,
                request_id="interrupted",
                position=1,
                reason="PRIVATE_OWNER_REASON 原文理由",
                actor="agent",
            )
    finally:
        if fault == "after_insert":
            event.remove(Engine, "after_cursor_execute", interrupt)
    query = invoke("selection", "--root", str(root))
    assert query.exit_code == 0 and json.loads(query.stdout)["history"] == []
    retried = select(root, view, "interrupted", "--position", "1")
    assert retried.exit_code == 0 and json.loads(retried.stdout)["replayed"] is False


def test_concurrent_replacements_have_one_current_sample(candidate: Candidate) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from paper_radar.experiment.selections import SelectionError, Selections

    root, view, _ = candidate
    first = json.loads(select(root, view, "first", "--position", "1").stdout)
    barrier = Barrier(2)

    def replace(number: int) -> str:
        barrier.wait(timeout=10)
        try:
            record, _ = Selections(root / "paper-radar.sqlite3", root).select(
                view_id=view,
                request_id=f"replace-{number}",
                position=number,
                reason="PRIVATE_OWNER_REASON 原文理由",
                actor="agent",
                replaces=first["selection_id"],
                replacement_reason="race synthetic",
            )
            return record.selection_id
        except SelectionError as error:
            return error.reason

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(replace, (1, 2)))
    assert results.count("selection_changed") == 1
    query = json.loads(invoke("selection", "--root", str(root)).stdout)
    assert len(query["history"]) == 2
    assert query["current_selection_id"] in results


@pytest.mark.parametrize(
    "action",
    [
        "UPDATE experiment_selections SET request_id='overwrite'",
        "DELETE FROM experiment_selections",
        "INSERT OR REPLACE INTO experiment_selections "
        "SELECT * FROM experiment_selections",
    ],
)
def test_database_rejects_mutating_selection_history(
    candidate: Candidate, action: str
) -> None:
    import sqlite3

    root, view, _ = candidate
    first = select(root, view, "first", "--position", "1")
    assert first.exit_code == 0
    with (
        sqlite3.connect(root / "paper-radar.sqlite3") as connection,
        pytest.raises(sqlite3.IntegrityError, match="append_only"),
    ):
        connection.execute(action)
    assert (
        len(json.loads(invoke("selection", "--root", str(root)).stdout)["history"]) == 1
    )


def test_backup_restore_subprocess_keeps_private_reason_and_full_authorization(
    candidate: Candidate, tmp_path: Path
) -> None:
    import os
    import subprocess
    import sys
    from pathlib import Path

    from typer.testing import CliRunner

    from paper_radar.cli import app

    root, view, _ = candidate
    first = select(root, view, "first", "--position", "1")
    assert first.exit_code == 0
    expected = json.loads(invoke("selection", "--root", str(root)).stdout)
    backups = tmp_path / "backups"
    result = CliRunner().invoke(
        app,
        [
            "backup",
            "create",
            "--database",
            str(root / "paper-radar.sqlite3"),
            "--data-root",
            str(root),
            "--output",
            str(backups),
        ],
    )
    assert result.exit_code == 0, result.output
    (batch,) = backups.iterdir()
    restored = tmp_path / "restored"
    env = {
        **os.environ,
        "PYTHONPATH": str(Path(__file__).parent / "deny_external_io"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    # 帮助的 SQLite 拒绝钩子不适用于恢复;查询另加网络拒绝钩子。
    env.pop("PYTHONPATH")
    restore = subprocess.run(
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
    assert restore.returncode == 0, restore.stdout + restore.stderr
    # 原根不可用且进程内禁用 socket;历史查询不要求原根、供给、凭据或 views 文件。
    root.rename(tmp_path / "unavailable-original")
    code = """
import json, socket, sys
from pathlib import Path
from paper_radar.experiment.selections import Selections, receipt
from paper_radar.experiment.validation import validate_all
def deny_network(*args, **kwargs):
    raise AssertionError('network forbidden')
socket.socket = deny_network
root=Path(sys.argv[1])
validate_all(root/'database.sqlite3',root)
records=Selections(root/'database.sqlite3',root).history()
assert records[0].request.reason == 'PRIVATE_OWNER_REASON 原文理由'
assert records[0].request.actor == 'agent' and records[0].request.authorizer == 'owner'
assert records[0].selected_at.endswith('+00:00')
print(json.dumps(dict(
    current_selection_id=records[-1].selection_id,
    history=[receipt(r) for r in records],
)))
"""
    queried = subprocess.run(
        [sys.executable, "-c", code, str(restored)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert queried.returncode == 0, queried.stderr
    assert json.loads(queried.stdout) == expected
    assert (
        "PRIVATE_"
        not in queried.stdout + queried.stderr + restore.stdout + restore.stderr
    )
    assert not (restored / "logs").exists()


@pytest.mark.parametrize(
    "kind,name",
    [("owner_waiver", "live-evidence"), ("experiment_egress", "stage-b-egress")],
)
def test_backup_validates_consumed_authorization_chains(
    candidate: Candidate, tmp_path: Path, kind: str, name: str
) -> None:
    import sqlite3

    from typer.testing import CliRunner

    from paper_radar.cli import app

    root, _, _ = candidate
    with sqlite3.connect(root / "paper-radar.sqlite3") as connection:
        connection.execute(
            "INSERT INTO config_versions VALUES(?,?,?,?,?)",
            (kind, name, "1", "wrong-hash", b"{}"),
        )
    result = CliRunner().invoke(
        app,
        [
            "backup",
            "create",
            "--database",
            str(root / "paper-radar.sqlite3"),
            "--data-root",
            str(root),
            "--output",
            str(tmp_path / "backups"),
        ],
    )
    assert result.exit_code == 2, result.output
    assert "registration_invalid" in result.output


def test_metadata_change_between_view_load_and_write_is_rejected(
    candidate: Candidate, monkeypatch: pytest.MonkeyPatch
) -> None:
    from contextlib import contextmanager

    from paper_radar.experiment import selections
    from paper_radar.feed_metadata.repository import transaction as real_transaction
    from paper_radar.papers import PaperFacts
    from tests.test_experiment_candidates_cli import MAIN

    root, view, check = candidate
    papers = PaperFacts(root / "paper-radar.sqlite3", root)
    current = papers.show(check["items"][0]["paper_id"])

    @contextmanager
    def changed_before_lock(
        database: Path, *, write: bool = False
    ) -> Iterator[Connection]:
        if write:
            papers.correct(
                dict(
                    version_id=current.version_id,
                    request_id="write-race",
                    actor="owner",
                    reason="synthetic",
                    fields={
                        "abstract": {
                            "value": {
                                "text": MAIN + " concurrent correction",
                                "is_truncated": False,
                                "rule": "synthetic",
                            },
                            "locator": "manual/abstract",
                        }
                    },
                )
            )
        with real_transaction(database, write=write) as connection:
            yield connection

    monkeypatch.setattr(selections, "transaction", changed_before_lock)
    result = select(root, view, "race", "--position", "1")
    assert result.exit_code == 2 and "basis_changed" in result.output
    assert "revision_changed" in result.output and "metadata_changed" in result.output
    assert json.loads(invoke("selection", "--root", str(root)).stdout)["history"] == []


def test_doi_must_identify_one_member_of_this_check(feed: Feed) -> None:
    root, state, fetch = feed
    state["order"] = [1, 1]
    check = fetch("duplicate")
    views = invoke("candidates", "--root", str(root), "--check-id", check["check_id"])
    result = select(
        root,
        json.loads(views.stdout)["view_id"],
        "duplicate",
        "--doi",
        "10.1029/synthetic1",
    )
    assert result.exit_code == 2 and "candidate_not_found" in result.output


@pytest.mark.parametrize("condition", ["truncated", "conflict"])
def test_blocked_snapshot_never_creates_authorization(
    feed: Feed, condition: str
) -> None:
    from paper_radar.papers import PaperFacts

    root, state, fetch = feed
    state["order"] = [1]
    check = fetch("original")
    if condition == "conflict":
        state["conflict"] = True
        check = fetch("conflicting")
    else:
        papers = PaperFacts(root / "paper-radar.sqlite3", root)
        current = papers.show(check["items"][0]["paper_id"])
        papers.correct(
            dict(
                version_id=current.version_id,
                request_id="truncated",
                actor="owner",
                reason="synthetic",
                fields={
                    "abstract": {
                        "value": {
                            "text": "PRIVATE_TRUNCATED...",
                            "is_truncated": True,
                            "rule": "synthetic",
                        },
                        "locator": "manual/abstract",
                    }
                },
            )
        )
    views = invoke("candidates", "--root", str(root), "--check-id", check["check_id"])
    refused = select(
        root, json.loads(views.stdout)["view_id"], "blocked", "--position", "1"
    )
    assert refused.exit_code == 2 and "candidate_not_ready" in refused.output
    assert json.loads(invoke("selection", "--root", str(root)).stdout)["history"] == []


def test_request_conflict_precedes_loading_a_different_view(
    candidate: Candidate,
) -> None:
    root, view, _ = candidate
    first = select(root, view, "first", "--position", "1")
    assert first.exit_code == 0
    conflict = select(root, "PRIVATE_NONEXISTENT_VIEW", "first", "--position", "1")
    assert conflict.exit_code == 2 and "request_conflict" in conflict.output
    assert "PRIVATE_" not in conflict.output
