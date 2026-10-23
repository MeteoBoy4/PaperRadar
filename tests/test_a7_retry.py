"""显式 retry 保留失败历史,只追加唯一后继预算代际。"""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from paper_radar.screening_tasks import (
    FailureKind,
    FailureReport,
    ScreeningTasks,
    TaskError,
)
from tests.a7_registration_support import archive, request_for

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_retry_appends_once_and_new_requests_follow_latest(tmp_path: Path) -> None:
    data = archive(tmp_path)
    service = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    initial_request = request_for(
        data,
        source="manual",
        scheduled_day=None,
        request_id="first",
        reason="首次请求",
        actor="测试研究者",
    )
    initial = service.register(initial_request)
    for _ in range(2):
        service.fail(
            service.claim(initial.receipt_id), FailureReport(FailureKind.TIMEOUT)
        )
    retry = {
        "paper_id": data.paper_id,
        "stage": "boundary",
        "snapshot_id": data.snapshot_id,
        "parent_task_id": initial.task_id,
        "request_id": "retry-1",
        "reason": "重新处理",
        "actor": "测试研究者",
    }
    successor = service.retry(retry)
    assert successor.generation == 1
    assert successor.budget_id == initial.budget_id
    assert successor.task_id != initial.task_id
    assert service.status(initial.receipt_id).state == "failed"
    assert service.status(successor.receipt_id).remaining_attempts == 2
    assert service.retry(retry) == successor
    assert service.register(initial_request) == initial
    assert (
        service.register(request_for(data, scheduled_day="2026-01-02")).task_id
        == successor.task_id
    )
    with pytest.raises(TaskError) as conflict:
        service.retry({**retry, "reason": "不同内容"})
    assert conflict.value.reason == "request_conflict"
    with pytest.raises(TaskError) as competed:
        service.retry({**retry, "request_id": "retry-2"})
    assert competed.value.reason == "already_retried"
    assert competed.value.successor_task_id == successor.task_id
    service.validate_all()


@pytest.mark.parametrize("stage", ["boundary", "value"])
def test_each_retry_generation_has_two_attempts_and_inherits_context(
    tmp_path: Path, stage: str
) -> None:
    from tests.a7_retry_support import exhaust, retry_for

    data = archive(tmp_path)
    service = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    extra = {"original_title_is_zh": False} if stage == "value" else {}
    initial = service.register(request_for(data, stage=stage, **extra))
    frozen = service.load_input(initial.receipt_id)
    exhaust(service, initial)
    second = service.retry(retry_for(data, initial))
    assert service.load_input(second.receipt_id) == frozen
    exhaust(service, second)
    third = service.retry(retry_for(data, second, request_id="retry-2"))
    assert (
        third.generation == 2
        and service.status(third.receipt_id).remaining_attempts == 2
    )
    assert (
        service.register(
            request_for(data, stage=stage, scheduled_day="2026-01-03", **extra)
        ).task_id
        == third.task_id
    )
    assert service.retry(retry_for(data, initial)) == second
    service.validate_all()


@pytest.mark.parametrize("state", ["ready", "retryable", "running", "expired_first"])
def test_retry_rejects_tasks_without_failed_terminal_state(
    tmp_path: Path, state: str
) -> None:
    from datetime import timedelta

    from tests.a7_retry_support import retry_for

    data = archive(tmp_path)
    now = NOW
    service = ScreeningTasks(data.database, data.data_root, clock=lambda: now)
    initial = service.register(request_for(data))
    if state != "ready":
        claim = service.claim(initial.receipt_id)
        if state == "retryable":
            service.fail(claim, FailureReport(FailureKind.TIMEOUT))
        elif state == "expired_first":
            now += timedelta(seconds=600)
    before = service.status(initial.receipt_id)
    with pytest.raises(TaskError) as error:
        service.retry(retry_for(data, initial))
    assert error.value.reason == "not_failed"
    assert service.status(initial.receipt_id) == before
    assert service.receipts(data.paper_id) == (initial,)


@pytest.mark.parametrize(
    "changes",
    [
        {"reason": ""},
        {"actor": " "},
        {"request_id": ""},
        {"reason": "<script>private</script>"},
        {"request_id": "x" * 2049},
        {"parent_task_id": "invalid"},
        {"original_title_is_zh": True},
        {"source": "retry"},
        {"scheduled_day": "2026-01-02"},
        {"payload": b"private"},
        {"stage": "reading"},
    ],
)
def test_retry_strict_request_cannot_change_frozen_context(
    tmp_path: Path, changes: dict[str, object]
) -> None:
    from tests.a7_retry_support import exhaust, retry_for

    data = archive(tmp_path)
    service = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    initial = service.register(request_for(data))
    exhaust(service, initial)
    with pytest.raises(TaskError) as error:
        service.retry(retry_for(data, initial, **changes))
    assert error.value.reason == "invalid_request"
    assert service.receipts(data.paper_id) == (initial,)


def test_register_retry_source_cannot_bypass_terminal_qualification(
    tmp_path: Path,
) -> None:
    data = archive(tmp_path)
    service = ScreeningTasks(data.database)
    with pytest.raises(TaskError) as error:
        service.register(
            request_for(
                data,
                source="retry",
                scheduled_day=None,
                request_id="bypass",
                reason="尝试",
                actor="local",
            )
        )
    assert error.value.reason == "invalid_request"
    assert service.receipts(data.paper_id) == ()


