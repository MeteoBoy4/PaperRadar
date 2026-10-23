"""A7-05 value 使用公共任务闭环与冻结的权威上下文。"""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from paper_radar.screening import ValuePredictionOutput
from paper_radar.screening_tasks import (
    FailureKind,
    FailureReceipt,
    ScreeningTasks,
    SuccessCandidate,
    SuccessReceipt,
    TaskError,
    TaskReason,
)
from tests.a7_registration_support import archive, request_for
from tests.a7_value_support import value_archive, value_payload

NOW = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.mark.parametrize("original_title_is_zh", [True, False])
def test_value_success_replays_and_caches_without_boundary(
    tmp_path: Path, original_title_is_zh: bool
) -> None:
    data = archive(tmp_path)
    service = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    request = request_for(
        data, stage="value", original_title_is_zh=original_title_is_zh
    )
    receipt = service.register(request)
    raw = value_payload(
        display_title_zh=None if original_title_is_zh else "区域极端降水诊断方法"
    )
    claim = service.claim(receipt.receipt_id)
    success = service.submit(claim, SuccessCandidate(raw, input_tokens=0))
    assert isinstance(success, SuccessReceipt)
    assert success.stage == "value" and success.executor_kind == "test"
    assert service.submit(claim, SuccessCandidate(raw, input_tokens=0)) == success
    assert service.status(receipt.receipt_id).state == "succeeded"
    content = service.load_success(success.success_id)
    assert content.raw_response == raw
    assert isinstance(content.output, ValuePredictionOutput)
    assert content.output.research_value == 4
    assert content.output.display_title_zh == (
        None if original_title_is_zh else "区域极端降水诊断方法"
    )
    assert content.audit["input_tokens"] == 0
    assert content.audit["output_tokens"] is None
    cached = service.register({**request, "scheduled_day": "2026-01-02"})
    assert cached.cached_success_id == success.success_id
    assert service.get_receipt(receipt.receipt_id).cached_success_id is None
    views = service.query_successes(
        paper_id=data.paper_id, stage="value", snapshot_id=data.snapshot_id
    )
    assert len(views) == 1 and views[0].applicability == "current"
    assert "research_value" not in repr((content, views, receipt, claim))
    assert "区域极端降水" not in repr((content, views, receipt, claim))
    service.validate_all()


@pytest.mark.parametrize(
    ("changes", "category", "location"),
    [
        ({"research_value": 0}, "business_rule", "$.research_value"),
        ({"research_value": 6}, "business_rule", "$.research_value"),
        ({"research_value": True}, "invalid_type", "$.research_value"),
        ({"research_value": 1.0}, "invalid_type", "$.research_value"),
        ({"reuse_feasibility": "3"}, "invalid_type", "$.reuse_feasibility"),
        ({"reuse_feasibility": 6}, "business_rule", "$.reuse_feasibility"),
        (
            {"reuse_feasibility_inferable": 1},
            "invalid_type",
            "$.reuse_feasibility_inferable",
        ),
        (
            {"reuse_feasibility_inferable": False},
            "business_rule",
            "$.reuse_feasibility_reason_zh",
        ),
        ({"value_types": []}, "business_rule", "$.value_types"),
        ({"value_types": ["other"]}, "invalid_enum", "$.value_types[0]"),
        ({"value_types": ["method", "method"]}, "business_rule", "$.value_types[1]"),
        ({"topic_ids": ["unknown-topic"]}, "business_rule", "$.topic_ids[0]"),
        ({"topic_ids": ["disabled-topic"]}, "business_rule", "$.topic_ids[0]"),
        (
            {"topic_ids": ["extreme-rainfall", "extreme-rainfall"]},
            "business_rule",
            "$.topic_ids[1]",
        ),
        ({"display_title_zh": "暂无"}, "invalid_text", "$.display_title_zh"),
        ({"abstract_brief_zh": "待补充"}, "invalid_text", "$.abstract_brief_zh"),
        ({"PRIVATE_VALUE_OUTPUT": "never persist"}, "extra_field", "$.<额外字段>"),
    ],
)
def test_invalid_value_is_safe_budgeted_and_has_a1_paths(
    tmp_path: Path, changes: dict[str, object], category: str, location: str
) -> None:
    data = value_archive(tmp_path)
    service = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    receipt = service.register(
        request_for(data, stage="value", original_title_is_zh=False)
    )
    raw = value_payload(**changes)
    before = {
        path: path.read_bytes() for path in data.data_root.rglob("*") if path.is_file()
    }
    claim = service.claim(receipt.receipt_id)
    failed = service.submit(claim, SuccessCandidate(raw))
    assert isinstance(failed, FailureReceipt)
    assert failed.kind == FailureKind.OUTPUT_INVALID
    assert any(
        issue.location == location and issue.category.value == category
        for issue in failed.issues
    )
    assert service.submit(claim, SuccessCandidate(raw)) == failed
    assert service.status(receipt.receipt_id).used_attempts == 1
    assert (
        service.query_successes(
            paper_id=data.paper_id, stage="value", snapshot_id=data.snapshot_id
        )
        == ()
    )
    assert {
        path: path.read_bytes() for path in data.data_root.rglob("*") if path.is_file()
    } == before
    assert "PRIVATE_VALUE_OUTPUT" not in repr(failed) and "never persist" not in repr(
        failed
    )
    service.validate_all()


