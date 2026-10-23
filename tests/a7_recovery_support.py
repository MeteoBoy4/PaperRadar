"""新解释器只从备份恢复任务历史,隔离原路径后继续既有预算。"""

import json
import sqlite3
import sys
from collections.abc import Callable
from contextlib import closing
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from paper_radar.backup.restore import restore_backup
from paper_radar.papers import PaperFacts
from paper_radar.screening import ValuePredictionOutput
from paper_radar.screening_tasks import (
    ScreeningTasks,
    SuccessCandidate,
    TaskError,
    TaskReason,
)
from paper_radar.storage.database import upgrade_database
from tests.a7_value_support import value_payload
from tests.backup_support import tree
from tests.test_paper_mapping import screening_fields
from tests.test_paper_service import observation
from tests.test_version_relations import relation


def _reject_paths(blocked: list[Path]) -> None:
    def audit(event: str, args: tuple[Any, ...]) -> None:
        if event not in {"open", "sqlite3.connect", "os.listdir", "os.scandir"}:
            return
        if not args or not isinstance(args[0], (str, bytes)):
            return
        raw = args[0].decode() if isinstance(args[0], bytes) else args[0]
        parsed = unquote(urlsplit(raw).path) if raw.startswith("file:") else raw
        path = Path(parsed).resolve()
        if any(path == base or base in path.parents for base in blocked):
            raise RuntimeError("original_directory_forbidden")

    sys.addaudithook(audit)
    for base in blocked:
        for path in (str(base / "probe"), "file:" + str(base / "probe") + "?mode=ro"):
            try:
                sqlite3.connect(path, uri=path.startswith("file:"))
            except RuntimeError as error:
                assert str(error) == "original_directory_forbidden"
            else:
                raise AssertionError("original_path_not_blocked")


def _reason(call: Callable[[], object], reason: TaskReason) -> None:
    try:
        call()
    except TaskError as error:
        assert error.reason == reason
    else:
        raise AssertionError("expected_controlled_rejection")