def test_request_id_conflicts_are_global_between_manual_and_retry(
    tmp_path: Path,
) -> None:
    from tests.a7_retry_support import exhaust, retry_for

    data = archive(tmp_path)
    service = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    manual = request_for(
        data,
        source="manual",
        scheduled_day=None,
        request_id="shared-id",
        actor="local",
        reason="首次",
    )
    initial = service.register(manual)
    exhaust(service, initial)
    with pytest.raises(TaskError) as conflict:
        service.retry(retry_for(data, initial, request_id="shared-id"))
    assert conflict.value.reason == "request_conflict"
    successor = service.retry(retry_for(data, initial))
    with pytest.raises(TaskError) as conflict:
        service.register({**manual, "request_id": "retry-1"})
    assert conflict.value.reason == "request_conflict"
    assert service.retry(retry_for(data, initial)) == successor


def test_success_input_rejects_retry_through_real_success_path(tmp_path: Path) -> None:
    from paper_radar.screening_tasks import SuccessCandidate, SuccessReceipt
    from tests.a7_retry_support import retry_for

    data = archive(tmp_path)
    service = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    initial = service.register(request_for(data))
    success = service.submit(
        service.claim(initial.receipt_id),
        SuccessCandidate(
            b'{"boundary":"in_scope","reason_zh":"Atmospheric prediction is studied."}'
        ),
    )
    assert isinstance(success, SuccessReceipt)
    with pytest.raises(TaskError) as error:
        service.retry(retry_for(data, initial))
    assert error.value.reason == "already_succeeded"
    assert service.status(initial.receipt_id).used_attempts == 1
    assert (
        service.register(
            request_for(data, scheduled_day="2026-01-03")
        ).cached_success_id
        == success.success_id
    )
    service.validate_all()


def test_mapping_reason_precedes_old_generation_and_exact_replay_remains_original(
    tmp_path: Path,
) -> None:
    from paper_radar.papers import PaperError, PaperFacts
    from tests.a7_retry_support import exhaust, retry_for
    from tests.test_paper_mapping import screening_fields
    from tests.test_paper_service import observation

    data = archive(tmp_path)
    service = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    initial = service.register(request_for(data))
    exhaust(service, initial)
    request = retry_for(data, initial)
    successor = service.retry(request)
    PaperFacts(data.database, data.data_root).submit(
        observation(
            parser_version=2,
            observed_at=datetime(2026, 1, 2, tzinfo=UTC),
            fields={"title": screening_fields()["title"]},
        )
    )
    with pytest.raises(PaperError) as error:
        service.retry({**request, "request_id": "new-id"})
    assert error.value.reason == "missing_abstract"
    assert service.retry(request) == successor
    query = service.query(
        paper_id=data.paper_id, stage="boundary", snapshot_id=data.snapshot_id
    )
    assert query.reason == "missing_abstract" and query.current_failures == ()
    assert query.budgets[0].applicability == "undeterminable"
    service.validate_all()


def test_retry_rejects_changed_current_input_and_wrong_parent(tmp_path: Path) -> None:
    from uuid import uuid4

    from paper_radar.papers import PaperFacts
    from tests.a7_retry_support import exhaust, retry_for

    data = archive(tmp_path)
    service = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    initial = service.register(request_for(data))
    exhaust(service, initial)
    with pytest.raises(TaskError) as error:
        service.retry(retry_for(data, initial, parent_task_id=str(uuid4())))
    assert error.value.reason == "task_not_found"
    PaperFacts(data.database, data.data_root).correct(
        {
            "version_id": data.version_id,
            "request_id": "change",
            "actor": "local",
            "reason": "更正",
            "fields": {"title": {"value": "Different research", "locator": "title"}},
        }
    )
    with pytest.raises(TaskError) as error:
        service.retry(retry_for(data, initial))
    assert error.value.reason == "facts_changed"
    query = service.query(
        paper_id=data.paper_id, stage="boundary", snapshot_id=data.snapshot_id
    )
    assert (
        query.current_failures == () and query.budgets[0].applicability == "historical"
    )


def test_retry_transaction_rejects_facts_changed_after_mapping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from paper_radar.papers import PaperFacts
    from tests.a7_retry_support import exhaust, retry_for

    data = archive(tmp_path)
    service = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    initial = service.register(request_for(data))
    exhaust(service, initial)
    original_mapping = PaperFacts.map_screening_inputs

    def changing_mapping(self, **kwargs):
        mapped = original_mapping(self, **kwargs)
        corrected = PaperFacts(data.database, data.data_root).correct(
            {
                "version_id": data.version_id,
                "request_id": "concurrent-change",
                "actor": "local",
                "reason": "并发更正",
                "fields": {
                    "title": {"value": "Changed after mapping", "locator": "title"}
                },
            }
        )
        assert corrected.status == "retained"
        return mapped

    with monkeypatch.context() as patch:
        patch.setattr(PaperFacts, "map_screening_inputs", changing_mapping)
        with pytest.raises(TaskError) as error:
            service.retry(retry_for(data, initial))
    assert error.value.reason == "facts_changed"
    assert service.receipts(data.paper_id) == (initial,)
    service.validate_all()


def test_retry_parent_uniqueness_is_enforced_by_sqlite(tmp_path: Path) -> None:
    import sqlite3
    from contextlib import closing
    from uuid import uuid4

    from tests.a7_retry_support import exhaust, retry_for

    data = archive(tmp_path)
    service = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    initial = service.register(request_for(data))
    exhaust(service, initial)
    service.retry(retry_for(data, initial))
    with closing(sqlite3.connect(data.database)) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        with pytest.raises(
            sqlite3.IntegrityError,
            match=r"UNIQUE constraint failed: screening_tasks\.parent_task_id",
        ):
            connection.execute(
                "INSERT INTO screening_tasks"
                "(task_id,budget_id,generation,parent_task_id) "
                "VALUES (?,?,2,?)",
                (str(uuid4()), initial.budget_id, initial.task_id),
            )
        connection.rollback()
    service.validate_all()
