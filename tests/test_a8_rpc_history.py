"""RPC 仍遵守既有租约、Paper 输入预算及 D1 双 snapshot。"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from paper_radar.llm import render_request
from paper_radar.llm.rpc import run_call
from paper_radar.llm.rpc_types import RpcCandidate
from paper_radar.papers import PaperFacts
from paper_radar.screening_tasks import (
    FailureKind,
    FailureReceipt,
    ScreeningTasks,
    SuccessCandidate,
    SuccessReceipt,
    TaskError,
    TaskReason,
)
from tests.a8_call_support import archive, prepare_call, request_for
from tests.a8_recovery_support import audit_upgrade, fault_factory, retry_request
from tests.a8_rpc_support import FakeFactory
from tests.a8_rpc_task_support import run_attempt
from tests.test_paper_mapping import screening_fields
from tests.test_paper_service import observation
from tests.test_version_relations import relation

NOW = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.mark.parametrize("reclaim", [False, True])
def test_rpc_candidate_ownership_is_decided_by_a7_settlement_not_lease_clock(
    tmp_path: Path, reclaim: bool
) -> None:
    data = archive(tmp_path)
    now = NOW
    tasks = ScreeningTasks(data.database, data.data_root, clock=lambda: now)
    receipt = tasks.register(request_for(data))
    description = prepare_call(tasks, receipt.receipt_id)
    claim = tasks.claim(receipt.receipt_id)
    factory = FakeFactory()
    result = run_call(
        description, render_request(description), factory, clock=factory.clock
    )
    assert type(result) is RpcCandidate
    sent = repr(factory.sessions[0].commands)
    assert claim.credential not in sent and claim.renewal_handle not in sent
    candidate = SuccessCandidate(
        result.raw_response,
        reported_provider=result.provider,
        reported_model=result.model,
    )
    now = claim.expires_at + timedelta(seconds=1)
    assert tasks.status(receipt.receipt_id).state == "lease_expired"
    assert prepare_call(tasks, receipt.receipt_id) == description
    before_files = tuple(data.data_root.rglob("*"))
    if reclaim:
        status = tasks.reclaim(receipt.receipt_id)
        assert status.last_failure is FailureKind.OUTCOME_UNKNOWN
        with pytest.raises(TaskError) as error:
            tasks.submit(claim, candidate)
        assert error.value.reason is TaskReason.INVALID_CREDENTIAL
        assert tuple(data.data_root.rglob("*")) == before_files
        assert (
            tasks.query_successes(
                paper_id=data.paper_id, stage="boundary", snapshot_id=data.snapshot_id
            )
            == ()
        )
    else:
        accepted = tasks.submit(claim, candidate)
        assert type(accepted) is SuccessReceipt
        assert (
            tasks.load_success(accepted.success_id).raw_response == result.raw_response
        )
        assert tasks.reclaim(receipt.receipt_id).state == "succeeded"
    assert tasks.status(receipt.receipt_id).used_attempts == 1
    tasks.validate_all()


def test_old_130_semantics_upgrade_to_140_and_rollback_refusal_keep_retry_budget(
    tmp_path: Path,
) -> None:
    data = archive(tmp_path, pi_version="1.3.0")
    tasks = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    old = tasks.register(request_for(data))
    audit_id = audit_upgrade(data)
    newer = tasks.register(request_for(data, snapshot_id=audit_id))
    assert old.budget_id == newer.budget_id
    description = prepare_call(tasks, newer.receipt_id)
    assert (
        description.semantic_snapshot_id,
        description.audit_snapshot_id,
        description.pi_version,
        description.adapter_version,
    ) == (data.snapshot_id, audit_id, "1.4.0", "transport-v2")
    for attempt in (1, 2):
        failed = fault_factory("protocol")
        result = run_attempt(tasks, newer.receipt_id, failed, clock=failed.clock)
        assert type(result) is FailureReceipt and result.attempt_no == attempt
        assert failed.sessions[0].description == description
    rollback = tasks.register(request_for(data, scheduled_day="2026-01-02"))
    unused = FakeFactory()
    with pytest.raises(TaskError) as error:
        run_attempt(tasks, rollback.receipt_id, unused, clock=unused.clock)
    assert error.value.reason is TaskReason.INVALID_CONTEXT
    assert (
        unused.sessions == [] and tasks.status(rollback.receipt_id).used_attempts == 2
    )
    assert tasks.get_receipt(old.receipt_id) == old
    successor = tasks.retry(retry_request(data, newer, snapshot_id=audit_id))
    assert tasks.retry(retry_request(data, newer, snapshot_id=audit_id)) == successor
    retry_description = prepare_call(tasks, successor.receipt_id)
    assert retry_description == description
    factory = FakeFactory()
    success = run_attempt(tasks, successor.receipt_id, factory, clock=factory.clock)
    assert type(success) is SuccessReceipt and success.attempt_no == 1
    assert factory.sessions[0].description.pi_version == "1.4.0"
    assert factory.sessions[0].description.semantic_snapshot_id == data.snapshot_id
    assert tasks.status(newer.receipt_id).used_attempts == 2
    tasks.validate_all()


def test_audit_a_b_a_uses_each_receipt_audit_and_the_original_remaining_budget(
    tmp_path: Path,
) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    original = tasks.register(request_for(data))
    initial = prepare_call(tasks, original.receipt_id)
    failure = fault_factory("protocol")
    run_attempt(tasks, original.receipt_id, failure, clock=failure.clock)
    audit_id = audit_upgrade(data)
    upgraded = tasks.register(request_for(data, snapshot_id=audit_id))
    newer = prepare_call(tasks, upgraded.receipt_id)
    assert (
        newer.adapter_version == "transport-v2" and newer.audit_snapshot_id == audit_id
    )
    assert render_request(newer) == render_request(initial)
    rollback = tasks.register(request_for(data, scheduled_day="2026-01-02"))
    assert rollback.budget_id == upgraded.budget_id == original.budget_id
    assert prepare_call(tasks, rollback.receipt_id) == initial
    assert tasks.status(upgraded.receipt_id).remaining_attempts == 1
    factory = FakeFactory()
    success = run_attempt(tasks, rollback.receipt_id, factory, clock=factory.clock)
    assert type(success) is SuccessReceipt and success.attempt_no == 2
    assert factory.sessions[0].description.adapter_version == "transport-v1"
    assert factory.sessions[0].description.audit_snapshot_id == data.snapshot_id
    assert tasks.get_receipt(upgraded.receipt_id).snapshot_id == audit_id
    tasks.validate_all()


def test_changed_paper_input_refuses_rpc_claim_and_a_b_a_returns_to_old_budget(
    tmp_path: Path,
) -> None:
    data = archive(tmp_path)
    tasks = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    original = tasks.register(request_for(data))
    first = fault_factory("protocol")
    run_attempt(tasks, original.receipt_id, first, clock=first.clock)
    papers = PaperFacts(data.database, data.data_root)
    for label, title in (("b", "Different atmospheric research"), ("a", "Title")):
        papers.correct(
            {
                "version_id": data.version_id,
                "request_id": label,
                "actor": "local",
                "reason": "correction",
                "fields": {"title": {"value": title, "locator": "title"}},
            }
        )
        if label == "b":
            unused = FakeFactory()
            with pytest.raises(TaskError) as error:
                run_attempt(tasks, original.receipt_id, unused, clock=unused.clock)
            assert error.value.reason is TaskReason.FACTS_CHANGED
            assert (
                unused.sessions == []
                and tasks.status(original.receipt_id).used_attempts == 1
            )
            other = tasks.register(request_for(data, scheduled_day="2026-01-02"))
            assert other.budget_id != original.budget_id
            other_factory = FakeFactory()
            assert (
                type(
                    run_attempt(
                        tasks,
                        other.receipt_id,
                        other_factory,
                        clock=other_factory.clock,
                    )
                )
                is SuccessReceipt
            )
    returned = tasks.register(request_for(data, scheduled_day="2026-01-03"))
    assert (
        returned.task_id == original.task_id
        and returned.budget_id == original.budget_id
    )
    factory = FakeFactory()
    result = run_attempt(tasks, returned.receipt_id, factory, clock=factory.clock)
    assert type(result) is SuccessReceipt and result.attempt_no == 2
    assert tasks.load_input(returned.receipt_id) == tasks.load_input(
        original.receipt_id
    )
    assert {
        view.applicability
        for view in tasks.query_successes(
            paper_id=data.paper_id, stage="boundary", snapshot_id=data.snapshot_id
        )
    } == {"current", "historical"}
    tasks.validate_all()


def test_rpc_success_remains_applicable_to_new_paper_version_with_same_fingerprint(
    tmp_path: Path,
) -> None:
    data = archive(tmp_path)
    papers = PaperFacts(data.database, data.data_root)
    preprint = papers.submit(
        observation(
            doi="10.1/pre",
            version_kind="preprint",
            payload=b"preprint",
            fields=screening_fields(),
        )
    )
    assert preprint.paper_id
    tasks = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    receipt = tasks.register(request_for(data, paper_id=preprint.paper_id))
    factory = FakeFactory()
    success = run_attempt(tasks, receipt.receipt_id, factory, clock=factory.clock)
    assert type(success) is SuccessReceipt
    journal = papers.submit(
        observation(
            doi="10.1/journal",
            payload=b"journal",
            fields=screening_fields(),
            relations=relation("has-preprint"),
        )
    )
    assert (
        journal.paper_id == preprint.paper_id
        and journal.version_id != receipt.version_id
    )
    cached = tasks.register(
        request_for(data, paper_id=journal.paper_id, scheduled_day="2026-01-02")
    )
    assert (
        cached.budget_id == receipt.budget_id
        and cached.cached_success_id == success.success_id
    )
    assert cached.version_id == journal.version_id
    assert tasks.get_receipt(receipt.receipt_id) == receipt
    assert (
        tasks.query_successes(
            paper_id=preprint.paper_id, stage="boundary", snapshot_id=data.snapshot_id
        )[0].applicability
        == "current"
    )
    unused = FakeFactory()
    with pytest.raises(TaskError) as error:
        run_attempt(tasks, cached.receipt_id, unused, clock=unused.clock)
    assert error.value.reason is TaskReason.ALREADY_SUCCEEDED and unused.sessions == []
    tasks.validate_all()