@pytest.mark.parametrize(
    ("raw", "category", "location"),
    [
        (b'{"research_value":4,"research_value":5}', "invalid_json", "$"),
        (b'{"research_value":NaN}', "invalid_json", "$"),
        (b"{}", "missing_field", "$.research_value"),
        (b"```json\n{}\n```", "invalid_json", "$"),
    ],
)
def test_invalid_json_and_missing_fields_consume_value_attempt(
    tmp_path: Path, raw: bytes, category: str, location: str
) -> None:
    data = archive(tmp_path)
    service = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    receipt = service.register(
        request_for(data, stage="value", original_title_is_zh=False)
    )
    failed = service.run_once(receipt.receipt_id, lambda *_: SuccessCandidate(raw))
    assert isinstance(failed, FailureReceipt)
    assert failed.kind == FailureKind.OUTPUT_INVALID
    assert any(
        issue.location == location and issue.category.value == category
        for issue in failed.issues
    )
    assert service.status(receipt.receipt_id).used_attempts == 1
    service.validate_all()


def test_chinese_display_title_fails_then_second_executor_gets_safe_correction(
    tmp_path: Path,
) -> None:
    from paper_radar.stage_inputs import StageInput

    data = archive(tmp_path)
    service = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    receipt = service.register(
        request_for(data, stage="value", original_title_is_zh=True)
    )
    failed = service.run_once(
        receipt.receipt_id,
        lambda *_: SuccessCandidate(
            value_payload(display_title_zh="PRIVATE_TRANSLATED_TITLE")
        ),
    )
    assert isinstance(failed, FailureReceipt)
    assert [(issue.category.value, issue.location) for issue in failed.issues] == [
        ("context_mismatch", "$.display_title_zh")
    ]

    def executor(
        stage_input: StageInput, correction: str | None, _handle: str
    ) -> SuccessCandidate:
        assert stage_input.stage.value == "value"
        assert correction is not None
        assert "$.display_title_zh" in correction and "context_mismatch" in correction
        assert "PRIVATE_TRANSLATED_TITLE" not in correction
        return SuccessCandidate(value_payload())

    success = service.run_once(receipt.receipt_id, executor)
    assert isinstance(success, SuccessReceipt)
    assert service.status(receipt.receipt_id).used_attempts == 2
    service.validate_all()


def test_value_second_failure_is_terminal_and_independent_of_boundary(
    tmp_path: Path,
) -> None:
    data = archive(tmp_path)
    service = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    boundary = service.register(request_for(data))
    value = service.register(
        request_for(data, stage="value", original_title_is_zh=False)
    )
    boundary_success = service.run_once(
        boundary.receipt_id,
        lambda *_: SuccessCandidate(
            b'{"boundary":"out_of_scope","reason_zh":"The subject is oceanic biology."}'
        ),
    )
    assert isinstance(boundary_success, SuccessReceipt)
    for _ in range(2):
        assert isinstance(
            service.run_once(value.receipt_id, lambda *_: SuccessCandidate(b"{}")),
            FailureReceipt,
        )
    assert service.status(value.receipt_id).state == "failed"
    with pytest.raises(TaskError) as error:
        service.run_once(value.receipt_id, lambda *_: pytest.fail("exhausted executor"))
    assert error.value.reason == TaskReason.BUDGET_EXHAUSTED
    assert service.status(boundary.receipt_id).state == "succeeded"
    service.validate_all()


def test_out_of_scope_boundary_does_not_cancel_successful_value(tmp_path: Path) -> None:
    data = value_archive(tmp_path)
    service = ScreeningTasks(data.database, data.data_root, clock=lambda: NOW)
    value = service.register(
        request_for(data, stage="value", original_title_is_zh=False)
    )
    boundary = service.register(request_for(data))
    service.run_once(
        boundary.receipt_id,
        lambda *_: SuccessCandidate(
            b'{"boundary":"out_of_scope","reason_zh":"The subject is oceanic biology."}'
        ),
    )
    success = service.run_once(
        value.receipt_id,
        lambda *_: SuccessCandidate(value_payload(topic_ids=["extreme-rainfall"])),
    )
    assert isinstance(success, SuccessReceipt)
    output = service.load_success(success.success_id).output
    assert isinstance(output, ValuePredictionOutput) and output.topic_ids == [
        "extreme-rainfall"
    ]
    service.validate_all()
