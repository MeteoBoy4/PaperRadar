"""公共任务接口保留 UTF-8 字节边界和各入口自己的 HTML 策略。"""

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

import pytest

from paper_radar.screening_tasks import (
    ScreeningTasks,
    SuccessCandidate,
    SuccessReceipt,
    TaskError,
    TaskReason,
)
from tests.a7_registration_support import archive, request_for
from tests.a7_retry_support import exhaust, retry_for


@pytest.mark.parametrize("entry", ["manual", "retry", "audit"])
@pytest.mark.parametrize(
    ("text", "bounded"),
    [
        ("", False),
        (" \t", False),
        ("private\ud800", False),
        ("界" * 682 + "ab", True),  # 恰好 2048 UTF-8 bytes
        ("界" * 683, False),  # 2049 bytes
        (" exact bytes ", True),
        ("<b>request-id</b>", True),
    ],
)
def test_text_boundaries_preserve_entry_policy(
    tmp_path: Path, entry: str, text: str, bounded: bool
) -> None:
    data = archive(tmp_path)
    service = ScreeningTasks(
        data.database, data.data_root, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    parent = service.register(request_for(data))
    claim = service.claim(parent.receipt_id) if entry == "audit" else None
    if entry == "retry":
        exhaust(service, parent)
    accepted = bounded and (entry == "audit" or not text.startswith("<"))

    def submit() -> object:
        if entry == "manual":
            return service.register(
                request_for(
                    data,
                    source="manual",
                    scheduled_day=None,
                    request_id="manual",
                    actor=text,
                    reason="核对输入",
                )
            )
        if entry == "retry":
            return service.retry(retry_for(data, parent, actor=text))
        assert claim is not None
        return service.submit(
            claim,
            SuccessCandidate(
                b'{"boundary":"in_scope","reason_zh":"Weather prediction is studied."}',
                provider_request_id=text,
            ),
        )

    if accepted:
        result = submit()
        assert submit() == result
        if entry == "audit":
            assert isinstance(result, SuccessReceipt)
            assert (
                service.load_success(result.success_id).audit["provider_request_id"]
                == text
            )
    else:
        with pytest.raises(TaskError) as error:
            submit()
        assert error.value.reason == (
            TaskReason.INVALID_CANDIDATE
            if entry == "audit"
            else TaskReason.INVALID_REQUEST
        )
    service.validate_all()


class StageText(str):
    pass


class StageEnum(StrEnum):
    BOUNDARY = "boundary"


@pytest.mark.parametrize(
    "stage", [StageText("boundary"), StageEnum.BOUNDARY, [], {}, None]
)
def test_query_stage_validation_preserves_public_entry_rules(
    tmp_path: Path, stage: object
) -> None:
    data = archive(tmp_path)
    service = ScreeningTasks(
        data.database, data.data_root, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)
    )
    arguments = {
        "paper_id": data.paper_id,
        "stage": stage,
        "snapshot_id": data.snapshot_id,
    }
    if isinstance(stage, str):
        result = service.query(**arguments)  # type: ignore[arg-type]
        assert result.stage == "boundary"
        assert type(result.stage) is str
    else:
        with pytest.raises(TaskError) as error:
            service.query(**arguments)  # type: ignore[arg-type]
        assert error.value.reason == TaskReason.INVALID_REQUEST
    with pytest.raises(TaskError) as error:
        service.query_successes(**arguments)  # type: ignore[arg-type]
    assert error.value.reason == TaskReason.INVALID_REQUEST
