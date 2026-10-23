"""A7-04 原始候选经公共任务接口形成不可变成功。"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from paper_radar.screening import BoundaryOutput
from paper_radar.screening_tasks import (
    FailureKind,
    FailureReceipt,
    FailureReport,
    ScreeningTasks,
    SuccessCandidate,
    SuccessReceipt,
    TaskError,
    TaskReason,
)
from paper_radar.stage_inputs import StageInput
from tests.a7_registration_support import archive, request_for


def test_boundary_raw_success_is_immutable_and_replays(tmp_path: Path) -> None:
    data = archive(tmp_path)
    service = ScreeningTasks(
        data.database, data.data_root, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    request = request_for(data)
    registered = service.register(request)
    claim = service.claim(registered.receipt_id)
    raw = b' \n{"boundary":"in_scope","reason_zh":"Weather prediction is studied."}\n '
    candidate = SuccessCandidate(raw)
    success = service.submit(claim, candidate)
    assert isinstance(success, SuccessReceipt)
    assert service.submit(claim, candidate) == success
    assert service.status(registered.receipt_id).state == "succeeded"
    loaded = service.load_success(success.success_id)
    assert loaded.raw_response == raw
    assert isinstance(loaded.output, BoundaryOutput)
    assert loaded.output.boundary == "in_scope"
    assert service.register(request) == registered
    assert registered.cached_success_id is None
    service.validate_all()


@pytest.mark.parametrize("boundary", ["in_scope", "out_of_scope", "uncertain"])
def test_driver_accepts_each_boundary_without_suggestion(
    tmp_path: Path, boundary: str
) -> None:
    import json

    data = archive(tmp_path)
    service = ScreeningTasks(
        data.database, data.data_root, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    receipt = service.register(request_for(data))
    raw = json.dumps(
        {"boundary": boundary, "reason_zh": "论文研究天气预测的物理过程。"},
        ensure_ascii=False,
    ).encode()
    result = service.run_once(receipt.receipt_id, lambda *_: SuccessCandidate(raw))
    assert isinstance(result, SuccessReceipt)
    output = service.load_success(result.success_id).output
    assert isinstance(output, BoundaryOutput)
    assert output.boundary == boundary
    assert "reason_zh" not in repr(result)
    service.validate_all()


@pytest.mark.parametrize(
    ("raw", "category", "location"),
    [
        (
            b'{"boundary":"in_scope","boundary":"out_of_scope","reason_zh":"private"}',
            "invalid_json",
            "$",
        ),
        (b"```json\n{}\n```", "invalid_json", "$"),
        (b"{", "invalid_json", "$"),
        (
            b'{"boundary":"in_scope","reason_zh":"valid","PRIVATE_SENTINEL":true}',
            "extra_field",
            "<额外字段>",
        ),
        (b'{"boundary":"in_scope","reason_zh":"TODO"}', "invalid_text", "reason_zh"),
        (b'{"boundary":"in_scope","reason_zh":5}', "invalid_type", "reason_zh"),
    ],
)
def test_invalid_raw_is_safe_budgeted_and_not_published(
    tmp_path: Path, raw: bytes, category: str, location: str
) -> None:
    data = archive(tmp_path)
    service = ScreeningTasks(
        data.database, data.data_root, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    receipt = service.register(request_for(data))
    claim = service.claim(receipt.receipt_id)
    before = {
        path: path.read_bytes() for path in data.data_root.rglob("*") if path.is_file()
    }
    result = service.submit(claim, SuccessCandidate(raw))
    assert isinstance(result, FailureReceipt)
    assert result.kind == FailureKind.OUTPUT_INVALID
    assert any(
        issue.category.value == category and location in issue.location
        for issue in result.issues
    )
    assert service.submit(claim, SuccessCandidate(raw)) == result
    assert service.status(receipt.receipt_id).used_attempts == 1
    assert "PRIVATE_SENTINEL" not in repr(result)
    assert {
        path: path.read_bytes() for path in data.data_root.rglob("*") if path.is_file()
    } == before
    service.validate_all()


def test_model_audit_unknown_and_zero_are_distinct_and_frozen(tmp_path: Path) -> None:
    data = archive(tmp_path)
    service = ScreeningTasks(
        data.database, data.data_root, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    receipt = service.register(request_for(data))
    raw = b'{"boundary":"uncertain","reason_zh":"Atmospheric evidence is limited."}'
    first = service.submit(
        service.claim(receipt.receipt_id),
        SuccessCandidate(raw, reported_model="PRIVATE_WRONG_MODEL"),
    )
    assert isinstance(first, FailureReceipt)
    assert first.kind == FailureKind.MODEL_MISMATCH
    assert "PRIVATE_WRONG_MODEL" not in repr(first)
    success = service.submit(
        service.claim(receipt.receipt_id),
        SuccessCandidate(raw, input_tokens=0, output_tokens=None),
    )
    assert isinstance(success, SuccessReceipt)
    content = service.load_success(success.success_id)
    assert content.audit == {
        "executor_kind": "test",
        "reported_provider": None,
        "reported_model": None,
        "provider_request_id": None,
        "input_tokens": 0,
        "output_tokens": None,
    }
    service.validate_all()


def test_success_fences_all_lifecycle_and_retains_original_request_receipt(
    tmp_path: Path,
) -> None:
    data = archive(tmp_path)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    service = ScreeningTasks(data.database, data.data_root, clock=lambda: now)
    original = request_for(
        data,
        source="manual",
        scheduled_day=None,
        request_id="before",
        reason="check",
        actor="local",
    )
    old_receipt = service.register(original)
    claim = service.claim(old_receipt.receipt_id)
    now += timedelta(hours=1)
    success = service.submit(
        claim,
        SuccessCandidate(
            b'{"boundary":"in_scope","reason_zh":"Atmospheric methods are studied."}'
        ),
    )
    assert isinstance(success, SuccessReceipt)
    assert service.reclaim(old_receipt.receipt_id).state == "succeeded"
    operations: list[tuple[Callable[[], object], TaskReason]] = [
        (lambda: service.claim(old_receipt.receipt_id), TaskReason.ALREADY_SUCCEEDED),
        (lambda: service.renew(claim.renewal_handle), TaskReason.INVALID_CREDENTIAL),
        (
            lambda: service.fail(claim, FailureReport(FailureKind.TIMEOUT)),
            TaskReason.SETTLEMENT_CONFLICT,
        ),
        (
            lambda: service.submit(claim, SuccessCandidate(b"{}")),
            TaskReason.SETTLEMENT_CONFLICT,
        ),
    ]
    for operation, reason in operations:
        with pytest.raises(TaskError) as error:
            operation()
        assert error.value.reason == reason
    assert service.register(original) == old_receipt
    new = service.register({**original, "request_id": "after"})
    assert new.cached_success_id == success.success_id
    assert service.status(new.receipt_id).used_attempts == 1
    assert service.get_receipt(old_receipt.receipt_id).cached_success_id is None
    views = service.query_successes(
        paper_id=data.paper_id, stage="boundary", snapshot_id=data.snapshot_id
    )
    assert views[0].applicability == "current"
    assert views[0].paper_reason is None
    assert "reason_zh" not in repr(views)
    service.validate_all()


def test_second_executor_gets_safe_a1_paths_without_failed_raw(tmp_path: Path) -> None:
    data = archive(tmp_path)
    service = ScreeningTasks(
        data.database, data.data_root, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    receipt = service.register(request_for(data))
    service.run_once(
        receipt.receipt_id,
        lambda *_: SuccessCandidate(
            b'{"boundary":"in_scope","reason_zh":42,"PRIVATE_SENTINEL":"never persist"}'
        ),
    )
    seen: list[str | None] = []

    def executor(
        _input: StageInput, correction: str | None, _handle: str
    ) -> SuccessCandidate:
        seen.append(correction)
        return SuccessCandidate(
            b'{"boundary":"in_scope","reason_zh":"Weather methods are studied."}'
        )

    assert isinstance(service.run_once(receipt.receipt_id, executor), SuccessReceipt)
    assert seen[0] is not None
    assert "$.reason_zh" in seen[0] and "invalid_type" in seen[0]
    assert "PRIVATE_SENTINEL" not in seen[0] and "never persist" not in seen[0]


@pytest.mark.parametrize(
    "audit",
    [
        {"executor_kind": "production"},
        {"input_tokens": True},
        {"output_tokens": -1},
        {"reported_provider": 42},
        {"provider_request_id": "\ud800"},
    ],
)
def test_invalid_executor_audit_is_safe_protocol_failure(
    tmp_path: Path, audit: dict[str, object]
) -> None:
    from typing import Any

    data = archive(tmp_path)
    service = ScreeningTasks(
        data.database, data.data_root, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    receipt = service.register(request_for(data))
    malformed: Any = audit
    result = service.run_once(
        receipt.receipt_id, lambda *_: SuccessCandidate(b"{}", **malformed)
    )
    assert isinstance(result, FailureReceipt)
    assert result.kind == FailureKind.PROTOCOL_ERROR
    assert service.status(receipt.receipt_id).used_attempts == 1
    service.validate_all()


def test_parsed_or_validated_claim_cannot_bypass_authority_and_other_paper_succeeds(
    tmp_path: Path,
) -> None:
    from typing import Any

    from paper_radar.papers import PaperFacts
    from tests.test_paper_mapping import screening_fields
    from tests.test_paper_service import observation

    data = archive(tmp_path)
    service = ScreeningTasks(
        data.database, data.data_root, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    receipt = service.register(request_for(data))
    bypass: Any = {
        "validated": True,
        "boundary": "in_scope",
        "reason_zh": "PRIVATE_SENTINEL",
    }
    result = service.run_once(receipt.receipt_id, lambda *_: bypass)
    assert isinstance(result, FailureReceipt)
    assert result.kind == FailureKind.PROTOCOL_ERROR
    other = PaperFacts(data.database, data.data_root).submit(
        observation(doi="10.1234/other", fields=screening_fields())
    )
    assert other.paper_id
    other_receipt = service.register(request_for(data, paper_id=other.paper_id))
    success = service.run_once(
        other_receipt.receipt_id,
        lambda *_: SuccessCandidate(
            b'{"boundary":"in_scope","reason_zh":"Atmospheric methods are studied."}',
            reported_provider="provider-a",
            reported_model="real-model",
            input_tokens=0,
            output_tokens=0,
        ),
    )
    assert isinstance(success, SuccessReceipt)
    assert service.load_success(success.success_id).audit["output_tokens"] == 0
    service.validate_all()


@pytest.mark.parametrize("via_driver", [False, True])
def test_unserializable_nonnegative_token_audit_is_controlled(
    tmp_path: Path, via_driver: bool
) -> None:
    data = archive(tmp_path)
    service = ScreeningTasks(
        data.database, data.data_root, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    receipt = service.register(request_for(data))
    candidate = SuccessCandidate(b"{}", input_tokens=10**5000)
    if via_driver:
        result = service.run_once(receipt.receipt_id, lambda *_: candidate)
        assert isinstance(result, FailureReceipt)
        assert result.kind == FailureKind.PROTOCOL_ERROR
    else:
        claim = service.claim(receipt.receipt_id)
        with pytest.raises(TaskError) as error:
            service.submit(claim, candidate)
        assert error.value.reason == TaskReason.INVALID_CANDIDATE
        assert service.status(receipt.receipt_id).state == "running"
    assert service.status(receipt.receipt_id).used_attempts == 1
    service.validate_all()


def test_serializable_large_token_audit_has_no_artificial_business_limit(
    tmp_path: Path,
) -> None:
    data = archive(tmp_path)
    service = ScreeningTasks(
        data.database, data.data_root, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    receipt = service.register(request_for(data))
    result = service.run_once(
        receipt.receipt_id,
        lambda *_: SuccessCandidate(
            b'{"boundary":"in_scope","reason_zh":"Atmospheric models are studied."}',
            input_tokens=10**300,
        ),
    )
    assert isinstance(result, SuccessReceipt)
    assert service.load_success(result.success_id).audit["input_tokens"] == 10**300
    service.validate_all()