def run() -> None:
    batch, target, moved = (Path(path) for path in sys.argv[1:4])
    ids, expected = json.loads(sys.argv[4]), json.loads(sys.argv[5])
    blocked = [Path(path).resolve() for path in sys.argv[6:]]
    _reject_paths(blocked)
    restored = restore_backup(batch, target)
    restored.target_dir.rename(moved)
    blocked.append(batch.resolve())
    _reject_paths(blocked)
    database = moved / "database.sqlite3"
    tasks = ScreeningTasks(
        database, moved, clock=lambda: datetime(2026, 1, 1, 0, 10, tzinfo=UTC)
    )
    before = tree(moved)
    with closing(sqlite3.connect(database)) as connection:
        dump = tuple(connection.iterdump())
    tasks.validate_all()
    actual = [
        asdict(tasks.query(paper_id=paper, stage=stage, snapshot_id=ids["snapshot"]))
        for paper in (ids["paper"], ids["other"])
        for stage in ("boundary", "value")
    ]
    assert json.loads(json.dumps(actual, default=str)) == expected
    for view in actual:
        for budget in view["budgets"]:
            for task in budget["tasks"]:
                for request in task["requests"]:
                    receipt = tasks.get_receipt(request["receipt_id"])
                    assert asdict(receipt) == request
                    frozen = tasks.load_input(receipt.receipt_id)
                    assert frozen.fingerprint == budget["fingerprint"]
                    assert (
                        frozen.stage_input.payload_bytes.hex()
                        == ids["payloads"][receipt.receipt_id]
                    )
                    assert (
                        frozen.snapshot.snapshot_id == ids["snapshot"]
                        or frozen.snapshot.snapshot_id == ids["old_snapshot"]
                    )
    assert tasks.load_input(ids["parent"]) == tasks.load_input(ids["successor"])
    frozen = tasks.load_input(ids["successor"])
    assert frozen.original_title_is_zh is False
    context = frozen.stage_input.value_prediction_context(
        frozen.snapshot, original_title_is_zh=False
    )
    assert context.enabled_topic_ids == frozenset({"extreme-rainfall"})
    loaded = tasks.load_success(ids["value_success"])
    assert isinstance(loaded.output, ValuePredictionOutput)
    assert loaded.output.topic_ids == ["extreme-rainfall"]
    assert loaded.audit["input_tokens"] == 0 and loaded.audit["output_tokens"] is None
    assert (
        loaded.raw_response
        == b" \n"
        + value_payload(
            topic_ids=["extreme-rainfall"], display_title_zh="极端降水诊断方法"
        )
        + b"\n "
    )
    boundary = tasks.query_successes(
        paper_id=ids["paper"], stage="boundary", snapshot_id=ids["snapshot"]
    )
    assert {view.receipt.success_id: view.applicability for view in boundary} == {
        ids["historical"]: "historical",
        ids["boundary_success"]: "current",
    }
    for success_view in boundary:
        assert tasks.load_success(
            success_view.receipt.success_id
        ).raw_response.startswith(b'{"boundary"')
    assert tasks.status(ids["successor"]).state == "lease_expired"
    assert tasks.status(ids["successor"]).used_attempts == 1
    assert tasks.status(ids["parent"]).used_attempts == 2
    assert tasks.get_receipt(ids["cached"]).cached_success_id == ids["value_success"]
    assert tree(moved) == before
    with closing(sqlite3.connect(database)) as connection:
        assert tuple(connection.iterdump()) == dump
    # 恢复与上面所有查询均不执行/回收/激活。显式准入后才继续。
    upgrade_database(database)
    calls: list[int] = []

    def executor(*_: object) -> SuccessCandidate:
        calls.append(1)
        return SuccessCandidate(value_payload(research_value=6))

    assert tasks.retry(ids["retry"]).receipt_id == ids["successor"]
    scheduled = tasks.register(
        {
            **ids["value_request"],
            "paper_id": ids["other"],
            "scheduled_day": "2026-01-04",
        }
    )
    manual = tasks.register(
        {
            "paper_id": ids["other"],
            "stage": "value",
            "snapshot_id": ids["snapshot"],
            "original_title_is_zh": False,
            "source": "manual",
            "request_id": "follow-latest",
            "actor": "local",
            "reason": "check",
        }
    )
    successor = tasks.get_receipt(ids["successor"])
    assert scheduled.task_id == manual.task_id == successor.task_id
    assert scheduled.generation == manual.generation == 1
    assert tasks.load_input(manual.receipt_id) == frozen
    tasks.run_once(scheduled.receipt_id, executor)
    assert calls == [1]
    status = tasks.status(ids["successor"])
    assert (status.state, status.used_attempts, status.remaining_attempts) == (
        "failed",
        2,
        0,
    )
    attempts = (
        tasks.query(paper_id=ids["other"], stage="value", snapshot_id=ids["snapshot"])
        .budgets[0]
        .tasks
    )
    assert attempts[1].attempts[0].failure is not None
    assert attempts[1].attempts[0].failure.kind == "outcome_unknown"
    assert [attempt.attempt_no for attempt in attempts[1].attempts] == [1, 2]
    assert attempts[0].used_attempts == 2
    assert all(
        attempt.failure is not None and attempt.failure.issues
        for attempt in attempts[0].attempts
    )
    _reason(
        lambda: tasks.run_once(ids["successor"], executor), TaskReason.BUDGET_EXHAUSTED
    )
    _reason(
        lambda: tasks.run_once(ids["failed"], executor), TaskReason.BUDGET_EXHAUSTED
    )
    hit = tasks.register({**ids["value_request"], "scheduled_day": "2026-01-04"})
    assert hit.cached_success_id == ids["value_success"]
    _reason(
        lambda: tasks.run_once(hit.receipt_id, executor), TaskReason.ALREADY_SUCCEEDED
    )
    _reason(
        lambda: tasks.retry(
            {
                "paper_id": ids["paper"],
                "stage": "value",
                "snapshot_id": ids["snapshot"],
                "parent_task_id": hit.task_id,
                "request_id": "success-retry",
                "actor": "local",
                "reason": "check",
            }
        ),
        TaskReason.ALREADY_SUCCEEDED,
    )
    assert calls == [1]
    # 同文本的正式版替换预印本; 不通过任务登记/再绑定来激活制品。
    papers = PaperFacts(database, moved)
    journal = papers.submit(
        observation(
            doi="10.1/journal",
            payload=b"journal",
            fields=screening_fields(),
            relations=relation("has-preprint"),
        )
    )
    assert journal.paper_id == ids["paper"] and journal.version_id != ids["version"]
    stable = tasks.query(
        paper_id=ids["paper"], stage="value", snapshot_id=ids["snapshot"]
    )
    assert stable.budgets[0].applicability == "current"
    requests = tasks.receipts(ids["paper"])
    removed = papers.submit(
        observation(
            doi="10.1/journal",
            payload=b"journal",
            parser_version=2,
            observed_at=datetime(2026, 1, 2, tzinfo=UTC),
            fields={"title": screening_fields()["title"]},
        )
    )
    assert removed.status == "retained"
    unknown = tasks.query(
        paper_id=ids["paper"], stage="value", snapshot_id=ids["snapshot"]
    )
    assert (unknown.budgets[0].applicability, unknown.reason) == (
        "undeterminable",
        "missing_abstract",
    )
    assert (
        tasks.query_successes(
            paper_id=ids["paper"], stage="value", snapshot_id=ids["snapshot"]
        )[0].applicability
        == "undeterminable"
    )
    restored_fields = papers.submit(
        observation(
            source_kind="registry",
            provider="crossref",
            query_key="10.1/journal",
            target_paper_id=ids["paper"],
            target_version_id=journal.version_id,
            doi="10.1/journal",
            payload=b"replacement",
            observed_at=datetime(2026, 1, 3, tzinfo=UTC),
            fields=screening_fields(),
        )
    )
    assert restored_fields.status == "retained"
    assert (
        tasks.query(paper_id=ids["paper"], stage="value", snapshot_id=ids["snapshot"])
        == stable
    )
    assert (
        tasks.query_successes(
            paper_id=ids["paper"], stage="value", snapshot_id=ids["snapshot"]
        )[0].applicability
        == "current"
    )
    assert tasks.receipts(ids["paper"]) == requests
    assert tasks.load_success(ids["value_success"]) == loaded
    tasks.validate_all()
    print(
        json.dumps(
            {
                "read_only": True,
                "remaining_calls": len(calls),
                "derived_applicability": True,
            }
        )
    )


if __name__ == "__main__":
    run()
